# AkhavanLink — Created by Alireza Akhavan
"""End-to-end tests: real relay server + real client engines (in-memory adapters)."""
import asyncio
import threading
import unittest

from akhavanlink.common import ws
from akhavanlink.common.aio import HttpWsServer
from akhavanlink.server.hub import Config, Hub
from akhavanlink.client.config import ConfigStore, normalize_server_url
from akhavanlink.client.engine import Engine
from akhavanlink.client.tun import MemTun, make_ipv4


class CodecTests(unittest.TestCase):
    def test_roundtrip_all_sizes(self):
        for mask in (False, True):
            for n in (0, 1, 125, 126, 127, 65535, 65536, 70000):
                data = bytes(i & 255 for i in range(n))
                p = ws.FrameParser(1 << 20, require_mask=mask)
                f = ws.build_frame(ws.OP_BINARY, data, mask)
                got = []
                for i in range(0, len(f), 7):           # feed in tiny chunks
                    got += p.feed(f[i:i + 7])
                self.assertEqual(got, [(ws.OP_BINARY, data)])

    def test_unmasked_client_frame_rejected(self):
        with self.assertRaises(ws.ProtocolError):
            ws.FrameParser(100, require_mask=True).feed(ws.build_frame(ws.OP_TEXT, b"x", False))

    def test_fragmentation_and_control_interleave(self):
        p = ws.FrameParser(1000)
        f1 = bytes([0x01, 3]) + b"abc"          # text, FIN=0
        ping = bytes([0x89, 1]) + b"p"
        f2 = bytes([0x80, 2]) + b"de"           # continuation, FIN=1
        self.assertEqual(p.feed(f1 + ping + f2), [(ws.OP_PING, b"p"), (ws.OP_TEXT, b"abcde")])

    def test_too_big(self):
        with self.assertRaises(ws.ProtocolError):
            ws.FrameParser(10).feed(ws.build_frame(ws.OP_BINARY, b"x" * 11))

    def test_accept_key_rfc_sample(self):
        self.assertEqual(ws.accept_key("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


class ConfigTests(unittest.TestCase):
    def test_normalize(self):
        n = normalize_server_url
        self.assertEqual(n("my-app.deplexo.app"), "wss://my-app.deplexo.app/ws")
        self.assertEqual(n("https://my-app.deplexo.app/"), "wss://my-app.deplexo.app/ws")
        self.assertEqual(n("wss://x.y/custom"), "wss://x.y/custom")
        self.assertEqual(n("192.168.1.5:8080"), "ws://192.168.1.5:8080/ws")
        self.assertEqual(n("localhost:8080"), "ws://localhost:8080/ws")
        self.assertEqual(n("example.com:443"), "wss://example.com/ws".replace("example.com", "example.com:443"))
        self.assertEqual(n("http://10.0.0.2:9000"), "ws://10.0.0.2:9000/ws")
        for bad in ("", "   ", "ftp://x.y", "wss://"):
            with self.assertRaises(ValueError):
                n(bad)

    def test_update_validation(self):
        c = ConfigStore(None)
        self.assertEqual(c.update({"mtu": 99999, "lang": "xx", "fx": "lite", "bogus": 1, "clientId": "hack"}), {"fx"})
        self.assertEqual(c.data["mtu"], 1400)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hub = Hub(Config())
        self.srv = HttpWsServer({"/ws": self.hub.ws_factory}, self.hub.http_routes())
        await self.srv.start("127.0.0.1", 0)
        self.url = "ws://127.0.0.1:%d/ws" % self.srv.port
        self.tuns = {}
        self.engines = []

    async def asyncTearDown(self):
        for e in self.engines:
            await e.shutdown()
        await self.srv.stop()

    def make(self, nick, **over):
        cfg = ConfigStore(None)
        cfg.update({"serverUrl": self.url, "network": "T", "nickname": nick, "firewall": False, **over})
        cfg.update({"clientId": (nick * 20)[:32]}, internal=True)

        def factory(spec):
            t = MemTun(spec)
            self.tuns[nick] = t
            return t
        e = Engine(cfg, asyncio.get_running_loop(), factory)
        e.start()
        self.engines.append(e)
        return e

    async def until(self, cond, timeout=6.0):
        end = asyncio.get_running_loop().time() + timeout
        while not cond():
            if asyncio.get_running_loop().time() > end:
                self.fail("timeout waiting for condition")
            await asyncio.sleep(0.02)

    async def two(self):
        a, b = self.make("Ali"), self.make("Sara")
        a.connect()
        await self.until(lambda: a.status == "online")
        b.connect()
        await self.until(lambda: b.status == "online" and a.peers)
        return a, b

    async def test_ips_and_peers(self):
        a, b = await self.two()
        self.assertEqual((a.ip, b.ip, a.prefix), ("10.77.0.2", "10.77.0.3", 16))
        self.assertEqual([p.nick for p in a.peers.values()], ["Sara"])
        self.assertEqual([p.nick for p in b.peers.values()], ["Ali"])
        self.assertEqual(self.tuns["Ali"].spec.ip, "10.77.0.2")

    async def test_packets_unicast_broadcast_multicast(self):
        a, b = await self.two()
        pkts = [make_ipv4("10.77.0.2", "10.77.0.3"), make_ipv4("10.77.0.2", "10.77.255.255", 100),
                make_ipv4("10.77.0.2", "255.255.255.255"), make_ipv4("10.77.0.2", "224.0.2.60", 1200)]
        for p in pkts:                                   # from a foreign thread, like the real adapter thread
            threading.Thread(target=self.tuns["Ali"].inject, args=(p,)).start()
        await self.until(lambda: len(self.tuns["Sara"].written) == 4)
        self.assertEqual(sorted(self.tuns["Sara"].written), sorted(pkts))
        self.assertEqual(self.tuns["Ali"].written, [])
        self.assertGreater(a.tx_p, 3)
        self.assertGreater(b.rx_p, 3)

    async def test_non_ipv4_and_spoofed_are_ignored(self):
        a, b = await self.two()
        self.tuns["Ali"].inject(b"\x60" + bytes(60))                         # IPv6
        self.tuns["Ali"].inject(make_ipv4("10.77.0.99", "10.77.0.3"))        # wrong source
        self.tuns["Ali"].inject(make_ipv4("10.77.0.2", "10.77.0.3"))
        await self.until(lambda: len(self.tuns["Sara"].written) >= 1)
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.tuns["Sara"].written), 1)

    async def test_pings(self):
        a, b = await self.two()
        await self.until(lambda: a.srv_rtt is not None and all(p.rtt is not None for p in a.peers.values()), 8)
        snap = a.snapshot()
        self.assertEqual(snap["status"], "online")
        self.assertLess(snap["ping"]["server"], 100)
        self.assertLess(snap["peers"][0]["rtt"], 100)

    async def test_reconnect_keeps_ip_and_adapter(self):
        a, b = await self.two()
        tun, ip = self.tuns["Sara"], b.ip
        b._conn.abort()
        await self.until(lambda: b.status == "reconnecting")
        await self.until(lambda: b.status == "online", 10)
        self.assertEqual(b.ip, ip)
        self.assertIs(b.tun, tun)
        self.assertFalse(tun.closed)
        self.tuns["Ali"].inject(make_ipv4("10.77.0.2", ip))
        await self.until(lambda: len(tun.written) == 1)

    async def test_peer_leave_event(self):
        events = []
        a, b = self.make("Ali"), self.make("Sara")
        a.on_event = events.append
        a.connect()
        await self.until(lambda: a.status == "online")
        b.connect()
        await self.until(lambda: a.peers)
        await b.disconnect()
        await self.until(lambda: not a.peers)
        self.assertEqual([e["ev"] for e in events], ["peer_join", "peer_leave"])
        self.assertTrue(self.tuns["Sara"].closed)
        self.assertEqual(b.status, "idle")

    async def test_wrong_password_is_fatal(self):
        a = self.make("Ali", password="secret")
        a.connect()
        await self.until(lambda: a.status == "online")
        c = self.make("Eve", password="nope")
        c.connect()
        await self.until(lambda: c.status == "error")
        self.assertEqual(c.err["code"], "bad_password")
        self.assertIsNone(c.tun)

    async def test_no_server_configured(self):
        e = self.make("Ali", serverUrl="")
        e.connect()
        await self.until(lambda: e.status == "error")
        self.assertEqual(e.err["code"], "no_server")

    async def test_unreachable_server_gives_up(self):
        e = self.make("Ali", serverUrl="ws://127.0.0.1:1/ws")
        e.connect()
        await self.until(lambda: e.status == "error", 20)
        self.assertEqual(e.err["code"], "refused")

    async def test_server_test_function(self):
        e = self.make("Ali")
        r = await e.test_server(self.url)
        self.assertTrue(r["ok"] and r["proto_ok"] and r["ms"] < 100, r)
        r = await e.test_server("ws://127.0.0.1:1/ws")
        self.assertFalse(r["ok"])
        r = await e.test_server("http://127.0.0.1:%d/healthz" % self.srv.port)   # a normal web page, not our ws endpoint
        self.assertFalse(r["ok"])

    async def test_many_players_unique_ips(self):
        engines = [self.make("P%02d" % i) for i in range(25)]
        for e in engines:
            e.connect()
        await self.until(lambda: all(e.status == "online" for e in engines), 15)
        self.assertEqual(len({e.ip for e in engines}), 25)
        await self.until(lambda: all(len(e.peers) == 24 for e in engines), 10)


if __name__ == "__main__":
    unittest.main()
