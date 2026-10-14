# AkhavanLink — Created by Alireza Akhavan
"""Hub rules, local-UI security, Wintun download logic and the portable packager."""
import asyncio
import hashlib
import http.server
import io
import json
import socket
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from akhavanlink.common import aio  # noqa: E402
from akhavanlink.client import winnet  # noqa: E402
from akhavanlink.client.tun import TunError  # noqa: E402
from akhavanlink.client.uiserver import UIServer  # noqa: E402
from akhavanlink.server.hub import Config, Hub, clean_text  # noqa: E402


class Collector:
    def __init__(self):
        self.q = asyncio.Queue()
        self.closed = asyncio.Event()

    def on_open(self, c): pass
    def on_close(self, c, e): self.closed.set()

    def on_message(self, c, op, d):
        if op == 1:
            self.q.put_nowait(json.loads(d))


async def join(url, cid, net="N", pw="", key="", want="", nick="x"):
    h = Collector()
    c = await aio.connect(url, h)
    await h.q.get()
    c.send_text(json.dumps({"t": "join", "v": 1, "net": net, "pw": pw, "id": cid.ljust(32, "0"), "nick": nick, "key": key, "want": want}))
    return c, h, await asyncio.wait_for(h.q.get(), 3)


class HubRules(unittest.IsolatedAsyncioTestCase):
    async def start(self, **cfg):
        self.hub = Hub(Config(**cfg))
        self.srv = aio.HttpWsServer({"/ws": self.hub.ws_factory}, self.hub.http_routes())
        await self.srv.start("127.0.0.1", 0)
        return "ws://127.0.0.1:%d/ws" % self.srv.port

    async def asyncTearDown(self):
        if hasattr(self, "srv"):
            await self.srv.stop()

    async def test_ip_stable_after_leaving_and_preferred_ip(self):
        url = await self.start()
        c1, _, w1 = await join(url, "alice")
        c2, _, w2 = await join(url, "bob")
        self.assertEqual((w1["ip"], w2["ip"]), ("10.77.0.2", "10.77.0.3"))
        c1.close(); await asyncio.sleep(0.1)
        c3, _, w3 = await join(url, "carol")                       # alice is offline but her address stays reserved
        self.assertEqual(w3["ip"], "10.77.0.4")
        c1b, _, w1b = await join(url, "alice")
        self.assertEqual(w1b["ip"], "10.77.0.2")
        c4, _, w4 = await join(url, "dave", want="10.77.0.50")      # a free preferred address is honoured ...
        self.assertEqual(w4["ip"], "10.77.0.50")
        c5, _, w5 = await join(url, "erin", want="10.77.0.2")       # ... a taken one is not
        self.assertEqual(w5["ip"], "10.77.0.5")

    async def test_access_key_and_player_limit(self):
        url = await self.start(access_key="s3cret", max_per_net=2)
        _, _, w = await join(url, "a1", key="wrong")
        self.assertEqual(w["code"], "bad_key")
        _, _, w = await join(url, "a2", key="s3cret")
        self.assertEqual(w["t"], "welcome")
        _, _, w = await join(url, "a3", key="s3cret")
        self.assertEqual(w["t"], "welcome")
        _, _, w = await join(url, "a4", key="s3cret")
        self.assertEqual(w["code"], "network_full")

    async def test_unlimited_by_default_and_isolated_networks(self):
        url = await self.start()
        ips = set()
        for i in range(40):
            _, _, w = await join(url, "u%03d" % i, net="Big")
            ips.add(w["ip"])
        self.assertEqual(len(ips), 40)
        _, _, w = await join(url, "u000", net="Other")               # same id, other network: independent address pool
        self.assertEqual(w["ip"], "10.77.0.2")
        _, _, w = await join(url, "zz", net="Big", pw="x")
        self.assertEqual(w["code"], "bad_password")

    async def test_http_endpoints(self):
        url = await self.start()
        port = self.srv.port
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"); await w.drain()
        data = await r.read(100000)
        self.assertIn(b"200 OK", data)
        self.assertIn("علیرضا اخوان".encode(), data)               # creator credit is on the landing page
        self.assertIn(b"Alireza Akhavan", data)
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(b"GET /nope HTTP/1.1\r\nHost: x\r\n\r\n"); await w.drain()
        self.assertIn(b"404", await r.read(1000))
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(b"GET /ws HTTP/1.1\r\nHost: x\r\n\r\n"); await w.drain()
        self.assertIn(b"426", await r.read(1000))
        r, w = await asyncio.open_connection("127.0.0.1", port)      # garbage must not kill the server
        w.write(b"\x16\x03\x01garbage\r\n\r\n"); await w.drain()
        await r.read(1000)
        _, _, wl = await join(url, "after-garbage")
        self.assertEqual(wl["t"], "welcome")

    def test_clean_text_keeps_persian_zwnj_and_drops_controls(self):
        self.assertEqual(clean_text("می\u200cخوام  \u202e\x00علی", 24), "می\u200cخوام علی")
        self.assertEqual(clean_text("x" * 99, 5), "xxxxx")


