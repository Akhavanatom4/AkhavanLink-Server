# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Tiny asyncio HTTP + WebSocket server and client built on asyncio.Protocol."""
import asyncio
import logging
import socket
import ssl
import time
from urllib.parse import urlsplit

from .. import VERSION
from . import ws

log = logging.getLogger("akhavanlink.aio")

MAX_HEAD = 16 * 1024
WRITE_LIMIT = 256 * 1024          # data frames are dropped (UDP-like) past this much queued output
UA = "AkhavanLink/%s (Created by Alireza Akhavan)" % VERSION
REASONS = {101: "Switching Protocols", 200: "OK", 204: "No Content", 400: "Bad Request", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 426: "Upgrade Required",
           431: "Request Header Fields Too Large", 500: "Internal Server Error"}


class HandshakeError(Exception):
    def __init__(self, status, detail=""):
        super().__init__(("HTTP %s %s" % (status, detail)).strip())
        self.status = status
        self.detail = detail


def parse_head(head):
    lines = head.decode("latin-1").split("\r\n")
    first = lines[0].split(" ", 2)
    if len(first) == 2:
        first.append("")
    if len(first) != 3:
        raise ValueError("bad start line")
    headers = {}
    for line in lines[1:]:
        k, sep, v = line.partition(":")
        if not sep:
            continue
        k = k.strip().lower()
        v = v.strip()
        headers[k] = "%s, %s" % (headers[k], v) if k in headers else v
    return first, headers


