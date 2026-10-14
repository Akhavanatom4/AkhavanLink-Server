# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Relay hub: virtual networks, IP allocation and packet forwarding."""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import struct
import time
import unicodedata
from pathlib import Path

from .. import APP_NAME, CREATOR, CREATOR_FA, VERSION, PROTO, DEFAULT_CIDR
from ..common import ws

log = logging.getLogger("akhavanlink.hub")
_UNPACK_II = struct.Struct(">II").unpack_from
_BAD_CODEPOINTS = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F, 0x061C}


def jdump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def ip2s(ip):
    return socket.inet_ntoa(struct.pack(">I", ip))


def s2ip(s):
    try:
        return int(ipaddress.IPv4Address(s))
    except (ValueError, TypeError):
        return None


def clean_text(s, maxlen):
    """Strip control / bidi-override characters (keeps ZWNJ for Persian) and collapse spaces."""
    if not isinstance(s, str):
        return ""
    out = []
    for ch in s:
        if ord(ch) in _BAD_CODEPOINTS or unicodedata.category(ch) in ("Cc", "Cs", "Co", "Cn", "Zl", "Zp"):
            continue
        out.append(ch)
    return " ".join("".join(out).split())[:maxlen]


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    def __init__(self, cidr=DEFAULT_CIDR, access_key="", net_ttl=6 * 3600, resv_ttl=12 * 3600,
                 max_per_net=0, max_nets=0, mtu=1400, max_msg=70000):
        self.cidr = cidr
        self.access_key = access_key
        self.net_ttl = net_ttl
        self.resv_ttl = resv_ttl
        self.max_per_net = max_per_net     # 0 = unlimited players
        self.max_nets = max_nets           # 0 = unlimited networks
        self.mtu = mtu
        self.max_msg = max_msg

    @classmethod
    def from_env(cls):
        e = os.environ
        return cls(cidr=e.get("VNET_CIDR", DEFAULT_CIDR), access_key=e.get("ACCESS_KEY", ""),
                   net_ttl=_env_int("NETWORK_TTL_HOURS", 6) * 3600, resv_ttl=_env_int("IP_RESERVE_HOURS", 12) * 3600,
                   max_per_net=_env_int("MAX_PLAYERS_PER_NETWORK", 0), max_nets=_env_int("MAX_NETWORKS", 0),
                   mtu=_env_int("VNET_MTU", 1400))


class PoolFull(Exception):
    pass


class Network:
    def __init__(self, hub, name, pwh):
        self.hub = hub
        self.name = name
        self.pwh = pwh
        self.members = {}                 # ip(int) -> Session (online)
        self.resv = {}                    # id-hash -> [ip, last_seen]
        self.owner = {}                   # ip -> id-hash
        self.empty_since = time.monotonic()

    def alloc(self):
        ip, last = self.hub.first, self.hub.last
        while ip <= last:
            if ip not in self.owner:
                return ip
            ip += 1
        return None

    def add(self, sess, idh, want):
        now = time.monotonic()
        ent = self.resv.get(idh)
        if ent is None:
            ip = None
            if want and self.hub.first <= want <= self.hub.last and want not in self.owner:
                ip = want
            if ip is None:
                ip = self.alloc()
            if ip is None:
                raise PoolFull()
            ent = self.resv[idh] = [ip, now]
            self.owner[ip] = idh
        ip = ent[0]
        ent[1] = now
        old = self.members.get(ip)
        limit = self.hub.cfg.max_per_net
        if limit and old is None and len(self.members) >= limit:
            raise PoolFull()
        self.members[ip] = sess
        return ip, old

    def broadcast_text(self, text, exclude=None):
        for s in tuple(self.members.values()):
            if s is not exclude:
                s.conn.send_text(text)

    def expire(self, now, ttl):
        for idh, (ip, seen) in list(self.resv.items()):
            if ip not in self.members and now - seen > ttl:
                del self.resv[idh]
                self.owner.pop(ip, None)


