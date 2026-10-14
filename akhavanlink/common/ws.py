# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""RFC 6455 WebSocket frame codec. Pure standard library."""
import base64
import hashlib
import os
import struct

GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BINARY = 0x0, 0x1, 0x2
OP_CLOSE, OP_PING, OP_PONG = 0x8, 0x9, 0xA


class ProtocolError(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def accept_key(key):
    return base64.b64encode(hashlib.sha1(key.encode("ascii") + GUID).digest()).decode("ascii")


def new_key():
    return base64.b64encode(os.urandom(16)).decode("ascii")


def xor_mask(data, key):
    n = len(data)
    if n == 0:
        return b""
    k = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(k, "big")).to_bytes(n, "big")


def build_frame(op, payload=b"", mask=False):
    n = len(payload)
    mbit = 0x80 if mask else 0
    if n < 126:
        head = bytes((0x80 | op, mbit | n))
    elif n < 65536:
        head = struct.pack(">BBH", 0x80 | op, mbit | 126, n)
    else:
        head = struct.pack(">BBQ", 0x80 | op, mbit | 127, n)
    if mask:
        key = os.urandom(4)
        return head + key + xor_mask(payload, key)
    return head + payload


def close_payload(code=1000, reason=""):
    return struct.pack(">H", code) + reason.encode("utf-8")[:100]


class FrameParser:
    """Incremental parser: feed(bytes) -> [(opcode, payload)] with messages reassembled."""

    def __init__(self, max_size=1 << 20, require_mask=False):
        self.buf = bytearray()
        self.max_size = max_size
        self.require_mask = require_mask
        self._fop = None
        self._frag = bytearray()

    def feed(self, data):
        buf = self.buf
        buf += data
        out = []
        pos = 0
        n = len(buf)
        while n - pos >= 2:
            b0 = buf[pos]
            b1 = buf[pos + 1]
            op = b0 & 0x0F
            fin = b0 & 0x80
            masked = b1 & 0x80
            ln = b1 & 0x7F
            hdr = 2
            if ln == 126:
                if n - pos < 4:
                    break
                ln = (buf[pos + 2] << 8) | buf[pos + 3]
                hdr = 4
            elif ln == 127:
                if n - pos < 10:
                    break
                ln = int.from_bytes(buf[pos + 2:pos + 10], "big")
                hdr = 10
            if b0 & 0x70:
                raise ProtocolError(1002, "reserved bits set")
            if op >= 8 and (ln > 125 or not fin):
                raise ProtocolError(1002, "bad control frame")
            if ln > self.max_size:
                raise ProtocolError(1009, "message too big")
            if self.require_mask and not masked:
                raise ProtocolError(1002, "client frames must be masked")
            total = hdr + (4 if masked else 0) + ln
            if n - pos < total:
                break
            p0 = pos + hdr
            if masked:
                key = bytes(buf[p0:p0 + 4])
                payload = xor_mask(bytes(buf[p0 + 4:pos + total]), key)
            else:
                payload = bytes(buf[p0:pos + total])
            pos += total
            if op >= 8:
                out.append((op, payload))
            elif op == OP_CONT:
                if self._fop is None:
                    raise ProtocolError(1002, "unexpected continuation")
                self._frag += payload
                if len(self._frag) > self.max_size:
                    raise ProtocolError(1009, "message too big")
                if fin:
                    out.append((self._fop, bytes(self._frag)))
                    self._fop = None
                    self._frag = bytearray()
            elif op in (OP_TEXT, OP_BINARY):
                if self._fop is not None:
                    raise ProtocolError(1002, "new message during fragmentation")
                if fin:
                    out.append((op, payload))
                else:
                    self._fop = op
                    self._frag = bytearray(payload)
            else:
                raise ProtocolError(1002, "unknown opcode")
        if pos:
            del buf[:pos]
        return out
