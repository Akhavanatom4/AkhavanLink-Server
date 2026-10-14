#!/usr/bin/env python3
# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Build the portable Windows package (the folder/zip you hand to your friends).

    python scripts/make_portable.py --server my-app.deplexo.app

Steps:  PyInstaller -> AkhavanLink.exe   |   download Wintun (wintun.dll)   |   write config.json + README   |   zip.
Runs on Windows (GitHub Actions does exactly this).  Result: dist/AkhavanLink-Portable-Windows.zip
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from akhavanlink import APP_NAME, CREATOR, VERSION  # noqa: E402
from akhavanlink.client import winnet  # noqa: E402
from akhavanlink.client.config import DEFAULTS  # noqa: E402
from akhavanlink.client.tun import TunError  # noqa: E402

FOLDER = "AkhavanLink-Portable"


def build_exe(dist, work):
    web = ROOT / "akhavanlink" / "client" / "web"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noconsole", "--uac-admin",
           "--name", "AkhavanLink", "--icon", str(ROOT / "assets" / "icon.ico"),
           "--version-file", str(ROOT / "assets" / "version_info.txt"),
           "--add-data", "%s%s%s" % (web, os.pathsep, "akhavanlink/client/web"),
           "--hidden-import", "akhavanlink.client.winnet", "--hidden-import", "akhavanlink.client.demo",
           "--distpath", str(dist), "--workpath", str(work), "--specpath", str(work), str(ROOT / "run_client.py")]
    print(">>", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(ROOT))
    return Path(dist) / "AkhavanLink"


def fetch_wintun(tmp):
    """Official Wintun release -> wintun.dll for this CPU. Verified against the pinned SHA-256."""
    try:
        return winnet.download_wintun(tmp), "verified (sha256 %s)" % winnet.WINTUN_SHA256
    except TunError as e:
        if e.code != "driver_hash":
            raise
        print("WARNING: %s\n         The file came from the official wintun.net over HTTPS; continuing and recording its hash." % e)
        path = winnet.download_wintun(tmp, expected_sha256=None)
        return path, "NOT matching the pinned hash - %s" % e.detail


def write_config(folder, server, extra=None):
    cfg = dict(DEFAULTS)
    cfg["serverUrl"] = server
    cfg.update({k: v for k, v in (extra or {}).items() if v})
    (folder / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assemble(app_dir, out_root, server, wintun_dll, wintun_note, readme, extra=None):
    folder = Path(out_root) / FOLDER
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(app_dir, folder)
    if wintun_dll:
        shutil.copy2(wintun_dll, folder / "wintun.dll")
    write_config(folder, server, extra)
    if readme and Path(readme).is_file():
        (folder / "README-FA.txt").write_text(Path(readme).read_text(encoding="utf-8"), encoding="utf-8-sig")
    info = ["%s %s" % (APP_NAME, VERSION), "Created by %s" % CREATOR, "Server preset: %s" % (server or "(none - set it in the app: Settings)"),
            "Network preset: %s%s%s" % ((extra or {}).get("network") or "AkhavanLAN", "  (password set)" if (extra or {}).get("password") else "  (no password)",
                                         "  (server access key set)" if (extra or {}).get("accessKey") else ""),
            "wintun.dll: %s" % (wintun_note if wintun_dll else "not bundled - the app downloads it on first run, or copy it next to AkhavanLink.exe")]
    (folder / "PACKAGE-INFO.txt").write_text("\n".join(info) + "\n", encoding="utf-8")
    return folder


def zip_folder(folder, zip_path):
    zip_path = Path(zip_path)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(Path(folder).rglob("*")):
            if p.is_file():
                z.write(p, Path(folder.name) / p.relative_to(folder))
    return zip_path


def main():
    ap = argparse.ArgumentParser(description="%s portable package builder - by %s" % (APP_NAME, CREATOR))
    ap.add_argument("--server", default=os.environ.get("AKHAVANLINK_SERVER", ""), help="server address written into config.json")
    ap.add_argument("--network", default=os.environ.get("AKHAVANLINK_NETWORK", ""), help="network name preset (default AkhavanLAN)")
    ap.add_argument("--password", default=os.environ.get("AKHAVANLINK_PASSWORD", ""), help="network password preset")
    ap.add_argument("--access-key", default=os.environ.get("AKHAVANLINK_ACCESS_KEY", ""), help="must equal ACCESS_KEY on the server, if you set one")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--skip-build", action="store_true", help="reuse an existing PyInstaller folder (--app-dir)")
    ap.add_argument("--app-dir", default="", help="PyInstaller output folder (with AkhavanLink.exe)")
    ap.add_argument("--no-wintun", action="store_true", help="do not bundle wintun.dll")
    ap.add_argument("--readme", default=str(ROOT / "scripts" / "portable-README-FA.txt"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    app_dir = Path(a.app_dir) if a.app_dir else None
    if not a.skip_build:
        app_dir = build_exe(out / "pyinstaller", out / "build")
    if app_dir is None or not app_dir.is_dir():
        sys.exit("PyInstaller output folder not found: %s" % app_dir)
    dll, note = (None, "")
    if not a.no_wintun:
        try:
            dll, note = fetch_wintun(out / "wintun-download")
        except Exception as e:  # noqa: BLE001
            print("WARNING: could not bundle wintun.dll (%s). The app will offer to download it on first run." % e)
            (out / "wintun-download").mkdir(exist_ok=True)
    extra = {"network": a.network.strip(), "password": a.password, "accessKey": a.access_key.strip()}
    folder = assemble(app_dir, out, a.server.strip(), dll, note, a.readme, extra)
    z = zip_folder(folder, out / "AkhavanLink-Portable-Windows.zip")
    print("\nDONE: %s  (%.1f MB)\n sha256 %s" % (z, z.stat().st_size / 1048576, hashlib.sha256(z.read_bytes()).hexdigest()))


if __name__ == "__main__":
    main()