class Session:
    """Handler for one client connection."""

    def __init__(self, hub, conn, req):
        self.hub = hub
        self.conn = conn
        self.net = None
        self.ip = 0
        self.ip_s = ""
        self.nick = ""
        self.idh = None
        self.kicked = False
        fwd = req["headers"].get("x-forwarded-for", "").split(",")[0].strip()
        self.remote = fwd or conn.peername

    # --- websocket callbacks
    def on_open(self, conn):
        conn.send_text(jdump({"t": "hello", "app": APP_NAME, "ver": VERSION, "proto": PROTO, "creator": CREATOR,
                              "time": int(time.time() * 1000)}))
        asyncio.get_running_loop().call_later(15, self._join_timeout)

    def _join_timeout(self):
        if self.net is None:
            self.conn.close(1008, "join timeout")

    def on_message(self, conn, op, data):
        if self.net is None:
            if op != ws.OP_TEXT:
                return
            try:
                m = json.loads(data)
            except ValueError:
                return
            if not isinstance(m, dict):
                return
            t = m.get("t")
            if t == "ping":
                conn.send_text(jdump({"t": "pong", "n": _num(m.get("n"))}))
            elif t == "join":
                self._join(m)
            return
        if op == ws.OP_BINARY:
            self._route(data)
        else:
            self._control(data)

    def on_close(self, conn, exc):
        net = self.net
        if net is None or net.members.get(self.ip) is not self:
            return
        del net.members[self.ip]
        ent = net.resv.get(self.idh)
        if ent:
            ent[1] = time.monotonic()
        if not net.members:
            net.empty_since = time.monotonic()
        net.broadcast_text(jdump({"t": "peer-", "ip": self.ip_s}))
        log.info("[%s] %s left (%s) - %d online", net.name, self.nick, self.ip_s, len(net.members))

    # --- join
    def _fail(self, code, msg, slow=False):
        self.conn.send_text(jdump({"t": "error", "code": code, "msg": msg}))
        if slow:
            asyncio.get_running_loop().call_later(0.8, self.conn.close, 1008, code)
        else:
            self.conn.close(1008, code)

    def _join(self, m):
        hub = self.hub
        cfg = hub.cfg
        try:
            v = int(m.get("v", 0))
        except (TypeError, ValueError):
            v = 0
        if v != PROTO:
            return self._fail("bad_version", "protocol mismatch (client %s, server %s) - update the app or the server" % (v, PROTO))
        if cfg.access_key and not hmac.compare_digest(str(m.get("key", "")).encode(), cfg.access_key.encode()):
            return self._fail("bad_key", "wrong server access key", slow=True)
        name = clean_text(m.get("net"), 32)
        if not name:
            return self._fail("bad_network", "network name is empty")
        pw = str(m.get("pw", ""))[:64]
        cid = str(m.get("id", ""))
        if not 16 <= len(cid) <= 128:
            return self._fail("bad_id", "invalid client id")
        nick = clean_text(m.get("nick"), 24) or "Player"
        net, err = hub.get_network(name, pw)
        if err:
            return self._fail(err, err.replace("_", " "), slow=(err == "bad_password"))
        idh = hashlib.sha256(cid.encode("utf-8")).digest()
        try:
            ip, old = net.add(self, idh, s2ip(m.get("want")))
        except PoolFull:
            return self._fail("network_full", "this network has no free addresses left")
        if old is not None and old is not self:
            old.kicked = True
            old.conn.close(4001, "replaced by a newer connection")
        self.net, self.ip, self.ip_s, self.nick, self.idh = net, ip, ip2s(ip), nick, idh
        hub.joins += 1
        peers = [{"ip": s.ip_s, "nick": s.nick} for s in net.members.values() if s is not self]
        self.conn.send_text(jdump({
            "t": "welcome", "ip": self.ip_s, "prefix": hub.prefix, "mask": hub.mask_s, "mtu": cfg.mtu,
            "net": net.name, "nick": nick, "peers": peers, "online": len(net.members),
            "server": {"ver": VERSION, "creator": CREATOR}}))
        net.broadcast_text(jdump({"t": "peer+", "p": {"ip": self.ip_s, "nick": nick}}), exclude=self)
        log.info("[%s] %s joined as %s from %s - %d online", net.name, nick, self.ip_s, self.remote, len(net.members))

    # --- data plane
    def _route(self, data):
        if len(data) < 20 or (data[0] >> 4) != 4:
            return
        hub = self.hub
        src, dst = _UNPACK_II(data, 12)
        if src != self.ip:
            hub.spoofed += 1
            return
        frame = ws.build_frame(ws.OP_BINARY, data)
        members = self.net.members
        if dst == 0xFFFFFFFF or dst == hub.bcast or (dst >> 28) == 0xE:      # broadcast / multicast -> flood
            for s in tuple(members.values()):
                if s is not self:
                    s.conn.send_frame(frame)
        else:
            s = members.get(dst)
            if s is not None:
                s.conn.send_frame(frame)
        hub.pkts += 1
        hub.nbytes += len(data)

    # --- control plane
    def _control(self, data):
        try:
            m = json.loads(data)
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        t = m.get("t")
        if t == "ping":
            self.conn.send_text(jdump({"t": "pong", "n": _num(m.get("n"))}))
        elif t in ("pp", "pr"):
            peer = self.net.members.get(s2ip(m.get("to")))
            if peer is not None and peer is not self:
                peer.conn.send_text(jdump({"t": t, "from": self.ip_s, "n": _num(m.get("n"))}))
        elif t == "nick":
            nick = clean_text(m.get("nick"), 24)
            if nick and nick != self.nick:
                self.nick = nick
                self.net.broadcast_text(jdump({"t": "peer~", "p": {"ip": self.ip_s, "nick": nick}}), exclude=self)
        elif t == "bye":
            self.conn.close(1000, "bye")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


