# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Client settings (config.json) and server-address normalisation."""
import getpass
import ipaddress
import json
import logging
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger("akhavanlink.config")

DEFAULTS = {
    "serverUrl": "",        # e.g. my-app.deplexo.app  or  wss://my-app.deplexo.app/ws
    "accessKey": "",        # optional key, must match ACCESS_KEY on the server
    "network": "AkhavanLAN",
    "password": "",
    "nickname": "",
    "clientId": "",
    "lastIp": "",
    "lang": "fa",
    "autoConnect": False,
    "firewall": True,
    "sound": True,
    "fx": "full",
    "proxy": "",            # optional HTTP proxy, e.g. http://127.0.0.1:10809
    "mtu": 1400,
    "wintunUrl": "",
}
STR_LIMITS = {"serverUrl": 300, "accessKey": 128, "network": 32, "nickname": 24, "proxy": 300, "wintunUrl": 300, "lastIp": 15}
BOOL_KEYS = ("autoConnect", "firewall", "sound")


def is_private_host(host):
    h = (host or "").strip("[]").lower()
    if h == "localhost" or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def normalize_server_url(raw):
    """'my-app.deplexo.app' -> 'wss://my-app.deplexo.app/ws';  'http://1.2.3.4:8080' -> 'ws://1.2.3.4:8080/ws'."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty server address")
    if "://" not in s:
        hostport = s.split("/", 1)[0]
        host, _, port = hostport.rpartition(":") if hostport.count(":") == 1 else (hostport, "", "")
        plain = (port not in ("", "443")) or is_private_host(host or hostport)
        s = ("ws://" if plain else "wss://") + s
    u = urlsplit(s)
    scheme = {"https": "wss", "http": "ws"}.get(u.scheme.lower(), u.scheme.lower())
    if scheme not in ("ws", "wss") or not u.hostname:
        raise ValueError("bad server address")
    path = u.path if u.path not in ("", "/") else "/ws"
    return urlunsplit((scheme, u.netloc, path, u.query, ""))


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                self.update(raw, internal=True, save=False)
        except (OSError, ValueError) as e:
            log.warning("could not read %s (%s) - using defaults", self.path, e)
            try:
                self.path.replace(self.path.with_suffix(".broken.json"))
            except OSError:
                pass

    def ensure_identity(self):
        changed = {}
        if len(self.data["clientId"]) < 16:
            changed["clientId"] = secrets.token_hex(16)
        if not self.data["nickname"]:
            try:
                changed["nickname"] = (os.environ.get("USERNAME") or getpass.getuser() or "Player")[:24]
            except Exception:
                changed["nickname"] = "Player"
        if changed:
            self.update(changed, internal=True)

    def update(self, patch, internal=False, save=True):
        """Validate and apply a settings patch; returns the set of keys that really changed."""
        changed = set()
        for k, v in (patch or {}).items():
            if k not in DEFAULTS or (k in ("clientId", "lastIp") and not internal):
                continue
            if k in BOOL_KEYS:
                v = bool(v)
            elif k == "password":
                v = v[:64] if isinstance(v, str) else None
            elif k in STR_LIMITS:
                v = v.strip()[:STR_LIMITS[k]] if isinstance(v, str) else None
            elif k == "clientId":
                v = v.strip()[:128] if isinstance(v, str) else None
            elif k == "lang":
                v = v if v in ("fa", "en") else None
            elif k == "fx":
                v = v if v in ("full", "lite") else None
            elif k == "mtu":
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = None
                if v is not None and not 1200 <= v <= 1500:
                    v = None
            if v is None or self.data.get(k) == v:
                continue
            self.data[k] = v
            changed.add(k)
        if changed and save:
            self.save()
        return changed

    def save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("could not save settings: %s", e)

    def public(self):
        d = dict(self.data)
        d.pop("clientId", None)
        return d
