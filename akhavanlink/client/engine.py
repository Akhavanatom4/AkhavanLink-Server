# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Client engine: connection state machine, packet pumps, pings and statistics.

Runs on the asyncio loop.  The only other thread is the adapter's reader thread, which hands packets over
with call_soon_threadsafe (batched), so the data path stays short and predictable.
"""
import asyncio
import collections
import json
import logging
import random
import socket
import ssl
import sys
import time

from .. import APP_NAME, CREATOR, CREATOR_FA, VERSION, PROTO
from ..common import aio, ws
from .config import normalize_server_url
from .tun import TunError, TunSpec

log = logging.getLogger("akhavanlink.engine")

FATAL_SERVER_CODES = {"bad_password", "bad_key", "bad_version", "bad_network", "bad_id", "network_full", "too_many_networks"}


def dumps(o):
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def now_us():
    return int(time.monotonic() * 1_000_000)


class Fatal(Exception):
    """An error that retrying cannot fix (wrong password, bad address, no admin rights ...)."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


def classify(e):
    """Exception -> (code, detail, fatal)"""
    if isinstance(e, aio.HandshakeError):
        st = e.status
        if st in (502, 503, 504):
            return "server_down", "HTTP %d" % st, False
        if st in (301, 302, 307, 308, 400, 403, 404, 405, 426):
            return "bad_url", "HTTP %d %s" % (st, e.detail), True
        return ("net" if st == 0 else "http"), str(e), False
    if isinstance(e, ssl.SSLCertVerificationError):
        return "tls", getattr(e, "verify_message", "") or str(e), False
    if isinstance(e, ssl.SSLError):
        return "tls", str(e), False
    if isinstance(e, socket.gaierror):
        return "dns", str(e), False
    if isinstance(e, ConnectionRefusedError):
        return "refused", str(e), False
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return "timeout", "", False
    if isinstance(e, ConnectionError):
        return "lost", str(e), False
    if isinstance(e, OSError):
        return "net", str(e), False
    return "net", "%s: %s" % (type(e).__name__, e), False


class Peer:
    __slots__ = ("ip", "nick", "rtt", "recent", "since")

    def __init__(self, ip, nick):
        self.ip, self.nick = ip, nick
        self.rtt = None
        self.recent = collections.deque(maxlen=20)
        self.since = time.time()

    def sample(self, ms):
        self.rtt = ms if self.rtt is None else self.rtt * 0.6 + ms * 0.4
        self.recent.append(0)

    def lost(self):
        self.recent.append(1)

    @property
    def loss(self):
        return round(100 * sum(self.recent) / len(self.recent)) if self.recent else 0


class _Link:
    """WebSocket handler: control messages go to a queue until joined, afterwards straight to the engine."""

    def __init__(self, engine):
        self.e = engine
        self.q = asyncio.Queue()
        self.online = False
        self.closed = asyncio.Event()
        self.last_rx = time.monotonic()

    def on_open(self, conn):
        pass

    def on_message(self, conn, op, data):
        self.last_rx = time.monotonic()
        if op == ws.OP_BINARY:
            if self.online:
                self.e._rx_packet(data)
            return
        try:
            m = json.loads(data)
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        if self.online:
            self.e._on_control(m, conn)
        else:
            self.q.put_nowait(m)

    def on_close(self, conn, exc):
        self.closed.set()
        self.q.put_nowait(None)


async def expect(link, types, timeout):
    """Wait for a control message of one of `types` (or an 'error' message)."""
    end = time.monotonic() + timeout
    while True:
        left = end - time.monotonic()
        if left <= 0:
            raise asyncio.TimeoutError()
        m = await asyncio.wait_for(link.q.get(), left)
        if m is None:
            raise ConnectionError("connection closed by the server")
        if m.get("t") in types or m.get("t") == "error":
            return m