class Hub:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        net = ipaddress.ip_network(self.cfg.cidr, strict=True)
        if net.version != 4 or not 8 <= net.prefixlen <= 28:
            raise ValueError("VNET_CIDR must be an IPv4 network between /8 and /28, e.g. 10.77.0.0/16")
        self.prefix = net.prefixlen
        self.mask_s = str(net.netmask)
        self.base = int(net.network_address)
        self.bcast = int(net.broadcast_address)
        self.first = self.base + 2          # .1 is reserved
        self.last = self.bcast - 1
        self.nets = {}
        self.started = time.time()
        self.joins = self.pkts = self.nbytes = self.spoofed = 0
        self._landing = None

    def ws_factory(self, conn, req):
        return Session(self, conn, req)

    def get_network(self, name, pw):
        key = name.casefold()
        pwh = hashlib.sha256(("%s\x00%s" % (key, pw)).encode("utf-8")).digest()
        net = self.nets.get(key)
        if net is None:
            if self.cfg.max_nets and len(self.nets) >= self.cfg.max_nets:
                return None, "too_many_networks"
            net = self.nets[key] = Network(self, name, pwh)
        elif not hmac.compare_digest(net.pwh, pwh):
            return None, "bad_password"
        return net, None

    def stats(self):
        return {"app": APP_NAME, "version": VERSION, "creator": CREATOR, "uptime": int(time.time() - self.started),
                "online": sum(len(n.members) for n in self.nets.values()),
                "networks": sum(1 for n in self.nets.values() if n.members), "packets": self.pkts}

    # --- plain HTTP routes
    def http_routes(self):
        def landing(req):
            if self._landing is None:
                html = Path(__file__).with_name("landing.html").read_text(encoding="utf-8")
                for k, v in (("__VERSION__", VERSION), ("__CREATOR_FA__", CREATOR_FA), ("__CREATOR__", CREATOR),
                             ("__PROTO__", str(PROTO))):
                    html = html.replace(k, v)
                self._landing = html.encode("utf-8")
            return 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}, self._landing

        def health(req):
            return 200, {"Cache-Control": "no-store"}, b"ok"

        def stats(req):
            return 200, {"Content-Type": "application/json", "Cache-Control": "no-store"}, jdump(self.stats()).encode()

        def need_ws(req):
            return 426, {"Upgrade": "websocket"}, b"AkhavanLink WebSocket endpoint - open it with the AkhavanLink app."

        return {"/": landing, "/index.html": landing, "/healthz": health, "/api/stats": stats, "/ws": need_ws}

    async def janitor(self, server):
        while True:
            await asyncio.sleep(15)
            try:
                server.sweep()
                now = time.monotonic()
                for key, net in list(self.nets.items()):
                    net.expire(now, self.cfg.resv_ttl)
                    if not net.members and now - net.empty_since > self.cfg.net_ttl:
                        del self.nets[key]
            except Exception:
                log.exception("janitor error")
