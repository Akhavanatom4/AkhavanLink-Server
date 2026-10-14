# AkhavanLink — شبکهٔ LAN مجازی برای گیمرها

**ساخته‌شده توسط علیرضا اخوان** · *Created by Alireza Akhavan*

AkhavanLink مثل Hamachi یا Radmin VPN کار می‌کنه: همهٔ دوستات به یک شبکهٔ خصوصی وصل می‌شن، هر نفر یک **آی‌پی مجازی** (مثل `10.77.0.2`) می‌گیره و بازی‌ها همدیگه رو مثل یک LAN واقعی پیدا می‌کنن. تعداد بازیکن‌ها محدودیت نداره (پیش‌فرض بیش از ۶۵ هزار آدرس).

| بخش | چیه | کجا اجرا می‌شه |
|---|---|---|
| **سرور** (همین ریپو + `Dockerfile`) | رلهٔ بسته‌ها + صفحهٔ وضعیت | Deplexo (Docker) |
| **کلاینت ویندوز پرتابل** | `AkhavanLink.exe` + `wintun.dll` + `config.json` | کامپیوتر تو و دوستات |

## راه‌اندازی در ۴ مرحله

### ۱) آپلود روی GitHub
یک ریپوی جدید بساز (مثلاً `akhavanlink`) و **همهٔ فایل‌ها و پوشه‌های** این پروژه رو توش آپلود کن (پوشهٔ `.github` و فایل `Dockerfile` حتماً باید ریشهٔ ریپو باشن).

### ۲) دیپلوی روی Deplexo
1. توی Deplexo پروژهٔ جدید از روی همین ریپوی GitHub بساز و روش **Docker / Dockerfile** رو انتخاب کن.
2. پورت سرویس: **8080** (سرور از متغیر `PORT` هم پیروی می‌کنه؛ اگه Deplexo خودش `PORT` می‌ده، همون استفاده می‌شه).
3. (پیشنهادی) متغیر محیطی `ACCESS_KEY` رو با یک کلید دلخواه بذار تا فقط کلاینت‌های خودت بتونن از سرورت استفاده کنن.
4. Deploy بزن. وقتی بالا اومد، آدرس سرویس (مثلاً `https://my-app.deplexo.app`) رو توی مرورگر باز کن: صفحهٔ AkhavanLink با **آدرس سرور** و دکمهٔ **«تست WebSocket»** میاد. تست باید سبز بشه.

> سرور باید WebSocket رو از طریق پروکسی هاستینگ رد کنه. تستِ همین صفحه بهت می‌گه اینطوره یا نه.

### ۳) ساخت نسخهٔ پرتابل (فایل exe)
**روش الف — خودکار با GitHub Actions (پیشنهادی):** ریپو → تب **Actions** → **Build Windows portable** → **Run workflow** → آدرس سرورت رو بنویس (مثلاً `my-app.deplexo.app`) → بعد از ~۵ دقیقه از پایین صفحهٔ اجرا فایل **AkhavanLink-Portable-Windows** رو دانلود کن.
(می‌تونی یک‌بار برای همیشه توی *Settings → Secrets and variables → Actions* این‌ها رو بذاری: Variables: `AKHAVANLINK_SERVER`، `AKHAVANLINK_NETWORK` — Secrets: `AKHAVANLINK_PASSWORD`، `AKHAVANLINK_ACCESS_KEY`.)

**روش ب — روی کامپیوتر خودت:** پایتون ۳.۹+ نصب کن و `build-windows.bat` رو اجرا کن؛ خروجی: `dist\AkhavanLink-Portable-Windows.zip`.

زیپ شامل `AkhavanLink.exe`، پوشهٔ فایل‌های لازم، `wintun.dll`، `config.json` (با آدرس سرور تو) و راهنمای فارسی هست.

### ۴) استفاده
زیپ رو برای دوستات بفرست. Extract → `AkhavanLink.exe` → **Yes** (Administrator) → دکمهٔ بزرگ اتصال. همه نام شبکه و رمز یکسان داشته باشن؛ آی‌پی هر نفر توی لیست بازیکن‌ها هست. برای تست: `ping 10.77.0.2`.

