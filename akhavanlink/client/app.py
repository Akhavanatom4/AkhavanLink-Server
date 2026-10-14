# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Application shell: settings, logging, local UI, app window and lifetime."""
import argparse
import asyncio
import collections
import logging
import logging.handlers
import os
import secrets
import sys
import time
import webbrowser
from pathlib import Path

from .. import APP_NAME, CREATOR, CREATOR_FA, VERSION
from .config import ConfigStore
from .engine import Engine
from .tun import MemTun
from .uiserver import UIServer

log = logging.getLogger("akhavanlink")


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.environ.get("AKHAVANLINK_HOME") or Path(__file__).resolve().parents[2])


def pick_home(base):
    """Portable by default (config next to the program); falls back to %APPDATA% if that folder is read-only."""
    try:
        (base / "logs").mkdir(parents=True, exist_ok=True)
        probe = base / "logs" / ".w"
        probe.write_text("x")
        probe.unlink()
        return base
    except OSError:
        alt = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
        (alt / "logs").mkdir(parents=True, exist_ok=True)
        return alt


def web_dir():
    for c in (Path(__file__).resolve().parent / "web", Path(getattr(sys, "_MEIPASS", ".")) / "akhavanlink" / "client" / "web"):
        if (c / "index.html").is_file():
            return c
    raise FileNotFoundError("web UI files not found")


class RingHandler(logging.Handler):
    def __init__(self, app):
        super().__init__(logging.INFO)
        self.app = app

    def emit(self, record):
        try:
            self.app.add_log(record.levelname[0], self.format(record))
        except Exception:
            pass


class StubPlatform:
    """Linux/macOS (development, tests, --demo): in-memory adapter, no admin needed."""
    name = "stub"

    def is_admin(self):
        return True

    def driver_status(self):
        return "n/a"

    def tun_factory(self, spec):
        return MemTun(spec)

    def download_driver(self, url=""):
        raise RuntimeError("only available on Windows")

    def relaunch_admin(self, args):
        return False

    def launch_ui(self, url, profile_dir):
        webbrowser.open(url)

    def open_folder(self, path):
        pass

    def cleanup(self):
        pass


