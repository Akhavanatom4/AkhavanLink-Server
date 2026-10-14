# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Local web UI server (127.0.0.1 only, random port, per-launch token)."""
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import parse_qs

from ..common.aio import HttpWsServer

log = logging.getLogger("akhavanlink.ui")

CTYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
          ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
          ".webmanifest": "application/manifest+json"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src ws://127.0.0.1:%(p)d ws://localhost:%(p)d; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


class UISession:
    def __init__(self, ui, conn):
        self.ui, self.conn = ui, conn

    def on_open(self, conn):
        self.ui.conns.add(self)

    def on_message(self, conn, op, data):
        try:
            m = json.loads(data)
        except ValueError:
            return
        if isinstance(m, dict):
            self.ui.on_cmd(self, m)

    def on_close(self, conn, exc):
        self.ui.conns.discard(self)

    def send(self, obj):
        self.conn.send_text(dumps(obj))


class UIServer:
    def __init__(self, app, web_dir, token):
        self.app, self.token = app, token
        self.conns = set()
        self.port = 0
        self.srv = None
        self._push_h = None
        self.files = {}
        root = Path(web_dir)
        for p in sorted(root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                self.files["/" if rel == "index.html" else "/" + rel] = (CTYPES.get(p.suffix.lower(), "application/octet-stream"), p.read_bytes())

    # ---- checks
    def _host_ok(self, req):
        return req["headers"].get("host", "") in ("127.0.0.1:%d" % self.port, "localhost:%d" % self.port)

    def _token_ok(self, req):
        return parse_qs(req["query"]).get("t", [""])[0] == self.token

    def _route(self, path, ctype, data):
        def handler(req):
            if not self._host_ok(req) or (path == "/" and not self._token_ok(req)):
                return 403, {}, b"forbidden"
            return 200, {"Content-Type": ctype, "Cache-Control": "no-store", "Content-Security-Policy": CSP % {"p": self.port},
                         "Referrer-Policy": "no-referrer"}, data
        return handler

    def _ws_factory(self, conn, req):
        origin = req["headers"].get("origin", "")
        if not self._host_ok(req) or not self._token_ok(req):
            return None
        if origin and origin not in ("http://127.0.0.1:%d" % self.port, "http://localhost:%d" % self.port):
            return None
        return UISession(self, conn)

    async def start(self, port=0):
        self.srv = HttpWsServer({"/ui": self._ws_factory}, {}, max_msg=1 << 20)
        await self.srv.start("127.0.0.1", port)
        self.port = self.srv.port
        self.srv.http_routes = {p: self._route(p, ct, d) for p, (ct, d) in self.files.items()}
        return self.port

    async def stop(self):
        if self.srv is not None:
            await self.srv.stop()

    # ---- push
    def broadcast(self, obj):
        if not self.conns:
            return
        text = dumps(obj)
        for s in tuple(self.conns):
            s.conn.send_text(text)

    def schedule_push(self):
        if self._push_h is None and self.conns:
            self._push_h = asyncio.get_running_loop().call_later(0.12, self._push)

    def _push(self):
        self._push_h = None
        if self.conns:
            self.broadcast(self.app.full_state())

    # ---- commands from the page
    def on_cmd(self, sess, m):
        c, app = m.get("cmd"), self.app
        try:
            if c == "hello":
                sess.send(app.full_state())
                sess.send({"t": "logs", "lines": list(app.logs)})
            elif c == "connect":
                app.engine.connect()
            elif c == "disconnect":
                asyncio.ensure_future(app.engine.disconnect())
            elif c == "save":
                asyncio.ensure_future(app.apply_config(m.get("cfg") or {}, quiet=bool(m.get("quiet"))))
            elif c == "test":
                asyncio.ensure_future(self._test(sess, m))
            elif c == "elevate":
                app.relaunch_admin()
            elif c == "driver":
                asyncio.ensure_future(app.install_driver())
            elif c == "openlog":
                app.open_log_dir()
            elif c == "quit":
                app.request_quit()
        except Exception:
            log.exception("command %s failed", c)

    async def _test(self, sess, m):
        res = await self.app.engine.test_server(str(m.get("url", "")), str(m.get("key", "")), str(m.get("proxy", "")))
        sess.send({"t": "testres", **res})