class Engine:
    def __init__(self, cfg, loop, tun_factory, on_change=None, on_event=None):
        self.cfg = cfg
        self.log = log
        self.loop = loop
        self.tun_factory = tun_factory
        self.on_change = on_change or (lambda: None)
        self.on_event = on_event or (lambda ev: None)
        self.pp_delay = 0.0                      # demo bots: artificial answer delay for peer pings
        self.status = "idle"                     # idle | connecting | online | reconnecting | error
        self.err = None
        self.retry_at = 0.0
        self.ip = ""
        self.prefix = 0
        self.net_name = ""
        self.nick = ""
        self.peers = {}
        self.srv_rtt = None
        self.srv_hist = collections.deque(maxlen=60)
        self.srv_lost = collections.deque(maxlen=30)
        self._sp = {}
        self._pp = {}
        self._rot = 0
        self.t_online = None
        self.tx_b = self.rx_b = self.tx_p = self.rx_p = 0
        self.rate = (0.0, 0.0)
        self._last = (0, 0, time.monotonic())
        self.tun = None
        self._tun_addr = None
        self._task = None
        self._conn = None
        self._tx_conn = None
        self._txq = collections.deque()
        self._tx_sched = False
        self._was_online = False
        self._ticker = None

    # ------------------------------------------------------------------ public
    def start(self):
        self._schedule_tick()

    def connect(self):
        if self._task is not None and not self._task.done():
            return
        self.err = None
        self.retry_at = 0.0
        self._set_status("connecting")
        self._task = self.loop.create_task(self._run())

    async def disconnect(self):
        t = self._task
        self._task = None
        if t is not None and not t.done():
            t.cancel()
            try:
                await t
            except BaseException:
                pass
        await self._teardown()
        if self.status != "error":
            self._set_status("idle")

    async def shutdown(self):
        if self._ticker is not None:
            self._ticker.cancel()
            self._ticker = None
        await self.disconnect()

    def send_nick(self):
        conn = self._tx_conn
        nick = self.cfg.data["nickname"]
        if conn is not None and nick:
            self.nick = nick
            conn.send_text(dumps({"t": "nick", "nick": nick}))
            self.on_change()

    def snapshot(self):
        c = self.cfg.data
        hist = list(self.srv_hist)
        jit = 0.0
        if len(hist) >= 3:
            last = hist[-10:]
            jit = sum(abs(a - b) for a, b in zip(last, last[1:])) / (len(last) - 1)
        loss = round(100 * sum(self.srv_lost) / len(self.srv_lost)) if self.srv_lost else 0
        peers = sorted(self.peers.values(), key=lambda p: tuple(int(x) for x in p.ip.split(".")))
        waiting = self.status in ("connecting", "reconnecting") and self.retry_at > time.time()
        return {
            "t": "state", "status": self.status, "err": self.err,
            "retry_in": int(self.retry_at - time.time() + 0.99) if waiting else 0,
            "ip": self.ip, "prefix": self.prefix, "net": self.net_name or c["network"], "server": c["serverUrl"],
            "nick": self.nick or c["nickname"],
            "peers": [{"ip": p.ip, "nick": p.nick, "rtt": None if p.rtt is None else round(p.rtt, 1), "loss": p.loss}
                      for p in peers],
            "ping": {"server": None if self.srv_rtt is None else round(self.srv_rtt, 1), "jitter": round(jit, 1),
                     "loss": loss, "hist": [round(x, 1) for x in hist]},
            "traffic": {"tx": round(self.rate[0]), "rx": round(self.rate[1]), "tx_total": self.tx_b,
                        "rx_total": self.rx_b, "tx_pkts": self.tx_p, "rx_pkts": self.rx_p},
            "uptime": int(time.monotonic() - self.t_online) if self.t_online else 0,
            "cfg": self.cfg.public(), "version": VERSION, "creator": CREATOR, "creator_fa": CREATOR_FA,
        }

    async def test_server(self, url, key="", proxy=""):
        """Connect, check the hello and measure latency without joining any network."""
        try:
            u = normalize_server_url(url)
        except ValueError:
            return {"ok": False, "code": "bad_url", "detail": url}
        link = _Link(self)
        try:
            conn = await aio.connect(u, link, proxy=proxy or None, timeout=10)
        except Exception as e:
            code, detail, _ = classify(e)
            return {"ok": False, "code": code, "detail": detail}
        try:
            hello = await expect(link, ("hello",), 6)
            if hello.get("t") != "hello" or hello.get("app") != APP_NAME:
                return {"ok": False, "code": "not_server", "detail": ""}
            rtts = []
            for _ in range(4):
                n = now_us()
                conn.send_text(dumps({"t": "ping", "n": n}))
                m = await expect(link, ("pong",), 4)
                if m.get("t") == "pong":
                    rtts.append((now_us() - n) / 1000.0)
            best = min(rtts[1:] or rtts) if rtts else None
            return {"ok": True, "ms": None if best is None else round(best, 1), "ver": hello.get("ver"),
                    "proto_ok": hello.get("proto") == PROTO, "url": u}
        except Exception as e:
            code, detail, _ = classify(e)
            return {"ok": False, "code": code, "detail": detail}
        finally:
            conn.close()

    # ------------------------------------------------------------------ state helpers
    def _set_status(self, st):
        if st != self.status:
            self.log.info("status: %s -> %s", self.status, st)
        self.status = st
        self.on_change()

    def _emit(self, **ev):
        try:
            self.on_event(ev)
        except Exception:
            self.log.exception("event handler failed")

    async def _teardown(self):
        self._tx_conn = None
        self._txq.clear()
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()
        tun, self.tun = self.tun, None
        self._tun_addr = None
        if tun is not None:
            try:
                await self.loop.run_in_executor(None, tun.close)
            except Exception:
                self.log.exception("closing the adapter failed")
        self.ip = ""
        self.prefix = 0
        self.peers.clear()
        self._sp.clear()
        self._pp.clear()
        self.t_online = None
        self.srv_rtt = None
        self.srv_hist.clear()
        self.srv_lost.clear()
        self.rate = (0.0, 0.0)

    # ------------------------------------------------------------------ connection loop
    async def _run(self):
        failures = 0
        ever_online = False
        try:
            while True:
                self._was_online = False
                try:
                    await self._session()
                except Fatal as f:
                    self.err = {"code": f.code, "detail": f.detail}
                    self.log.error("fatal: %s %s", f.code, f.detail)
                    await self._teardown()
                    self._set_status("error")
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    code, detail, fatal = classify(e)
                    self.err = {"code": code, "detail": detail}
                    self.log.warning("connection problem: %s %s", code, detail)
                    if fatal:
                        await self._teardown()
                        self._set_status("error")
                        return
                self._tx_conn = None
                if self._was_online:
                    ever_online, failures = True, 0
                else:
                    failures += 1
                if not ever_online and failures >= 3:
                    await self._teardown()
                    self._set_status("error")
                    return
                wait = min(8.0, 0.7 * (failures + 1)) + random.random() * 0.6
                self.retry_at = time.time() + wait
                self._set_status("reconnecting" if ever_online else "connecting")
                await asyncio.sleep(wait)
        finally:
            self._tx_conn = None

    async def _session(self):
        c = self.cfg.data
        if not c["serverUrl"].strip():
            raise Fatal("no_server")
        try:
            url = normalize_server_url(c["serverUrl"])
        except ValueError:
            raise Fatal("bad_url", c["serverUrl"])
        if not c["network"].strip():
            raise Fatal("bad_network")
        link = _Link(self)
        conn = await aio.connect(url, link, proxy=c["proxy"] or None, timeout=12)
        self._conn = conn
        ping_task = None
        try:
            hello = await expect(link, ("hello",), 8)
            if hello.get("t") != "hello" or hello.get("app") != APP_NAME:
                raise Fatal("not_server")
            conn.send_text(dumps({"t": "join", "v": PROTO, "net": c["network"], "pw": c["password"],
                                  "id": c["clientId"], "nick": c["nickname"], "key": c["accessKey"],
                                  "want": self.ip or c["lastIp"], "os": sys.platform, "ver": VERSION}))
            w = await expect(link, ("welcome",), 10)
            if w.get("t") == "error":
                code = w.get("code", "error")
                if code in FATAL_SERVER_CODES:
                    raise Fatal(code, w.get("msg", ""))
                raise ConnectionError("%s %s" % (code, w.get("msg", "")))
            await self._on_welcome(w)
            link.online = True
            while not link.q.empty():                 # control messages that arrived while the adapter was being set up
                queued = link.q.get_nowait()
                if queued is not None:
                    self._on_control(queued, conn)
            self._was_online = True
            self._tx_conn = conn
            self.err = None
            self.retry_at = 0.0
            if self.t_online is None:
                self.t_online = time.monotonic()
            self._set_status("online")
            self.log.info("online as %s/%d in network '%s' with %d other player(s)", self.ip, self.prefix, self.net_name,
                     len(self.peers))
            ping_task = self.loop.create_task(self._pinger(conn, link))
            await link.closed.wait()
            raise ConnectionError("connection to the server was lost")
        finally:
            link.online = False
            self._tx_conn = None
            if ping_task is not None:
                ping_task.cancel()
            conn.abort()
            if self._conn is conn:
                self._conn = None

    async def _on_welcome(self, w):
        ip, prefix = w["ip"], int(w["prefix"])
        mtu = int(w.get("mtu") or 1400)
        self.ip, self.prefix = ip, prefix
        self.net_name = w.get("net") or self.cfg.data["network"]
        self.nick = w.get("nick") or self.cfg.data["nickname"]
        self.peers = {p["ip"]: Peer(p["ip"], p.get("nick", "")) for p in w.get("peers", []) if "ip" in p}
        if self.tun is None:
            spec = TunSpec(ip, prefix, min(mtu, self.cfg.data["mtu"]), self.cfg.data["firewall"])
            fut = self.loop.run_in_executor(None, self.tun_factory, spec)
            try:
                tun = await asyncio.shield(fut)
            except asyncio.CancelledError:
                fut.add_done_callback(lambda f: (not f.cancelled() and f.exception() is None) and f.result().close())
                raise
            except TunError as e:
                raise Fatal(e.code, e.detail)
            self.tun = tun
            self._tun_addr = (ip, prefix)
            tun.start(self._on_tun_packet)
        elif self._tun_addr != (ip, prefix):
            try:
                await self.loop.run_in_executor(None, self.tun.set_address, ip, prefix)
            except TunError as e:
                raise Fatal(e.code, e.detail)
            self._tun_addr = (ip, prefix)
        self.cfg.update({"lastIp": ip}, internal=True)

    # ------------------------------------------------------------------ data plane
    def _on_tun_packet(self, pkt):                   # adapter thread
        if len(pkt) < 20 or (pkt[0] >> 4) != 4 or self._tx_conn is None or len(self._txq) > 4096:
            return
        self._txq.append(pkt)
        if not self._tx_sched:
            self._tx_sched = True
            try:
                self.loop.call_soon_threadsafe(self._flush_tx)
            except RuntimeError:
                pass

    def _flush_tx(self):                              # loop thread
        self._tx_sched = False
        q = self._txq
        conn = self._tx_conn
        if conn is None or conn.closed:
            q.clear()
            return
        send = conn.send_binary
        while q:
            pkt = q.popleft()
            if send(pkt):
                self.tx_b += len(pkt)
                self.tx_p += 1

    def _rx_packet(self, data):                       # loop thread
        tun = self.tun
        if tun is None:
            return
        self.rx_b += len(data)
        self.rx_p += 1
        try:
            tun.write(data)
        except Exception:
            self.log.exception("writing to the adapter failed")

    # ------------------------------------------------------------------ control plane
    def _on_control(self, m, conn):
        t = m.get("t")
        if t == "pong":
            n = m.get("n")
            if self._sp.pop(n, None) is not None:
                ms = (now_us() - n) / 1000.0
                self.srv_hist.append(ms)
                self.srv_lost.append(0)
                self.srv_rtt = ms if self.srv_rtt is None else self.srv_rtt * 0.6 + ms * 0.4
        elif t == "pp":
            reply = dumps({"t": "pr", "to": m.get("from"), "n": m.get("n")})
            if self.pp_delay > 0:
                self.loop.call_later(self.pp_delay, conn.send_text, reply)
            else:
                conn.send_text(reply)
        elif t == "pr":
            n, ip = m.get("n"), m.get("from")
            if self._pp.pop(n, None) is not None and ip in self.peers:
                self.peers[ip].sample((now_us() - n) / 1000.0)
        elif t == "peer+":
            p = m.get("p") or {}
            ip, nick = p.get("ip"), p.get("nick", "")
            if ip and ip != self.ip:
                is_new = ip not in self.peers
                if is_new:
                    self.peers[ip] = Peer(ip, nick)
                else:
                    self.peers[ip].nick = nick
                if is_new:
                    self.log.info("%s joined (%s)", nick, ip)
                    self._emit(ev="peer_join", nick=nick, ip=ip)
        elif t == "peer-":
            p = self.peers.pop(m.get("ip"), None)
            if p is not None:
                self.log.info("%s left (%s)", p.nick, p.ip)
                self._emit(ev="peer_leave", nick=p.nick, ip=p.ip)
        elif t == "peer~":
            p = m.get("p") or {}
            if p.get("ip") in self.peers:
                self.peers[p["ip"]].nick = p.get("nick", "")
        elif t == "notice":
            self.log.info("server: %s", m.get("msg", ""))
        elif t == "error":
            self.log.warning("server error: %s %s", m.get("code"), m.get("msg"))
        self.on_change()

    async def _pinger(self, conn, link):
        while True:
            await asyncio.sleep(2.0)
            if conn.closed:
                return
            if time.monotonic() - link.last_rx > 12.0:
                self.log.warning("no data from the server for 12 s - reconnecting")
                conn.abort()
                return
            n = now_us()
            self._sp[n] = True
            conn.send_text(dumps({"t": "ping", "n": n}))
            peers = list(self.peers.values())
            if len(peers) > 40:                       # huge networks: rotate through the peers
                self._rot = (self._rot + 40) % len(peers)
                peers = (peers[self._rot:] + peers[:self._rot])[:40]
            for i, p in enumerate(peers, 1):
                self._pp[n + i] = p.ip
                conn.send_text(dumps({"t": "pp", "to": p.ip, "n": n + i}))
            self._purge(n)

    def _purge(self, now):
        for n in [k for k in self._sp if now - k > 6_000_000]:
            del self._sp[n]
            self.srv_lost.append(1)
        for n in [k for k in self._pp if now - k > 6_000_000]:
            ip = self._pp.pop(n)
            if ip in self.peers:
                self.peers[ip].lost()

    # ------------------------------------------------------------------ 1 Hz tick
    def _schedule_tick(self):
        self._ticker = self.loop.call_later(1.0, self._tick)

    def _tick(self):
        now = time.monotonic()
        tx0, rx0, t0 = self._last
        dt = max(0.001, now - t0)
        self.rate = ((self.tx_b - tx0) / dt, (self.rx_b - rx0) / dt)
        self._last = (self.tx_b, self.rx_b, now)
        self.on_change()
        self._schedule_tick()