class App:
    def __init__(self, args, home, cfg, plat):
        self.args, self.home, self.cfg, self.plat = args, home, cfg, plat
        self.logs = collections.deque(maxlen=300)
        self.loop = None
        self.engine = None
        self.ui = None
        self.demo = None
        self.demo_tun = None
        self.proc = None
        self.quit = None
        self.token = args.token or secrets.token_urlsafe(18)
        self.t0 = time.monotonic()

    # ---- log ring (any thread)
    def add_log(self, level, text):
        line = {"ts": time.strftime("%H:%M:%S"), "lv": level, "msg": text}
        def push():
            self.logs.append(line)
            if self.ui is not None:
                self.ui.broadcast({"t": "log", "line": line})
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(push)
        else:
            self.logs.append(line)

    # ---- state for the page
    def full_state(self):
        s = self.engine.snapshot()
        s.update(admin=self.plat.is_admin(), platform=sys.platform, driver=self.plat.driver_status(),
                 demo=bool(self.args.demo), home=str(self.home))
        if self.args.fake_windows:                      # UI preview of the Windows-only banners
            s.update(platform="win32", admin=False, driver="missing", demo=False)
        return s

    def _changed(self):
        if self.ui is not None:
            self.ui.schedule_push()

    def _event(self, ev):
        if self.ui is not None:
            self.ui.broadcast({"t": "event", **ev})

    async def apply_config(self, patch, quiet=False):
        eng = self.engine
        changed = self.cfg.update(patch)
        if changed and eng.status in ("connecting", "online", "reconnecting"):
            if changed & {"serverUrl", "accessKey", "network", "password", "proxy"}:
                await eng.disconnect()
                eng.connect()
            elif "nickname" in changed:
                eng.send_nick()
        self._changed()
        if not quiet:
            self.ui.broadcast({"t": "toast", "k": "saved"})

    async def install_driver(self):
        self.ui.broadcast({"t": "toast", "k": "driver_downloading"})
        try:
            await self.loop.run_in_executor(None, self.plat.download_driver, self.cfg.data["wintunUrl"])
            self.ui.broadcast({"t": "toast", "k": "driver_ok"})
        except Exception as e:
            log.warning("driver download failed: %s", e)
            self.ui.broadcast({"t": "toast", "k": "driver_fail", "detail": str(e)[:200]})
        self._changed()

    def relaunch_admin(self):
        if self.plat.relaunch_admin(["--elevated"]):
            self.request_quit()

    def open_log_dir(self):
        self.plat.open_folder(self.home / "logs")

    def request_quit(self):
        self.loop.call_soon_threadsafe(self.quit.set)

    # ---- lifetime
    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.quit = asyncio.Event()
        self.engine = Engine(self.cfg, self.loop, self._make_tun, on_change=self._changed, on_event=self._event)
        self.ui = UIServer(self, web_dir(), self.token)
        port = await self.ui.start(self.args.port)
        self.engine.start()
        url = "http://127.0.0.1:%d/?t=%s" % (port, self.token)
        log.info("%s %s - Created by %s (%s)", APP_NAME, VERSION, CREATOR, CREATOR_FA)
        log.info("local UI: http://127.0.0.1:%d/", port)
        if self.args.print_url:
            print(url, flush=True)
        if self.args.demo:
            from .demo import Demo
            self.demo = Demo(self)
            await self.demo.start()
        if not self.args.no_browser:
            try:
                self.proc = self.plat.launch_ui(url, self.home / "webview")
            except Exception:
                log.exception("could not open the app window")
                webbrowser.open(url)
        if self.cfg.data["autoConnect"] and self.cfg.data["serverUrl"] and not self.args.demo:
            self.engine.connect()
        watcher = asyncio.ensure_future(self._watch())
        try:
            await self.quit.wait()
        finally:
            watcher.cancel()
            log.info("shutting down")
            if self.demo:
                await self.demo.stop()
            await self.engine.shutdown()
            await self.ui.stop()
            try:
                self.plat.cleanup()
            except Exception:
                log.exception("cleanup failed")

    def _make_tun(self, spec):
        t = self.plat.tun_factory(spec)
        if self.args.demo:
            self.demo_tun = t
        return t

    async def _watch(self):
        """Quit when the app window is gone."""
        ever, zero_since, opened = False, None, False
        while True:
            await asyncio.sleep(1.0)
            if self.args.no_browser:
                continue
            now = time.monotonic()
            if self.ui.conns:
                ever, zero_since = True, None
                continue
            zero_since = zero_since or now
            if not ever and not opened and now - self.t0 > 20:           # window never appeared -> use the default browser
                opened = True
                log.warning("the app window did not connect - opening the default browser")
                webbrowser.open("http://127.0.0.1:%d/?t=%s" % (self.ui.port, self.token))
            gone = self.proc is not None and self.proc.poll() is not None
            if (ever and now - zero_since > (4 if gone else 30)) or (not ever and now - self.t0 > 90):
                log.info("app window closed")
                self.quit.set()
                return


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog=APP_NAME, description="%s - virtual LAN for gamers. Created by %s" % (APP_NAME, CREATOR))
    ap.add_argument("--demo", action="store_true", help="preview with simulated players (no server, no admin rights needed)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the app window")
    ap.add_argument("--print-url", action="store_true")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--token", default="")
    ap.add_argument("--config", default="")
    ap.add_argument("--elevated", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--fake-windows", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-elevate", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="Windows: check driver, admin rights and adapter creation")
    ap.add_argument("--version", action="store_true")
    return ap.parse_args(argv)


def setup_logging(home, app):
    lg = logging.getLogger("akhavanlink")
    lg.setLevel(logging.INFO)
    fmt = logging.Formatter("%(message)s")
    ring = RingHandler(app)
    ring.setFormatter(fmt)
    lg.addHandler(ring)
    fh = logging.handlers.RotatingFileHandler(home / "logs" / "akhavanlink.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    lg.addHandler(fh)
    if sys.stderr is not None:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        lg.addHandler(sh)


def main(argv=None):
    args = parse_args(argv)
    if args.version:
        print("%s %s - Created by %s" % (APP_NAME, VERSION, CREATOR))
        return 0
    for name in ("stdout", "stderr"):                       # windowed (no console) builds have no std streams
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))
    base = app_dir()
    home = pick_home(base)
    plat = StubPlatform()
    if sys.platform == "win32":
        from . import winnet
        holder = {}
        plat = winnet.WindowsPlatform(base, home, lambda: holder["cfg"].data)
        if args.selftest:
            return winnet.selftest(plat, home / "selftest.txt")
        if not args.demo and not winnet.is_admin() and not args.elevated and not args.no_elevate:
            if winnet.relaunch_as_admin(["--elevated"] + sys.argv[1:]):
                return 0
        if not args.demo:
            _, running = winnet.single_instance()
            if running:
                winnet.message_box(APP_NAME, "AkhavanLink is already running.\nبرنامه از قبل در حال اجراست.")
                return 0
    cfg = ConfigStore(None if args.demo else (args.config or home / "config.json"))
    if sys.platform == "win32":
        holder["cfg"] = cfg
    cfg.ensure_identity()
    if not args.demo and not (home / "config.json").exists() and not args.config:
        cfg.save()
    app = App(args, home, cfg, plat)
    setup_logging(home, app)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
    return 0
