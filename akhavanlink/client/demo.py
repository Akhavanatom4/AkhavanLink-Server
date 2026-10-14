# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""--demo: preview the app without a server or driver. A private relay and a few bot players run in-process."""
import asyncio
import logging
import random
import time

from ..common.aio import HttpWsServer
from ..server.hub import Config, Hub
from .config import ConfigStore
from .engine import Engine
from .tun import MemTun, make_ipv4

BOTS = (("Sara", 0.012), ("Reza", 0.034), ("Mina", 0.071), ("Kian", 0.128), ("Nima", 0.26))


class Demo:
    def __init__(self, app):
        self.app = app
        self.hub = Hub(Config())
        self.srv = HttpWsServer({"/ws": self.hub.ws_factory}, self.hub.http_routes())
        self.bots = []
        self.tuns = {}
        self.task = None
        self.cool = {}

    async def start(self):
        await self.srv.start("127.0.0.1", 0)
        url = "ws://127.0.0.1:%d/ws" % self.srv.port
        self.app.cfg.update({"serverUrl": url, "network": "LAN Party", "password": "", "nickname": "Alireza"}, save=False)
        loop = asyncio.get_running_loop()
        for i, (nick, delay) in enumerate(BOTS):
            cfg = ConfigStore(None)
            cfg.update({"serverUrl": url, "network": "LAN Party", "nickname": nick, "firewall": False}, save=False)
            cfg.update({"clientId": ("bot%d-%s" % (i, nick)).ljust(32, "x")}, internal=True, save=False)
            eng = Engine(cfg, loop, lambda spec, n=nick: self._tun(n, spec))
            eng.pp_delay = delay
            eng.log = logging.getLogger("akhavanlink.bot")
            eng.log.propagate = False
            eng.start()
            self.bots.append(eng)
        self.task = asyncio.ensure_future(self._run())

    def _tun(self, nick, spec):
        t = MemTun(spec)
        self.tuns[nick] = t
        return t

    async def _run(self):
        main = self.app.engine
        while True:
            await asyncio.sleep(0.4)
            if main.status != "online":
                for b in self.bots:                       # bots only exist while you are on the LAN
                    if b.status != "idle":
                        await b.disconnect()
                continue
            for b in self.bots:
                if b.status == "idle" and time.monotonic() >= self.cool.get(id(b), 0):
                    b.connect()
                    await asyncio.sleep(0.9)
            # light traffic in both directions so the counters move
            mt = self.app.demo_tun
            for b in self.bots:
                t = self.tuns.get(b.cfg.data["nickname"])
                if t is not None and b.ip and main.ip and random.random() < 0.8:
                    t.inject(make_ipv4(b.ip, main.ip, random.randint(60, 600)))
                if mt is not None and main.ip and b.ip and random.random() < 0.6:
                    mt.inject(make_ipv4(main.ip, b.ip, random.randint(60, 400)))
            if random.random() < 0.012 and self.bots:        # somebody drops out now and then
                victim = random.choice(self.bots[2:])
                await victim.disconnect()
                self.cool[id(victim)] = time.monotonic() + random.uniform(8, 16)

    async def stop(self):
        if self.task:
            self.task.cancel()
        for b in self.bots:
            await b.shutdown()
        await self.srv.stop()