class WsConn(asyncio.Protocol):
    """One connection: plain HTTP first, then (after upgrade) a WebSocket."""

    def __init__(self, role, server=None, max_msg=70000):
        self.role = role                      # "server" | "client"
        self.server = server
        self.max_msg = max_msg
        self.mask = role == "client"
        self.transport = None
        self.phase = "http"                   # http -> ws
        self.head = bytearray()
        self.parser = None
        self.handler = None
        self.closing = False
        self.closed = False
        self.dropped = 0
        self.last_rx = time.monotonic()
        self.peername = ""
        self.request = None
        self.ready = None
        self.target = None
        self._key = None

    # ------------------------------------------------------------ protocol
    def connection_made(self, transport):
        self.transport = transport
        sock = transport.get_extra_info("socket")
        if sock is not None:
            for level, opt in ((socket.IPPROTO_TCP, socket.TCP_NODELAY), (socket.SOL_SOCKET, socket.SO_KEEPALIVE)):
                try:
                    sock.setsockopt(level, opt, 1)
                except (OSError, AttributeError):
                    pass
        pn = transport.get_extra_info("peername")
        if pn:
            self.peername = str(pn[0])
        if self.role == "server":
            if self.server is not None:
                self.server.conns.add(self)
        else:
            self._send_request()

    def data_received(self, data):
        self.last_rx = time.monotonic()
        if self.phase == "ws":
            self._feed(data)
            return
        self.head += data
        i = self.head.find(b"\r\n\r\n")
        if i < 0:
            if len(self.head) > MAX_HEAD:
                self._reply(431, b"Header too large")
            return
        head = bytes(self.head[:i])
        rest = bytes(self.head[i + 4:])
        self.head.clear()
        try:
            if self.role == "server":
                self._server_handshake(head, rest)
            else:
                self._client_handshake(head, rest)
        except ValueError:
            if self.role == "server":
                self._reply(400, b"Bad request")
            else:
                self._fail_ready(HandshakeError(0, "bad response"))
        except Exception:
            log.exception("handshake error")
            self.abort()

    def connection_lost(self, exc):
        was_closed = self.closed
        self.closed = True
        if self.server is not None:
            self.server.conns.discard(self)
        if self.ready is not None and not self.ready.done():
            self.ready.set_exception(HandshakeError(0, str(exc) if exc else "connection closed"))
        if self.handler is not None and self.phase == "ws" and not was_closed:
            try:
                self.handler.on_close(self, exc)
            except Exception:
                log.exception("on_close error")

    # ------------------------------------------------------------ server side
    def _server_handshake(self, head, rest):
        (method, target, _ver), hdr = parse_head(head)
        path, _, query = target.partition("?")
        req = {"method": method, "path": path, "query": query, "headers": hdr, "remote": self.peername}
        self.request = req
        srv = self.server
        upgrade = "websocket" in hdr.get("upgrade", "").lower() and "upgrade" in hdr.get("connection", "").lower()
        if upgrade and path in srv.ws_routes:
            key = hdr.get("sec-websocket-key", "")
            if method != "GET" or hdr.get("sec-websocket-version") != "13" or not key:
                return self._reply(400, b"Bad WebSocket handshake", {"Sec-WebSocket-Version": "13"})
            handler = srv.ws_routes[path](self, req)
            if handler is None:
                return self._reply(403, b"Forbidden")
            self._write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                         "Sec-WebSocket-Accept: %s\r\n\r\n" % ws.accept_key(key)).encode("ascii"))
            self.handler = handler
            self.phase = "ws"
            self.parser = ws.FrameParser(self.max_msg, require_mask=True)
            handler.on_open(self)
            if rest and not self.closed and not self.closing:
                self._feed(rest)
            return
        if upgrade:
            return self._reply(404, b"Not found")
        if method not in ("GET", "HEAD"):
            return self._reply(405, b"Method not allowed")
        route = srv.http_routes.get(path)
        if route is None:
            return self._reply(404, b"Not found")
        status, headers, body = route(req)
        self._reply(status, body, headers, head_only=(method == "HEAD"))

    def _reply(self, status, body=b"", headers=None, head_only=False):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h = {"Content-Length": str(len(body)), "Connection": "close", "X-Content-Type-Options": "nosniff",
             "Server": "AkhavanLink/%s (by Alireza Akhavan)" % VERSION}
        if headers:
            h.update(headers)
        h.setdefault("Content-Type", "text/plain; charset=utf-8")
        head = "HTTP/1.1 %d %s\r\n%s\r\n" % (status, REASONS.get(status, "OK"), "".join("%s: %s\r\n" % kv for kv in h.items()))
        self._write(head.encode("latin-1") + (b"" if head_only else body))
        self.closing = True
        self.transport.close()

    # ------------------------------------------------------------ client side
    def _send_request(self):
        host, port, path, extra = self.target
        self._key = ws.new_key()
        hostport = host if port in (80, 443) else "%s:%d" % (host, port)
        lines = ["GET %s HTTP/1.1" % path, "Host: %s" % hostport, "Upgrade: websocket", "Connection: Upgrade",
                 "Sec-WebSocket-Key: %s" % self._key, "Sec-WebSocket-Version: 13", "User-Agent: %s" % UA]
        for k, v in (extra or {}).items():
            lines.append("%s: %s" % (k, v))
        self.transport.write(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))

    def _client_handshake(self, head, rest):
        first, hdr = parse_head(head)
        try:
            status = int(first[1])
        except ValueError:
            status = 0
        if status != 101:
            return self._fail_ready(HandshakeError(status, first[2]))
        if hdr.get("sec-websocket-accept", "") != ws.accept_key(self._key):
            return self._fail_ready(HandshakeError(0, "bad accept key"))
        self.phase = "ws"
        self.parser = ws.FrameParser(self.max_msg, require_mask=False)
        if self.handler is not None:
            self.handler.on_open(self)
        if self.ready is not None and not self.ready.done():
            self.ready.set_result(True)
        if rest and not self.closed:
            self._feed(rest)

    def _fail_ready(self, exc):
        if self.ready is not None and not self.ready.done():
            self.ready.set_exception(exc)
        self.abort()

    # ------------------------------------------------------------ websocket
    def _feed(self, data):
        try:
            msgs = self.parser.feed(data)
        except ws.ProtocolError as e:
            self.close(e.code, e.reason)
            return
        for op, payload in msgs:
            if op == ws.OP_PING:
                self._write(ws.build_frame(ws.OP_PONG, payload, self.mask))
            elif op == ws.OP_PONG:
                continue
            elif op == ws.OP_CLOSE:
                if not self.closing:
                    self.closing = True
                    self._write(ws.build_frame(ws.OP_CLOSE, payload[:2], self.mask))
                self.transport.close()
                return
            else:
                try:
                    self.handler.on_message(self, op, payload)
                except Exception:
                    log.exception("on_message error")
                    self.close(1011, "internal error")
                    return
                if self.closed or self.closing:
                    return

    def _write(self, b):
        if not self.closed and self.transport is not None:
            self.transport.write(b)

    def send_text(self, s):
        if self.closed or self.closing or self.phase != "ws":
            return False
        self.transport.write(ws.build_frame(ws.OP_TEXT, s.encode("utf-8"), self.mask))
        return True

    def send_binary(self, payload):
        """Send one data packet; dropped (not queued) when the peer is congested."""
        if self.closed or self.closing or self.phase != "ws":
            return False
        if self.transport.get_write_buffer_size() > WRITE_LIMIT:
            self.dropped += 1
            return False
        self.transport.write(ws.build_frame(ws.OP_BINARY, payload, self.mask))
        return True

    def send_frame(self, frame):
        """Send an already-built (unmasked, server side) data frame with the same drop rule."""
        if self.closed or self.closing or self.phase != "ws":
            return False
        if self.transport.get_write_buffer_size() > WRITE_LIMIT:
            self.dropped += 1
            return False
        self.transport.write(frame)
        return True

    def close(self, code=1000, reason=""):
        if self.closed or self.closing:
            return
        self.closing = True
        if self.phase == "ws":
            self._write(ws.build_frame(ws.OP_CLOSE, ws.close_payload(code, reason), self.mask))
        if self.transport is not None:
            self.transport.close()

    def abort(self):
        self.closing = True
        if self.transport is not None:
            self.transport.abort()


