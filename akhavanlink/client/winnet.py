# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Windows-specific parts: Wintun adapter, netsh setup, elevation, app window and driver download.

Everything that touches ctypes/Windows APIs lives inside functions or classes, so this module imports fine
on other systems (the pure helpers are unit-tested on Linux).
"""
import hashlib
import io
import ipaddress
import logging
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

from .tun import Tun, TunError

log = logging.getLogger("akhavanlink.win")

WINTUN_URL = "https://www.wintun.net/builds/wintun-0.14.1.zip"
WINTUN_SHA256 = "07c256185d6ee3652e09fa55c0b673e2624b565e02c4b9091c79ca7d2f24ef51"
ADAPTER_NAME = "AkhavanLink"
FW_RULE = "AkhavanLink-LAN"
CREATE_NO_WINDOW = 0x08000000
ERROR_ACCESS_DENIED, ERROR_HANDLE_EOF, ERROR_NO_MORE_ITEMS = 5, 38, 259


# ------------------------------------------------------------------ pure helpers
def arch():
    m = platform.machine().lower()
    if "arm" in m:
        return "arm64" if sys.maxsize > 2 ** 32 else "arm"
    return "amd64" if sys.maxsize > 2 ** 32 else "x86"


def prefix_to_mask(prefix):
    return str(ipaddress.ip_network("0.0.0.0/%d" % prefix).netmask)


def find_wintun(dirs):
    for d in dirs:
        for rel in ("wintun.dll", os.path.join("drivers", "wintun.dll")):
            p = Path(d) / rel
            if p.is_file():
                return p
    return None


def download_wintun(dest_dir, url="", expected_sha256=WINTUN_SHA256):
    """Download the official Wintun zip, verify its SHA-256 and extract the DLL for this CPU."""
    req = urllib.request.Request(url or WINTUN_URL, headers={"User-Agent": "AkhavanLink (Created by Alireza Akhavan)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read(40 * 1024 * 1024)
    got = hashlib.sha256(data).hexdigest()
    if expected_sha256 and got != expected_sha256:
        raise TunError("driver_hash", "checksum mismatch: got %s" % got)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            blob = z.read("wintun/bin/%s/wintun.dll" % arch())
    except (zipfile.BadZipFile, KeyError) as e:
        raise TunError("driver_download", "the downloaded archive is not a valid Wintun package (%s)" % e)
    dest = Path(dest_dir) / "wintun.dll"
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(blob)
    os.replace(tmp, dest)
    return dest


def browser_candidates(env=os.environ):
    bases = [env.get("ProgramFiles(x86)"), env.get("ProgramFiles"), env.get("LocalAppData")]
    rels = (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Vivaldi\Application\vivaldi.exe")
    return [os.path.join(b, r) for r in rels for b in bases if b]


def browser_args(exe, url, profile_dir):
    return [exe, "--app=" + url, "--user-data-dir=" + str(profile_dir), "--window-size=1260,840",
            "--no-first-run", "--no-default-browser-check", "--disable-background-mode",
            "--disable-features=Translate,msEdgeSidebarV2", "--disable-sync"]


def run_hidden(args, timeout=20):
    """Run a console tool without flashing a window; never raises (returns (exit_code, text))."""
    try:
        kw = {}
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            kw = {"startupinfo": si, "creationflags": CREATE_NO_WINDOW}
        r = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, **kw)
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError) as e:
        return 1, str(e)
    raw = r.stdout or b""
    try:
        out = raw.decode("oem")
    except (LookupError, UnicodeDecodeError):
        out = raw.decode("utf-8", "replace")
    return r.returncode, out.strip()


def netsh():
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "netsh.exe")


def configure_address(name, ip, prefix):
    last = ""
    for _ in range(16):                       # the adapter needs a moment before the IP stack knows it
        rc, out = run_hidden([netsh(), "interface", "ipv4", "set", "address", "name=" + name, "source=static",
                              "address=" + ip, "mask=" + prefix_to_mask(prefix), "store=active"])
        if rc == 0:
            return
        last = out
        time.sleep(0.5)
    raise TunError("tun_failed", "netsh could not set the IP address: " + last[:300])


def tune_adapter(name, mtu):
    """Best effort: lowest metric (games pick this adapter for LAN broadcast), MTU, no duplicate-address wait."""
    for args in (["set", "interface", name, "metric=1", "store=active"],
                 ["set", "subinterface", name, "mtu=%d" % mtu, "store=active"],
                 ["set", "interface", name, "dadtransmits=0", "store=active"]):
        rc, out = run_hidden([netsh(), "interface", "ipv4"] + args)
        if rc != 0:
            log.info("netsh %s -> %s", " ".join(args[:2]), out[:160])


def firewall_allow(cidr):
    run_hidden([netsh(), "advfirewall", "firewall", "delete", "rule", "name=" + FW_RULE])
    rc, out = run_hidden([netsh(), "advfirewall", "firewall", "add", "rule", "name=" + FW_RULE, "dir=in",
                          "action=allow", "protocol=any", "remoteip=" + cidr, "profile=any", "enable=yes"])
    if rc != 0:
        log.warning("firewall rule could not be added: %s", out[:200])


def firewall_remove():
    run_hidden([netsh(), "advfirewall", "firewall", "delete", "rule", "name=" + FW_RULE])


# ------------------------------------------------------------------ Windows API wrappers
def is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(extra_args=()):
    """Ask Windows (UAC prompt) to start this program again with administrator rights."""
    import ctypes
    extra = list(extra_args)
    if getattr(sys, "frozen", False):
        params, cwd = extra, os.path.dirname(sys.executable)
    else:
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        if spec is not None and spec.name:
            params = ["-m", spec.name[:-9] if spec.name.endswith(".__main__") else spec.name] + extra
        else:
            params = [os.path.abspath(sys.argv[0])] + extra
        cwd = os.getcwd()
    sh = ctypes.windll.shell32.ShellExecuteW
    sh.restype = ctypes.c_void_p
    sh.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
    r = sh(None, "runas", sys.executable, subprocess.list2cmdline(params), cwd, 1)
    return (r or 0) > 32


def single_instance(name="Local\\AkhavanLink.by.AlirezaAkhavan"):
    """Returns (handle, already_running)."""
    import ctypes
    from ctypes import wintypes as wt
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    k.CreateMutexW.restype = wt.HANDLE
    h = k.CreateMutexW(None, False, name)
    return h, ctypes.get_last_error() == 183


def message_box(title, text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except Exception:
        pass


class WintunTun(Tun):
    """Layer-3 adapter backed by wintun.dll (https://www.wintun.net)."""

    def __init__(self, dll_path, spec):
        import ctypes
        from ctypes import wintypes as wt
        self._ct = ctypes
        self.spec = spec
        self._closed = False
        self._wlock = threading.Lock()
        self._thread = None
        try:
            d = ctypes.WinDLL(str(dll_path), use_last_error=True)
        except OSError as e:
            raise TunError("no_driver", "cannot load %s: %s" % (dll_path, e))
        P = ctypes.c_void_p

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

        d.WintunCreateAdapter.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.POINTER(GUID)]
        d.WintunCreateAdapter.restype = P
        d.WintunCloseAdapter.argtypes = [P]
        d.WintunCloseAdapter.restype = None
        d.WintunStartSession.argtypes = [P, wt.DWORD]
        d.WintunStartSession.restype = P
        d.WintunEndSession.argtypes = [P]
        d.WintunEndSession.restype = None
        d.WintunGetReadWaitEvent.argtypes = [P]
        d.WintunGetReadWaitEvent.restype = wt.HANDLE
        d.WintunReceivePacket.argtypes = [P, ctypes.POINTER(wt.DWORD)]
        d.WintunReceivePacket.restype = P
        d.WintunReleaseReceivePacket.argtypes = [P, P]
        d.WintunReleaseReceivePacket.restype = None
        d.WintunAllocateSendPacket.argtypes = [P, wt.DWORD]
        d.WintunAllocateSendPacket.restype = P
        d.WintunSendPacket.argtypes = [P, P]
        d.WintunSendPacket.restype = None
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        k32.WaitForSingleObject.restype = wt.DWORD
        k32.SetEvent.argtypes = [wt.HANDLE]
        k32.SetEvent.restype = wt.BOOL
        self._d, self._k32, self._size = d, k32, wt.DWORD(0)

        guid = GUID(0xA4E5D1B2, 0x6C3F, 0x4C7A, (ctypes.c_ubyte * 8)(0x9B, 0x1D, 0x5A, 0x0F, 0x7E, 0x2C, 0x8D, 0x41))
        self._adapter = d.WintunCreateAdapter(spec.name, "AkhavanLink", ctypes.byref(guid))
        if not self._adapter:
            err = ctypes.get_last_error()
            if err == ERROR_ACCESS_DENIED:
                raise TunError("no_admin", "access denied")
            raise TunError("tun_failed", "WintunCreateAdapter failed (Windows error %d)" % err)
        self._session = d.WintunStartSession(self._adapter, 0x400000)
        if not self._session:
            err = ctypes.get_last_error()
            d.WintunCloseAdapter(self._adapter)
            raise TunError("tun_failed", "WintunStartSession failed (Windows error %d)" % err)
        self._event = d.WintunGetReadWaitEvent(self._session)
        try:
            configure_address(spec.name, spec.ip, spec.prefix)
            tune_adapter(spec.name, spec.mtu)
            if spec.firewall:
                firewall_allow(str(ipaddress.ip_network("%s/%d" % (spec.ip, spec.prefix), strict=False)))
        except BaseException:
            self.close()
            raise
        log.info("adapter '%s' ready: %s/%d mtu %d", spec.name, spec.ip, spec.prefix, spec.mtu)

    def start(self, on_packet):
        self._cb = on_packet
        self._thread = threading.Thread(target=self._reader, name="wintun-reader", daemon=True)
        self._thread.start()

    def _reader(self):
        d, ct, size = self._d, self._ct, self._size
        while not self._closed:
            ptr = d.WintunReceivePacket(self._session, ct.byref(size))
            if ptr:
                pkt = ct.string_at(ptr, size.value)
                d.WintunReleaseReceivePacket(self._session, ptr)
                try:
                    self._cb(pkt)
                except Exception:
                    log.exception("packet callback failed")
                continue
            err = ct.get_last_error()
            if err == ERROR_NO_MORE_ITEMS:
                self._k32.WaitForSingleObject(self._event, 250)
            elif err == ERROR_HANDLE_EOF:
                break
            else:
                log.warning("WintunReceivePacket error %d", err)
                time.sleep(0.05)

    def write(self, pkt):
        n = len(pkt)
        with self._wlock:
            if self._closed:
                return
            buf = self._d.WintunAllocateSendPacket(self._session, n)
            if not buf:                         # ring full -> drop, exactly like a congested network card
                return
            self._ct.memmove(buf, pkt, n)
            self._d.WintunSendPacket(self._session, buf)

    def set_address(self, ip, prefix):
        configure_address(self.spec.name, ip, prefix)
        self.spec.ip, self.spec.prefix = ip, prefix
        if self.spec.firewall:
            firewall_allow(str(ipaddress.ip_network("%s/%d" % (ip, prefix), strict=False)))

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._k32.SetEvent(self._event)
            if self._thread is not None:
                self._thread.join(2.0)
            with self._wlock:
                self._d.WintunEndSession(self._session)
                self._d.WintunCloseAdapter(self._adapter)
        finally:
            firewall_remove()
            log.info("adapter closed")


