# AkhavanLink — Created by Alireza Akhavan
"""Micro-benchmark of the relay itself (loopback): forwarding delay and throughput.   python tests/bench_relay.py"""
import asyncio
import json
import statistics
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from akhavanlink.common import aio, ws  # noqa: E402
from akhavanlink.server.hub import Config, Hub  # noqa: E402


class Peer:
    def __init__(self):
        self.q = asyncio.Queue()
        self.delays, self.count, self.ip = [], 0, None

    def on_open(self, c): pass
    def on_close(self, c, e): pass

    def on_message(self, c, op, d):
        if op == ws.OP_TEXT:
            self.q.put_nowait(json.loads(d))
        else:
            self.count += 1
            sent = struct.unpack_from(">q", d, 20)[0]
            self.delays.append((time.perf_counter_ns() - sent) / 1e6)


def pkt(src, dst, size=120):
    h = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + 8 + size, 0, 0, 64, 17, 0, bytes(map(int, src.split("."))), bytes(map(int, dst.split("."))))
    return h + struct.pack(">q", time.perf_counter_ns()) + bytes(size)


async def join(url, name):
    p = Peer()
    c = await aio.connect(url, p)
    await p.q.get()
    c.send_text(json.dumps({"t": "join", "v": 1, "net": "bench", "id": (name * 20)[:32], "nick": name}))
    w = await p.q.get()
    p.ip = w["ip"]
    return c, p


async def main():
    hub = Hub(Config())
    srv = aio.HttpWsServer({"/ws": hub.ws_factory}, hub.http_routes())
    await srv.start("127.0.0.1", 0)
    url = "ws://127.0.0.1:%d/ws" % srv.port
    print("1) two players, 500 packets/s of 150 bytes for 4 s (one-way delay through the relay)")
    (ca, pa), (cb, pb) = await join(url, "a"), await join(url, "b")
    for _ in range(2000):
        ca.send_binary(pkt(pa.ip, pb.ip)); await asyncio.sleep(0.002)
    await asyncio.sleep(0.2)
    d = sorted(pb.delays)
    print("   delivered %d/2000   median %.3f ms   p99 %.3f ms   max %.3f ms" % (pb.count, statistics.median(d), d[int(len(d) * .99)], d[-1]))

    print("2) 10 players x 60 packets/s each, all broadcast-flooded (worst case fan-out), 4 s")
    peers = [await join(url, "p%d" % i) for i in range(10)]
    for _, p in peers:
        p.delays.clear(); p.count = 0
    t_end = time.perf_counter() + 4
    sent = 0
    while time.perf_counter() < t_end:
        for c, p in peers:
            c.send_binary(pkt(p.ip, "10.77.255.255")); sent += 1
        await asyncio.sleep(1 / 60)
    await asyncio.sleep(0.3)
    got = sum(p.count for _, p in peers); alld = sorted(x for _, p in peers for x in p.delays)
    print("   sent %d packets -> delivered %d (expected %d)   median %.3f ms   p99 %.3f ms" % (sent, got, sent * 9, statistics.median(alld), alld[int(len(alld) * .99)]))

    print("3) raw throughput: one sender, one receiver, 1400-byte packets as fast as the event loop allows, 3 s")
    pb.count = 0; pb.delays.clear()
    t0 = time.perf_counter(); n = 0
    big = pkt(pa.ip, pb.ip, 1400)
    while time.perf_counter() - t0 < 3:
        for _ in range(50):
            ca.send_binary(big); n += 1
        await asyncio.sleep(0)
    await asyncio.sleep(0.5)
    dt = 3.0
    print("   sent %d  delivered %d  (%.0f packets/s, %.0f Mbit/s forwarded; excess is dropped by design when a receiver is congested)" % (n, pb.count, pb.count / dt, pb.count * 1400 * 8 / dt / 1e6))
    await srv.stop()


asyncio.run(main())