## تنظیمات سرور (متغیرهای محیطی)
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `PORT` | `8080` | پورتی که سرور گوش می‌ده |
| `ACCESS_KEY` | خالی | اگه بذاری، کلاینت باید همین مقدار رو در `accessKey` داشته باشه |
| `VNET_CIDR` | `10.77.0.0/16` | محدودهٔ آی‌پی مجازی (IPv4، بین `/8` تا `/28`). اگه با شبکهٔ خونه‌ات تداخل داشت عوضش کن |
| `MAX_PLAYERS_PER_NETWORK` | `0` | `0` = نامحدود |
| `MAX_NETWORKS` | `0` | `0` = نامحدود |
| `NETWORK_TTL_HOURS` | `6` | یک شبکهٔ خالی بعد از این مدت پاک می‌شه (رمزش هم آزاد می‌شه) |
| `IP_RESERVE_HOURS` | `12` | آی‌پی هر نفر بعد از رفتنش این‌قدر برای خودش نگه داشته می‌شه |
| `VNET_MTU` | `1400` | MTU کارت مجازی |

## تنظیمات کلاینت (`config.json` کنار exe — از داخل برنامه هم قابل تغییره)
`serverUrl` (آدرس سرور)، `network`، `password`، `nickname`، `accessKey`، `firewall` (اجازهٔ ترافیک شبکهٔ مجازی در فایروال ویندوز)، `proxy` (پروکسی HTTP اختیاری)، `mtu`، `autoConnect`، `lang` (`fa`/`en`)، `sound`، `fx` (`full`/`lite`).

## عیب‌یابی
* **تستِ صفحهٔ سرور قرمز شد** → WebSocket روی هاستینگ فعال نیست یا پورت اشتباهه.
* **«wintun.dll پیدا نشد»** → دکمهٔ دانلود خودکار توی برنامه، یا فایل رو از [wintun.net](https://www.wintun.net) بگیر و کنار exe بذار.
* **اجرای برنامه خطای SmartScreen داد** → More info → Run anyway (برنامه امضای دیجیتال پولی نداره).
* **تشخیص مشکل روی ویندوز:** `AkhavanLink.exe --selftest` → فایل `selftest.txt` ساخته می‌شه. لاگ‌ها: پوشهٔ `logs`.
* **پیش‌نمایش ظاهر بدون سرور و بدون درایور:** `python -m akhavanlink.client --demo` (بازیکن‌های شبیه‌سازی‌شده).

---

# English

**AkhavanLink — a virtual LAN for gamers. Created by Alireza Akhavan (علیرضا اخوان).**

Everyone joins one private network through a relay server, gets a virtual IPv4 address (default `10.77.0.0/16`) on a virtual network adapter, and games see each other like on a real LAN (direct IP, directed/limited broadcast and multicast are all forwarded).

```
 Windows PC  ──┐                                     ┌── Windows PC
 AkhavanLink   │  wss://your-app.deplexo.app/ws      │   AkhavanLink
 Wintun adapter├──────────►  relay server  ◄─────────┤   Wintun adapter
 10.77.0.2     │          (Docker, Python)           │   10.77.0.3
```

* **Server** (`akhavanlink/server`, `Dockerfile`): pure-Python asyncio, zero dependencies. One WebSocket per player; IPv4 packets are binary frames, control messages are JSON text frames. The server checks the source address (no spoofing), routes unicast by destination, and floods broadcast/multicast. Congested receivers drop packets instead of queueing them (UDP semantics = no lag build-up). Measured on loopback: 0.15 ms median forwarding delay, >50k packets/s (`python tests/bench_relay.py`).
* **Client** (`akhavanlink/client`): asyncio engine + [Wintun](https://www.wintun.net) adapter (`ctypes`), set up with `netsh` (lowest interface metric so games prefer it for LAN broadcast, MTU, firewall rule). The UI is a local web page (`127.0.0.1`, random port, per-launch token) shown in an Edge/Chrome app window.
* **Addresses:** first free address from `.0.2`; stable per client id, honoured as a preferred address after server restarts; per-network pools; network name + password (checked while the network exists).

**Latency:** all traffic goes through the server, so your ping ≈ round trip to the server. Put the server close to the players. A direct peer-to-peer path (UDP hole punching) is not part of this version.

**Limitations (honest list):** Windows 10/11 for the client (the relay runs anywhere with Python 3.9+/Docker); IPv4 only; TCP-based transport means games that tunnel their own TCP can show head-of-line blocking on very lossy links; the Windows exe is not code-signed, so SmartScreen warns once.

## Development
```bash
python -m unittest discover -s tests -t . -v      # 27 tests: codec, relay, engine, UI security, packager ...
python -m akhavanlink.server --port 8080          # run the relay
python -m akhavanlink.client --demo               # preview the UI with simulated players (any OS)
node tests/node_interop.js 8080                   # independent WebSocket client check against a running server
python tests/bench_relay.py                       # relay micro-benchmark
python scripts/make_portable.py --server my-app.deplexo.app   # Windows: build the portable package
```