class WindowsPlatform:
    name = "windows"

    def __init__(self, app_dir, home, config_getter):
        self.app_dir, self.home, self.cfg = Path(app_dir), Path(home), config_getter
        self._proc = None

    def search_dirs(self):
        d = [self.app_dir, self.home, Path(getattr(sys, "_MEIPASS", self.app_dir))]
        return [x for i, x in enumerate(d) if x not in d[:i]]

    def is_admin(self):
        return is_admin()

    def driver_status(self):
        return "ok" if find_wintun(self.search_dirs()) else "missing"

    def tun_factory(self, spec):
        if not is_admin():
            raise TunError("no_admin", "not elevated")
        dll = find_wintun(self.search_dirs())
        if dll is None:
            raise TunError("no_driver", "wintun.dll was not found next to the program")
        return WintunTun(dll, spec)

    def download_driver(self, url=""):
        dest = self.app_dir if os.access(self.app_dir, os.W_OK) else self.home
        return download_wintun(dest, url, None if url else WINTUN_SHA256)

    def relaunch_admin(self, args):
        return relaunch_as_admin(args)

    def launch_ui(self, url, profile_dir):
        exe = next((c for c in browser_candidates() if os.path.isfile(c)), None)
        if exe is None:
            webbrowser.open(url)
            return None
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        self._proc = subprocess.Popen(browser_args(exe, url, profile_dir), stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return self._proc

    def open_folder(self, path):
        try:
            os.startfile(str(path))
        except Exception:
            pass

    def cleanup(self):
        firewall_remove()


def selftest(platform_obj, report_path):
    """Diagnostics for troubleshooting on a real PC:  AkhavanLink.exe --selftest"""
    from .tun import TunSpec
    lines = ["AkhavanLink self-test  (Created by Alireza Akhavan)", "Python %s on %s %s" % (sys.version.split()[0], platform.platform(), arch())]
    ok = True

    def step(title, fn):
        nonlocal ok
        try:
            lines.append("OK    %s %s" % (title, fn() or ""))
        except Exception as e:  # noqa
            ok = False
            lines.append("FAIL  %s: %s" % (title, e))

    step("administrator rights", lambda: None if is_admin() else (_ for _ in ()).throw(RuntimeError("not elevated - run as administrator")))
    step("wintun.dll present", lambda: str(find_wintun(platform_obj.search_dirs()) or (_ for _ in ()).throw(RuntimeError("missing"))))
    tun = []

    def create():
        t = platform_obj.tun_factory(TunSpec("10.77.254.2", 16, 1400, True))
        tun.append(t)
    step("create adapter + IP 10.77.254.2/16", create)
    if tun:
        step("ping own address", lambda: run_hidden(["ping", "-n", "1", "-w", "1500", "10.77.254.2"])[1].splitlines()[-1:] and "")
        tun[0].close()
    step("browser found", lambda: next((c for c in browser_candidates() if os.path.isfile(c)), None) or (_ for _ in ()).throw(RuntimeError("no Edge/Chrome found")))
    lines.append("RESULT: %s" % ("everything is fine" if ok else "some checks failed - send this file to the developer"))
    text = "\n".join(lines)
    try:
        Path(report_path).write_text(text, encoding="utf-8")
    except OSError:
        pass
    message_box("AkhavanLink self-test", text)
    return 0 if ok else 1