class HttpWsServer:
    def __init__(self, ws_routes=None, http_routes=None, max_msg=70000):
        self.ws_routes = ws_routes or {}
        self.http_routes = http_routes or {}
        self.max_msg = max_msg
        self.conns = set()
        self.server = None

    def _factory(self):
        return WsConn("server", server=self, max_msg=self.max_msg)

    async def start(self, host, port, **kw):
        loop = asyncio.get_running_loop()
        self.server = await loop.create_server(self._factory, host, port, **kw)
        return self.server

    @property
    def port(self):
        return self.server.sockets[0].getsockname()[1]

    def sweep(self, ws_idle=45.0, http_idle=15.0):
        now = time.monotonic()
        for c in list(self.conns):
            idle = now - c.last_rx
            if (c.phase == "ws" and idle > ws_idle) or (c.phase != "ws" and idle > http_idle):
                c.abort()

    async def stop(self):
        if self.server is not None:
            self.server.close()
        for c in list(self.conns):
            c.close(1001, "server shutting down")
        await asyncio.sleep(0.05)


def _proxy_socket(proxy, host, port, timeout):
    u = urlsplit(proxy if "://" in proxy else "http://" + proxy)
    s = socket.create_connection((u.hostname, u.port or 8080), timeout)
    try:
        req = "CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\nUser-Agent: %s\r\n" % (host, port, host, port, UA)
        if u.username:
            import base64
            cred = base64.b64encode(("%s:%s" % (u.username, u.password or "")).encode()).decode()
            req += "Proxy-Authorization: Basic %s\r\n" % cred
        s.sendall((req + "\r\n").encode("latin-1"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk or len(buf) > 16384:
                raise HandshakeError(0, "proxy closed the connection")
            buf += chunk
        parts = buf.split(b"\r\n", 1)[0].decode("latin-1").split(" ", 2)
        if len(parts) < 2 or parts[1] != "200":
            raise HandshakeError(int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0, "proxy refused CONNECT")
        s.setblocking(False)
        return s
    except BaseException:
        s.close()
        raise


async def connect(url, handler, *, headers=None, proxy=None, timeout=12.0, max_msg=70000, ssl_context=None):
    """Open a WebSocket client connection; returns a ready WsConn."""
    u = urlsplit(url)
    scheme = u.scheme.lower()
    if scheme not in ("ws", "wss", "http", "https"):
        raise ValueError("unsupported scheme: %s" % scheme)
    tls = scheme in ("wss", "https")
    host = u.hostname
    if not host:
        raise ValueError("no host in url")
    port = u.port or (443 if tls else 80)
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    loop = asyncio.get_running_loop()
    conn = WsConn("client", max_msg=max_msg)
    conn.handler = handler
    conn.ready = loop.create_future()
    conn.target = (host, port, path, headers)
    ctx = None
    if tls:
        ctx = ssl_context or ssl.create_default_context()
        try:
            ctx.set_alpn_protocols(["http/1.1"])
        except (NotImplementedError, AttributeError):
            pass
    try:
        sni = host if tls else None
        if proxy:
            sock = await loop.run_in_executor(None, _proxy_socket, proxy, host, port, timeout)
            await asyncio.wait_for(loop.create_connection(lambda: conn, sock=sock, ssl=ctx, server_hostname=sni), timeout)
        else:
            await asyncio.wait_for(loop.create_connection(lambda: conn, host, port, ssl=ctx, server_hostname=sni,
                                                          happy_eyeballs_delay=0.25), timeout)
        await asyncio.wait_for(conn.ready, timeout)
    except BaseException:
        conn.abort()
        raise
    return conn