class UISecurity(unittest.IsolatedAsyncioTestCase):
    async def test_token_host_origin(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "index.html").write_text("<p>hi</p>")
            (Path(d) / "app.js").write_text("1")
            ui = UIServer(SimpleNamespace(), d, "tok123")
            port = await ui.start()
            async def get(path, host=None):
                r, w = await asyncio.open_connection("127.0.0.1", port)
                w.write(("GET %s HTTP/1.1\r\nHost: %s\r\n\r\n" % (path, host or "127.0.0.1:%d" % port)).encode()); await w.drain()
                data = await r.read(10000); w.close()
                return data.split(b"\r\n", 1)[0].decode(), data
            self.assertIn("200", (await get("/?t=tok123"))[0])
            self.assertIn("403", (await get("/"))[0])
            self.assertIn("403", (await get("/?t=wrong"))[0])
            self.assertIn("403", (await get("/?t=tok123", host="evil.example:%d" % port))[0])     # DNS-rebinding style request
            line, raw = await get("/app.js")
            self.assertIn("200", line)
            self.assertIn(b"text/javascript", raw)
            self.assertIn(b"Content-Security-Policy", raw)
            # websocket: right token ok, wrong token / foreign origin refused
            h = Collector()
            c = await aio.connect("ws://127.0.0.1:%d/ui?t=tok123" % port, h)
            c.close()
            for url, hdr in (("ws://127.0.0.1:%d/ui?t=nope" % port, None), ("ws://127.0.0.1:%d/ui?t=tok123" % port, {"Origin": "http://evil.example"})):
                with self.assertRaises(aio.HandshakeError):
                    await aio.connect(url, Collector(), headers=hdr)
            await ui.stop()


class DriverDownload(unittest.TestCase):
    def setUp(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for a in ("amd64", "x86", "arm64", "arm"):
                z.writestr("wintun/bin/%s/wintun.dll" % a, b"MZ-fake-dll-" + a.encode())
        self.zip = buf.getvalue()

        data = self.zip

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = data if self.path == "/w.zip" else b"not a zip"
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *a): pass
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d/" % self.httpd.server_port

    def tearDown(self):
        self.httpd.shutdown()

    def test_download_verify_extract(self):
        with tempfile.TemporaryDirectory() as d:
            p = winnet.download_wintun(d, self.url + "w.zip", hashlib.sha256(self.zip).hexdigest())
            self.assertTrue(p.read_bytes().startswith(b"MZ-fake-dll-"))
            self.assertEqual(winnet.find_wintun([d]), p)
            with self.assertRaises(TunError) as e:
                winnet.download_wintun(d, self.url + "w.zip", "0" * 64)
            self.assertEqual(e.exception.code, "driver_hash")
            with self.assertRaises(TunError) as e:
                winnet.download_wintun(d, self.url + "bad", None)
            self.assertEqual(e.exception.code, "driver_download")

    def test_pure_helpers(self):
        self.assertEqual(winnet.prefix_to_mask(16), "255.255.0.0")
        self.assertEqual(winnet.prefix_to_mask(24), "255.255.255.0")
        args = winnet.browser_args("msedge.exe", "http://127.0.0.1:1/?t=x", "C:/p")
        self.assertIn("--app=http://127.0.0.1:1/?t=x", args)
        self.assertTrue(any(a.startswith("--user-data-dir=") for a in args))
        self.assertTrue(winnet.browser_candidates({"ProgramFiles": "C:\\PF"})[0].endswith("msedge.exe"))


class Packager(unittest.TestCase):
    def test_assemble_and_zip(self):
        import make_portable as mp
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            app = d / "AkhavanLink"; (app / "_internal").mkdir(parents=True)
            (app / "AkhavanLink.exe").write_bytes(b"MZ"); (app / "_internal" / "x.dll").write_bytes(b"1")
            dll = d / "wintun.dll"; dll.write_bytes(b"DLL")
            folder = mp.assemble(app, d / "out", "my-app.deplexo.app", dll, "verified", ROOT / "scripts" / "portable-README-FA.txt",
                                 {"network": "", "password": "pw123", "accessKey": "k"})
            cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["serverUrl"], "my-app.deplexo.app")
            self.assertEqual((cfg["network"], cfg["password"], cfg["accessKey"]), ("AkhavanLAN", "pw123", "k"))
            z = mp.zip_folder(folder, d / "x.zip")
            names = zipfile.ZipFile(z).namelist()
            for n in ("AkhavanLink-Portable/AkhavanLink.exe", "AkhavanLink-Portable/wintun.dll", "AkhavanLink-Portable/config.json",
                      "AkhavanLink-Portable/README-FA.txt", "AkhavanLink-Portable/_internal/x.dll", "AkhavanLink-Portable/PACKAGE-INFO.txt"):
                self.assertIn(n, names)
            self.assertIn("علیرضا اخوان", (folder / "README-FA.txt").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
