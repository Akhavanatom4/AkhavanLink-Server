# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Virtual network adapter interface + an in-memory adapter (tests / demo)."""
import struct
import threading


class TunError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class TunSpec:
    def __init__(self, ip, prefix, mtu=1400, firewall=True, name="AkhavanLink"):
        self.ip, self.prefix, self.mtu, self.firewall, self.name = ip, prefix, mtu, firewall, name


class Tun:
    """A layer-3 adapter. start() begins delivering outgoing IPv4 packets (from a worker thread)."""

    def start(self, on_packet):
        raise NotImplementedError

    def write(self, pkt):
        raise NotImplementedError

    def set_address(self, ip, prefix):
        pass

    def close(self):
        pass


class MemTun(Tun):
    def __init__(self, spec=None):
        self.spec = spec
        self.written = []
        self.closed = False
        self._cb = None

    def start(self, on_packet):
        self._cb = on_packet

    def write(self, pkt):
        self.written.append(bytes(pkt))

    def inject(self, pkt):
        """Pretend the OS sent this packet through the adapter."""
        if self._cb and not self.closed:
            self._cb(bytes(pkt))

    def set_address(self, ip, prefix):
        self.spec = TunSpec(ip, prefix, self.spec.mtu if self.spec else 1400)

    def close(self):
        self.closed = True


def make_ipv4(src, dst, payload_len=24, proto=17):
    """Build a minimal IPv4 packet (header checksum left 0 - not needed for the relay)."""
    total = 20 + payload_len
    head = struct.pack(">BBHHHBBH4s4s", 0x45, 0, total, 0, 0, 64, proto, 0,
                       bytes(int(x) for x in src.split(".")), bytes(int(x) for x in dst.split(".")))
    return head + bytes((i & 0xFF) for i in range(payload_len))
