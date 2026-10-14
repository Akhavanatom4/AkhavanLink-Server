# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""AkhavanLink relay server.   python -m akhavanlink.server"""
import argparse
import asyncio
import logging
import os
import signal
import sys
import urllib.request

from .. import APP_NAME, CREATOR, CREATOR_FA, VERSION
from ..common.aio import HttpWsServer
from .hub import Config, Hub

BANNER = """
  ============================================================
    {name} Server  v{ver}
    Virtual LAN relay for gamers
    Created by {creator}  ({creator_fa})
  ============================================================"""


def healthcheck(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/healthz" % port, timeout=4) as r:
            return 0 if r.status == 200 else 1
    except Exception:
        return 1


async def serve(host, port, cfg):
    hub = Hub(cfg)
    server = HttpWsServer({"/ws": hub.ws_factory}, hub.http_routes(), max_msg=cfg.max_msg)
    await server.start(host, port)
    log = logging.getLogger("akhavanlink")
    log.info("listening on %s:%d  |  network %s  |  players per network: %s  |  access key: %s",
             host, server.port, cfg.cidr, cfg.max_per_net or "unlimited", "ON" if cfg.access_key else "off")
    janitor = asyncio.ensure_future(hub.janitor(server))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError, ValueError):
            pass
    try:
        await stop.wait()
    finally:
        janitor.cancel()
        log.info("shutting down")
        await server.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="akhavanlink.server", description="%s relay server - by %s" % (APP_NAME, CREATOR))
    ap.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080") or 8080))
    ap.add_argument("--healthcheck", action="store_true")
    ap.add_argument("--version", action="store_true")
    a = ap.parse_args(argv)
    if a.version:
        print("%s Server %s - Created by %s" % (APP_NAME, VERSION, CREATOR))
        return 0
    if a.healthcheck:
        return healthcheck(a.port)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    print(BANNER.format(name=APP_NAME, ver=VERSION, creator=CREATOR, creator_fa=CREATOR_FA), flush=True)
    try:
        asyncio.run(serve(a.host, a.port, Config.from_env()))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
