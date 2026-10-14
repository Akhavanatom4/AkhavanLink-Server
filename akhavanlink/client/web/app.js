/* AkhavanLink UI — Created by Alireza Akhavan (علیرضا اخوان) */
(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const root = document.documentElement;
const qs = new URLSearchParams(location.search);

/* ------------------------------------------------------------------ texts */
const I18N = {
  fa: {
    tagline: 'شبکهٔ LAN مجازی برای گیمرها', createdBy: 'ساخته‌شده توسط', language: 'English', sound: 'صدا', logs: 'گزارش‌ها', settings: 'تنظیمات', about: 'درباره',
    openLog: 'پوشهٔ گزارش', lostCore: 'ارتباط با هستهٔ برنامه قطع شد…', linkQuality: 'کیفیت اتصال', pingServer: 'پینگ تا سرور', jitter: 'نوسان', loss: 'افت بسته',
    up: 'ارسال', down: 'دریافت', uptime: 'مدت اتصال', packets: 'بسته‌ها', players: 'بازیکن‌ها', noPlayers: 'هنوز کسی نیست. اسم شبکه و رمزش رو به دوستات بده تا وصل بشن.',
    yourIp: 'آی‌پی مجازی تو', copy: 'کپی', copied: 'کپی شد', you: 'تو', network: 'شبکه', server: 'سرور',
    connect: 'اتصال', cancel: 'لغو', disconnect: 'قطع', retry: 'دوباره', online: 'آنلاین',
    st_idle: 'آفلاین', st_connecting: 'در حال اتصال', st_online: 'آنلاین', st_reconnecting: 'اتصال دوباره', st_error: 'خطا',
    hintIdle: 'برای ورود به شبکهٔ مجازی روی دکمه بزن', hintConnecting: 'در حال وصل شدن به سرور…',
    hintAlone: 'وصلی! دوستات رو دعوت کن؛ اسم شبکه و رمزش رو براشون بفرست',
    hintOnline: 'به شبکه وصلی. آی‌پی مجازی رو توی بازی وارد کن، یا آی‌پی دوستت رو',
    hintReconnecting: 'ارتباط قطع شد؛ تلاش دوباره…',
    fServer: 'آدرس سرور', hServer: 'آدرسی که بعد از دیپلوی روی Deplexo گرفتی؛ مثلاً my-app.deplexo.app', test: 'تست سرور', testing: 'در حال تست…',
    fNetwork: 'نام شبکه', fPassword: 'رمز شبکه (اختیاری)', fNick: 'نام نمایشی', fKey: 'کلید دسترسی سرور (اختیاری)',
    fAuto: 'اتصال خودکار هنگام باز شدن', fFirewall: 'اجازهٔ ترافیک شبکهٔ مجازی در فایروال', fSound: 'جلوه‌های صوتی', fLite: 'جلوهٔ سبک (سیستم ضعیف)',
    advanced: 'تنظیمات پیشرفته', fProxy: 'پروکسی HTTP (اختیاری)', save: 'ذخیره', close: 'بستن', saved: 'تنظیمات ذخیره شد',
    aboutText: 'AkhavanLink یک شبکهٔ LAN مجازی برای گیمرهاست: همه به یک شبکهٔ خصوصی وصل می‌شن و با آی‌پی مجازی همدیگه رو توی بازی پیدا می‌کنن.',
    how1: 'همه یک‌جور تنظیم کنن: آدرس سرور، نام شبکه و رمز.', how2: 'روی دکمهٔ بزرگ بزن تا وصل بشی و آی‌پی مجازی بگیری.',
    how3: 'میزبان بازی رو بسازه؛ بقیه با آی‌پی میزبان (از لیست بازیکن‌ها کپی کن) وصل بشن.', how4: 'اگه بازی «LAN» داره، خودش شبکهٔ AkhavanLink رو پیدا می‌کنه.',
    errorT: 'مشکل در اتصال', needAdminT: 'اجرا با Administrator لازمه', needAdminD: 'برای ساخت کارت شبکهٔ مجازی، برنامه باید با دسترسی Administrator باز بشه.', btnAdmin: 'اجرا با Administrator',
    needDriverT: 'درایور شبکه پیدا نشد', needDriverD: 'فایل wintun.dll کنار برنامه نیست. می‌تونی خودکار دانلودش کنی.', btnDriver: 'دانلود خودکار',
    reconT: 'ارتباط قطع شد', reconD: 'دوباره وصل می‌شم؛ بازی رو نبند.', noServerT: 'سرور تنظیم نشده', noServerD: 'آدرس سرور رو از تنظیمات وارد کن.', btnSettings: 'باز کردن تنظیمات',
    driver_downloading: 'در حال دانلود درایور…', driver_ok: 'درایور آماده شد؛ دوباره وصل شو', driver_fail: 'دانلود درایور ناموفق بود', joined: '{nick} وارد شد', left: '{nick} رفت', testOk: 'سرور در دسترسه',
    err_no_server: 'آدرس سرور تنظیم نشده. از تنظیمات وارد کن.', err_bad_url: 'آدرس سرور درست نیست یا سرور AkhavanLink اونجا نیست.', err_not_server: 'این آدرس سرور AkhavanLink نیست.',
    err_bad_password: 'رمز شبکه اشتباهه.', err_bad_key: 'کلید دسترسی سرور اشتباهه.', err_bad_version: 'نسخهٔ برنامه و سرور با هم نمی‌خونن؛ هر دو رو آپدیت کن.',
    err_bad_network: 'نام شبکه خالیه.', err_network_full: 'این شبکه آی‌پی خالی نداره.', err_too_many_networks: 'سرور به سقف تعداد شبکه‌ها رسیده.',
    err_dns: 'آدرس سرور پیدا نشد؛ اینترنت و آدرس رو چک کن.', err_refused: 'سرور اتصال رو رد کرد؛ آدرس یا پورت رو چک کن.', err_timeout: 'جوابی از سرور نیومد؛ اینترنت یا آدرس رو چک کن.',
    err_tls: 'گواهی امنیتی سرور قبول نشد؛ تاریخ و ساعت ویندوز رو چک کن.', err_server_down: 'سرور فعلاً بالا نیست (شاید در حال راه‌اندازیه)؛ چند لحظهٔ دیگه امتحان کن.',
    err_lost: 'ارتباط با سرور قطع شد.', err_net: 'مشکل شبکه.', err_http: 'پاسخ ناخوشایند از سرور.',
    err_no_admin: 'برای ساخت کارت شبکهٔ مجازی باید برنامه با Administrator اجرا بشه.', err_no_driver: 'فایل wintun.dll کنار برنامه نیست.',
    err_driver_hash: 'فایل دانلودشده با مقدار انتظار نمی‌خونه؛ wintun.dll رو دستی از wintun.net بگیر.', err_driver_download: 'دانلود درایور ناموفق بود.',
    err_tun_failed: 'ساخت کارت شبکهٔ مجازی ناموفق بود. گزارش‌ها رو ببین.', err_other: 'خطای ناشناخته.',
  },
  en: {
    tagline: 'Virtual LAN for gamers', createdBy: 'Created by', language: 'فارسی', sound: 'Sound', logs: 'Logs', settings: 'Settings', about: 'About',
    openLog: 'Open log folder', lostCore: 'Lost contact with the app core…', linkQuality: 'Link quality', pingServer: 'Ping to the server', jitter: 'Jitter', loss: 'Packet loss',
    up: 'Upload', down: 'Download', uptime: 'Connected for', packets: 'Packets', players: 'Players', noPlayers: 'Nobody here yet. Give your friends the network name and password.',
    yourIp: 'Your virtual IP', copy: 'Copy', copied: 'Copied', you: 'You', network: 'Network', server: 'Server',
    connect: 'Connect', cancel: 'Cancel', disconnect: 'Leave', retry: 'Retry', online: 'Online',
    st_idle: 'Offline', st_connecting: 'Connecting', st_online: 'Online', st_reconnecting: 'Reconnecting', st_error: 'Error',
    hintIdle: 'Press the button to join the virtual LAN', hintConnecting: 'Connecting to the server…',
    hintAlone: "You're in! Invite your friends - send them the network name and password",
    hintOnline: "You're on the LAN. Use your virtual IP in the game, or your friend's IP",
    hintReconnecting: 'Connection lost, trying again…',
    fServer: 'Server address', hServer: 'The address you got after deploying on Deplexo, e.g. my-app.deplexo.app', test: 'Test server', testing: 'Testing…',
    fNetwork: 'Network name', fPassword: 'Network password (optional)', fNick: 'Display name', fKey: 'Server access key (optional)',
    fAuto: 'Connect automatically on start', fFirewall: 'Allow virtual-LAN traffic in the firewall', fSound: 'Sound effects', fLite: 'Light effects (slow PC)',
    advanced: 'Advanced', fProxy: 'HTTP proxy (optional)', save: 'Save', close: 'Close', saved: 'Settings saved',
    aboutText: 'AkhavanLink is a virtual LAN for gamers: everyone joins one private network and finds each other in-game with virtual IP addresses.',
    how1: 'Everybody uses the same server address, network name and password.', how2: 'Press the big button to connect and receive a virtual IP.',
    how3: "The host creates the game; others join using the host's IP (copy it from the players list).", how4: 'Games with a LAN tab will find the AkhavanLink network by themselves.',
    errorT: 'Connection problem', needAdminT: 'Administrator rights needed', needAdminD: 'The virtual network adapter can only be created when the app runs as Administrator.', btnAdmin: 'Run as Administrator',
    needDriverT: 'Network driver not found', needDriverD: 'wintun.dll is missing next to the program. You can download it automatically.', btnDriver: 'Download automatically',
    reconT: 'Connection lost', reconD: "Reconnecting - keep your game open.", noServerT: 'No server set', noServerD: 'Enter the server address in Settings.', btnSettings: 'Open settings',
    driver_downloading: 'Downloading the driver…', driver_ok: 'Driver ready - connect again', driver_fail: 'Driver download failed', joined: '{nick} joined', left: '{nick} left', testOk: 'Server reachable',
    err_no_server: 'No server address set. Enter it in Settings.', err_bad_url: "The address is wrong, or there's no AkhavanLink server there.", err_not_server: "That address isn't an AkhavanLink server.",
    err_bad_password: 'Wrong network password.', err_bad_key: 'Wrong server access key.', err_bad_version: 'App and server versions do not match - update both.',
    err_bad_network: 'The network name is empty.', err_network_full: 'This network has no free addresses.', err_too_many_networks: 'The server reached its network limit.',
    err_dns: "The server address can't be found - check your internet and the address.", err_refused: 'The server refused the connection - check address and port.', err_timeout: 'The server did not answer - check your internet and the address.',
    err_tls: "The server's certificate was rejected - check the Windows date and time.", err_server_down: 'The server is not up right now (maybe starting) - try again in a moment.',
    err_lost: 'Connection to the server was lost.', err_net: 'Network problem.', err_http: 'Unexpected answer from the server.',
    err_no_admin: 'Run the app as Administrator to create the virtual adapter.', err_no_driver: 'wintun.dll is missing next to the program.',
    err_driver_hash: 'The downloaded file did not match the expected checksum - get wintun.dll manually from wintun.net.', err_driver_download: 'Driver download failed.',
    err_tun_failed: 'Creating the virtual adapter failed. See the logs.', err_other: 'Unknown error.',
  },
};
let lang = 'fa';
const t = (k, p) => { let s = (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k; if (p) for (const [a, b] of Object.entries(p)) s = s.replace('{' + a + '}', b); return s; };
const errText = (e) => { if (!e) return ''; const k = 'err_' + e.code; return I18N.en[k] ? t(k) : t('err_other'); };
const errDetail = (e) => (e && e.detail && !['no_server', 'bad_password', 'bad_key', 'bad_network'].includes(e.code) ? String(e.detail).slice(0, 160) : '');

/* ------------------------------------------------------------------ state + link to the app core */
const token = qs.get('t') || '';
let S = null, ws = null, logs = [], settingsLoaded = false;
const send = (o) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); };

function connectWS() {
  ws = new WebSocket('ws://' + location.host + '/ui?t=' + encodeURIComponent(token));
  ws.onopen = () => { $('#lost').hidden = true; send({ cmd: 'hello' }); };
  ws.onmessage = (ev) => { try { handle(JSON.parse(ev.data)); } catch (e) { console.error(e); } };
  ws.onclose = () => { $('#lost').hidden = false; setTimeout(connectWS, 1500); };
}
function handle(m) {
  if (m.t === 'state') onState(m);
  else if (m.t === 'log') addLog(m.line, true);
  else if (m.t === 'logs') { logs = []; $('#logbox').textContent = ''; m.lines.forEach((l) => addLog(l, false)); tickLast(); }
  else if (m.t === 'event') { if (m.ev === 'peer_join') { toast(t('joined', { nick: m.nick })); SND.join(); } else if (m.ev === 'peer_leave') { toast(t('left', { nick: m.nick })); SND.leave(); } }
  else if (m.t === 'toast') { const k = m.k; toast(t(k) + (m.detail ? ' - ' + m.detail : '')); }
  else if (m.t === 'testres') showTestResult(m);
}

/* ------------------------------------------------------------------ sound (tiny WebAudio blips) */
let actx = null;
const soundOn = () => !!(S && S.cfg && S.cfg.sound);
function tone(freq, at, dur, type, vol) {
  if (!soundOn()) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === 'suspended') actx.resume();
    const o = actx.createOscillator(), g = actx.createGain(), t0 = actx.currentTime + at;
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(vol, t0 + 0.012); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(actx.destination); o.start(t0); o.stop(t0 + dur + 0.03);
  } catch (e) { /* audio is optional */ }
}
const SND = {
  connect() { [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, i * 0.07, 0.3, 'triangle', 0.05)); },
  disconnect() { [783.99, 659.25, 523.25].forEach((f, i) => tone(f, i * 0.07, 0.26, 'triangle', 0.045)); },
  join() { tone(880, 0, 0.12, 'sine', 0.05); tone(1318.5, 0.08, 0.15, 'sine', 0.04); },
  leave() { tone(440, 0, 0.17, 'sine', 0.045); },
  error() { tone(150, 0, 0.28, 'sawtooth', 0.035); tone(120, 0.13, 0.3, 'sawtooth', 0.035); },
};

/* ------------------------------------------------------------------ helpers */
const QC = { good: '#38f2a2', ok: '#b6f24a', warn: '#ffb83d', bad: '#ff5572', unk: '#5b6894' };
const quality = (ms) => (ms == null ? 'unk' : ms <= 45 ? 'good' : ms <= 90 ? 'ok' : ms <= 150 ? 'warn' : 'bad');
const hueOf = (ip) => { const p = String(ip).split('.').map(Number); return ((p[3] || 0) * 47 + (p[2] || 0) * 13 + 190) % 360; };
const initial = (n) => (Array.from((n || '?').trim())[0] || '?').toUpperCase();
const fmtRate = (b) => (b < 1024 ? b + ' B/s' : b < 1048576 ? (b / 1024).toFixed(1) + ' KB/s' : (b / 1048576).toFixed(2) + ' MB/s');
const fmtTime = (s) => [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map((x) => String(x).padStart(2, '0')).join(':');
const fmtNum = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const icon = (id, cls) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'ic' + (cls ? ' ' + cls : '')); const u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#i-' + id); s.appendChild(u); return s; };
async function copyText(text, flashEl) {
  try { await navigator.clipboard.writeText(text); } catch (e) {
    const ta = mk('textarea'); ta.value = text; ta.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e2) { /* ignore */ } ta.remove();
  }
  toast(t('copied') + ': ' + text);
  if (flashEl) { flashEl.classList.add('copied'); setTimeout(() => flashEl.classList.remove('copied'), 900); }
}
function toast(text) {
  const box = $('#toasts'); const e = mk('div', 'toast cut', text); box.appendChild(e);
  while (box.children.length > 3) box.firstChild.remove();
  setTimeout(() => e.remove(), 3400);
}

/* ------------------------------------------------------------------ rendering: texts, status, panels */
let lastStatus = null, hueBase = 200, hueMode = 'idle', errT = -9, flash = 0, hoverCore = false;
const nodes = new Map();           // ip -> node
let nodeList = [];
const rows = new Map();

function applyLang() {
  root.lang = lang; root.dir = lang === 'fa' ? 'rtl' : 'ltr';
  $$('[data-i18n]').forEach((e) => { e.textContent = t(e.dataset.i18n); });
  $$('[data-i18n-title]').forEach((e) => { e.title = t(e.dataset.i18nTitle); });
  $('#langTxt').textContent = lang === 'fa' ? 'EN' : 'FA';
  $('#how').replaceChildren(...[1, 2, 3, 4].map((i) => mk('li', null, t('how' + i))));
  noticeSig = '';
  if (S) renderAll(true);
}

function onState(m) {
  const prev = S ? S.status : null;
  S = m;
  if (m.cfg && m.cfg.lang && m.cfg.lang !== lang && !langTouched) { lang = m.cfg.lang; applyLang(); }
  if (prev !== m.status) onStatus(prev, m.status);
  renderAll(false);
  if (!settingsLoaded) { settingsLoaded = true; if (!m.cfg.serverUrl && !qs.has('nosplash') && !m.demo) setTimeout(() => openModal('#mSettings'), 2800); }
}
let langTouched = false;

function onStatus(prev, st) {
  root.dataset.state = st; $('#stage').dataset.state = st;
  if (st === 'online') { flash = 1; hueMode = 'online'; if (prev) SND.connect(); }
  else if (st === 'connecting' || st === 'reconnecting') hueMode = 'busy';
  else if (st === 'error') { hueMode = 'error'; errT = performance.now() / 1000; if (prev) SND.error(); }
  else { hueMode = 'idle'; if (prev === 'online' || prev === 'reconnecting') SND.disconnect(); }
  setHue();
}
function setHue() {
  const h = { online: 152, busy: 38, error: 350 }[hueMode];
  if (h != null) { if (S && hueMode === 'online' && S.ping && S.ping.server > 150) hueBase = 40; else hueBase = h; }
  root.style.setProperty('--hue', hueBase);
}
setInterval(() => { if (hueMode === 'idle') { hueBase += 28; root.style.setProperty('--hue', hueBase); } }, 1400);

let noticeSig = '';
function renderAll(force) {
  if (!S) return;
  const st = S.status;
  $('#chipText').textContent = t('st_' + st) + (st === 'reconnecting' && S.retry_in ? ' ' + S.retry_in + 's' : '');
  $('#ver').textContent = 'v' + S.version;
  $('#aboutVer').textContent = 'v' + S.version + (S.demo ? '  (demo)' : '');
  document.title = 'AkhavanLink — ساخته‌شده توسط علیرضا اخوان';
  // sound icon
  $('#btnSound').classList.toggle('off', !S.cfg.sound); $('#btnSound use').setAttribute('href', S.cfg.sound ? '#i-sound' : '#i-mute');
  root.dataset.fx = S.cfg.fx;
  // core button
  const lab = $('#coreLabel'), sub = $('#coreSub');
  if (st === 'idle' || st === 'error') { lab.textContent = st === 'error' ? t('retry') : t('connect'); sub.textContent = ''; }
  else if (st === 'online') { lab.textContent = hoverCore ? t('disconnect') : t('online'); sub.textContent = S.ping.server != null ? Math.round(S.ping.server) + ' ms' : ''; }
  else { lab.textContent = t('cancel'); sub.textContent = st === 'reconnecting' && S.retry_in ? S.retry_in + 's' : ''; }
  // hint + ip
  const hint = $('#hint'); const ipBox = $('#ipBox');
  hint.textContent = st === 'idle' ? t('hintIdle') : st === 'connecting' ? t('hintConnecting') : st === 'reconnecting' ? t('hintReconnecting')
    : st === 'error' ? errText(S.err) : (S.peers.length ? t('hintOnline') : t('hintAlone'));
  hint.style.color = st === 'error' ? 'var(--coral)' : '';
  const showIp = !!S.ip && (st === 'online' || st === 'reconnecting');
  if (ipBox.hidden === showIp) { ipBox.hidden = !showIp; relayoutSoon(); }
  $('#ipText').textContent = S.ip || '0.0.0.0';
  $('#netChip').textContent = showIp ? t('network') + ': ' + S.net : '';
  $('#srvChip').textContent = showIp ? hostOf(S.server) : '';
  // link panel
  const ps = S.ping.server;
  $('#pingNum').textContent = ps == null ? '--' : String(Math.round(ps)); $('#pingNum').classList.toggle('na', ps == null);
  $('.link').dataset.q = quality(ps);
  $('#jitter').textContent = ps == null ? '—' : S.ping.jitter.toFixed(1) + ' ms';
  $('#loss').textContent = ps == null ? '—' : S.ping.loss + '%';
  $('#up').textContent = st === 'online' ? fmtRate(S.traffic.tx) : '—';
  $('#down').textContent = st === 'online' ? fmtRate(S.traffic.rx) : '—';
  $('#uptime').textContent = S.uptime ? fmtTime(S.uptime) : '—';
  $('#pkts').textContent = S.traffic.tx_pkts + S.traffic.rx_pkts ? fmtNum(S.traffic.tx_pkts + S.traffic.rx_pkts) : '—';
  drawTrace();
  renderPlayers();
  syncNodes();
  renderNotice(force);
  setHue();
}
const hostOf = (u) => { try { return new URL(u.includes('://') ? u : 'wss://' + u).host; } catch (e) { return u; } };

function renderPlayers() {
  const list = $('#plist'); const showIp = !!S.ip && (S.status === 'online' || S.status === 'reconnecting');
  const entries = [];
  if (showIp) entries.push({ ip: S.ip, nick: S.nick, rtt: S.ping.server, you: true });
  S.peers.forEach((p) => entries.push(p));
  $('#count').textContent = String(S.peers.length + (showIp ? 1 : 0));
  const keep = new Set(entries.map((e) => e.ip));
  for (const [ip, r] of rows) if (!keep.has(ip)) { r.remove(); rows.delete(ip); }
  entries.forEach((p, idx) => {
    let r = rows.get(p.ip);
    if (!r) {
      r = mk('li', 'prow'); r.dataset.ip = p.ip;
      const hex = mk('div', 'hex sm'); hex.style.setProperty('--h', hueOf(p.ip));
      const who = mk('div', 'who'); const nick = mk('span', 'nick'); const pip = mk('span', 'pip'); who.append(nick, pip);
      const pg = mk('div', 'pg'); const bars = mk('span', 'bars'); for (let i = 0; i < 4; i++) bars.appendChild(mk('i')); pg.append(bars, mk('span', 'ms'));
      const cp = mk('button', 'cp'); cp.type = 'button'; cp.appendChild(icon('copy'));
      cp.addEventListener('click', () => copyText(r.dataset.ip, null)); pip.addEventListener('click', () => copyText(r.dataset.ip, null));
      r.append(hex, who, pg, cp); rows.set(p.ip, r);
    }
    r.classList.toggle('you', !!p.you);
    r.firstChild.textContent = initial(p.nick);
    const nick = r.querySelector('.nick'); nick.textContent = p.nick; nick.dataset.tag = p.you ? t('you') : '';
    r.querySelector('.pip').textContent = p.ip; r.querySelector('.cp').title = t('copy');
    const q = quality(p.rtt); r.dataset.q = q;
    r.querySelector('.ms').textContent = p.rtt == null ? '—' : Math.round(p.rtt) + ' ms';
    const n = { good: 4, ok: 3, warn: 2, bad: 1, unk: 0 }[q];
    r.querySelectorAll('.bars i').forEach((b, i) => b.classList.toggle('on', i < n));
    const at = list.children[idx]; if (at !== r) list.insertBefore(r, at || null);   // keeps the order: you first, then by address
  });
}

function renderNotice(force) {
  let n = null;
  const winOnly = S.platform === 'win32';
  if (S.status === 'error') {
    const c = S.err ? S.err.code : '';
    const acts = [{ label: t('retry'), cmd: 'connect', primary: true }];
    if (c === 'no_admin') acts.unshift({ label: t('btnAdmin'), cmd: 'elevate', primary: true });
    else if (['no_driver', 'driver_hash', 'driver_download'].includes(c) && winOnly) acts.unshift({ label: t('btnDriver'), cmd: 'driver', primary: true });
    else acts.push({ label: t('settings'), fn: () => openModal('#mSettings') });
    n = { c: '350 100% 66%', title: t('errorT'), text: errText(S.err), detail: errDetail(S.err), acts };
  } else if (winOnly && !S.admin && !S.demo) {
    n = { c: '38 100% 62%', title: t('needAdminT'), text: t('needAdminD'), acts: [{ label: t('btnAdmin'), cmd: 'elevate', primary: true }] };
  } else if (winOnly && S.driver === 'missing' && !S.demo) {
    n = { c: '38 100% 62%', title: t('needDriverT'), text: t('needDriverD'), acts: [{ label: t('btnDriver'), cmd: 'driver', primary: true }] };
  } else if (S.status === 'reconnecting') {
    n = { c: '38 100% 62%', title: t('reconT'), text: t('reconD') + (S.retry_in ? ' (' + S.retry_in + 's)' : ''), acts: [] };
  } else if (S.status === 'idle' && !S.cfg.serverUrl) {
    n = { c: '190 100% 62%', title: t('noServerT'), text: t('noServerD'), acts: [{ label: t('btnSettings'), fn: () => openModal('#mSettings'), primary: true }] };
  }
  const box = $('#notice');
  if (!n) { if (!box.hidden) { box.hidden = true; relayoutSoon(); } noticeSig = ''; return; }
  const sig = n.title + '|' + n.acts.map((a) => a.label).join(',') + '|' + lang;
  box.style.setProperty('--nc', n.c);
  $('#noticeTitle').textContent = n.title; $('#noticeText').textContent = n.text; $('#noticeDetail').textContent = n.detail || '';
  if (sig !== noticeSig || force) {
    noticeSig = sig; const acts = $('#noticeActs'); acts.replaceChildren();
    n.acts.forEach((a) => { const b = mk('button', 'btn ' + (a.primary ? 'primary' : 'ghost'), a.label); b.type = 'button'; b.addEventListener('click', () => (a.fn ? a.fn() : send({ cmd: a.cmd }))); acts.appendChild(b); });
  }
  if (box.hidden) { box.hidden = false; relayoutSoon(); }
}

/* ------------------------------------------------------------------ latency trace */
function drawTrace() {
  const c = $('#trace'); const r = c.getBoundingClientRect(); if (!r.width) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  if (c.width !== Math.round(r.width * dpr) || c.height !== Math.round(r.height * dpr)) { c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr); }
  const x = c.getContext('2d'); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, r.width, r.height);
  const w = r.width, h = r.height; const hist = (S && S.ping.hist) || [];
  x.strokeStyle = 'rgba(141,153,192,.14)'; x.lineWidth = 1; x.setLineDash([2, 5]);
  for (let i = 1; i < 4; i++) { const y = Math.round((h * i) / 4) + .5; x.beginPath(); x.moveTo(0, y); x.lineTo(w, y); x.stroke(); }
  x.setLineDash([]);
  if (hist.length < 2) return;
  const max = Math.max(40, Math.ceil(Math.max(...hist) * 1.3 / 10) * 10), N = 60, pad = 6;
  const pts = hist.map((v, i) => [w - (hist.length - 1 - i) * ((w - 8) / (N - 1)) - 4, h - pad - (v / max) * (h - pad * 2)]);
  const col = QC[quality(hist[hist.length - 1])];
  const g = x.createLinearGradient(0, 0, 0, h); g.addColorStop(0, col + '55'); g.addColorStop(1, col + '00');
  x.beginPath(); x.moveTo(pts[0][0], h); pts.forEach((p) => x.lineTo(p[0], p[1])); x.lineTo(pts[pts.length - 1][0], h); x.closePath(); x.fillStyle = g; x.fill();
  x.beginPath(); pts.forEach((p, i) => (i ? x.lineTo(p[0], p[1]) : x.moveTo(p[0], p[1]))); x.strokeStyle = col; x.lineWidth = 2; x.lineJoin = 'round'; x.shadowColor = col; x.shadowBlur = 8; x.stroke(); x.shadowBlur = 0;
  const l = pts[pts.length - 1]; x.beginPath(); x.arc(l[0], l[1], 3.5, 0, 7); x.fillStyle = '#fff'; x.fill();
  x.fillStyle = 'rgba(141,153,192,.7)'; x.font = '11px Bahnschrift, Segoe UI, sans-serif'; x.textAlign = 'left'; x.fillText(max + ' ms', 4, 12);
}

/* ------------------------------------------------------------------ stage: RGB ring, orbiting friends, ping-timed cables */
const stage = $('#stage'), cvs = $('#cables'), cctx = cvs.getContext('2d');
const ringSharp = $('#ringSharp'), ringBloom = $('#ringBloom'), rc = ringSharp.getContext('2d'), bc = ringBloom.getContext('2d');
const G = { w: 0, h: 0, cx: 0, cy: 0, rx: 0, ry: 0, k: 1, dpr: 1 };
const RN = 72, RR = 112, MAXN = 14;
const leds = Array.from({ length: RN }, () => ({ r: 90, g: 100, b: 150, a: 0 }));
let bootP = 0, booting = false, drift = 0, lastT = 0, relayoutT = 0;

function layout() {
  const r = stage.getBoundingClientRect(); if (!r.width || !r.height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  G.w = r.width; G.h = r.height; G.dpr = dpr;
  cvs.width = Math.round(r.width * dpr); cvs.height = Math.round(r.height * dpr);
  const k = clamp(Math.min(r.height / 620, r.width / 540), 0.6, 1.28), R = RR * k;
  const readH = $('#readout').offsetHeight + 16;
  let cy = Math.max(R + 64, r.height * 0.40);
  const ry = clamp(Math.min(r.height - readH - cy - 72, cy - 52), R + 36, 250);
  if (cy - ry < 48) cy = ry + 48;
  const rx = clamp(r.width * 0.40, R + 76, 330);
  Object.assign(G, { cx: r.width / 2, cy, rx, ry, k, R });
  stage.style.setProperty('--cx', G.cx + 'px'); stage.style.setProperty('--cy', cy + 'px'); stage.style.setProperty('--k', k);
  const px = Math.round(280 * dpr * Math.max(1, k));
  if (ringSharp.width !== px) { ringSharp.width = ringBloom.width = px; ringSharp.height = ringBloom.height = px; }
}
const relayoutSoon = () => { cancelAnimationFrame(relayoutT); relayoutT = requestAnimationFrame(layout); };
new ResizeObserver(layout).observe(stage); new ResizeObserver(relayoutSoon).observe($('#readout')); addEventListener('resize', () => { relayoutSoon(); drawTrace(); });

function hsl2rgb(h, s, l) { h = ((h % 360) + 360) % 360; s /= 100; l /= 100; const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l); const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1))); return [f(0) * 255, f(8) * 255, f(4) * 255]; }
function ledTarget(f, tm, st) {
  if (st === 'online') {
    const slow = S && S.ping.server > 150, base = slow ? 40 : 152;
    const [r, g, b] = hsl2rgb(base + 24 * Math.sin(f * 12.566 + tm * 0.8), 96, 58);
    const d = (((f - (tm * 0.32) % 1) % 1) + 1) % 1, rip = Math.exp(-d * 9);
    return [r + 110 * rip, g + 60 * rip, b + 90 * rip, Math.min(1, 0.7 + 0.14 * Math.sin(tm * 1.9 + f * 6.283) + 0.5 * rip + flash)];
  }
  if (st === 'connecting') {
    const d = ((((tm * 0.6) % 1) - f) % 1 + 1) % 1, [r, g, b] = hsl2rgb(38 + 140 * clamp(d * 3, 0, 1), 100, 60);
    return [r, g, b, 0.07 + 0.93 * Math.exp(-d * 7)];
  }
  if (st === 'reconnecting') { const [r, g, b] = hsl2rgb(38, 100, 60); return [r, g, b, 0.2 + 0.6 * (0.5 + 0.5 * Math.sin(tm * 3.2 - f * 4))]; }
  if (st === 'error') {
    const [r, g, b] = hsl2rgb(350, 100, 62), age = tm - errT;
    return [r, g, b, age < 1.2 ? (Math.random() < 0.5 ? 0.2 : 1) : 0.45 + 0.1 * Math.sin(tm * 2)];
  }
  const [r, g, b] = hsl2rgb(f * 360 + tm * 38, 100, 60);
  return [r, g, b, 0.4 + 0.14 * Math.sin(tm * 1.1 + f * 12.566) + (hoverCore ? 0.3 : 0)];
}
function drawRing(tm, dt) {
  const W = ringSharp.width, s = W / 280, st = S ? S.status : 'idle', sm = 1 - Math.exp(-dt * 9);
  rc.clearRect(0, 0, W, W); rc.lineCap = 'round'; rc.lineWidth = 9 * s;
  for (let i = 0; i < RN; i++) {
    const f = i / RN; let [r, g, b, a] = ledTarget(f, tm, st);
    if (bootP < 1) { const lit = clamp((bootP - f) * 16, 0, 1); a *= lit; if (lit > 0 && lit < 1) { r = g = b = 255; a = 0.95; } }
    const L = leds[i]; L.r += (r - L.r) * sm; L.g += (g - L.g) * sm; L.b += (b - L.b) * sm; L.a += (a - L.a) * sm;
    const a0 = -Math.PI / 2 + f * Math.PI * 2;
    rc.strokeStyle = 'rgba(' + Math.min(255, L.r | 0) + ',' + Math.min(255, L.g | 0) + ',' + Math.min(255, L.b | 0) + ',' + clamp(L.a, 0, 1).toFixed(3) + ')';
    rc.beginPath(); rc.arc(W / 2, W / 2, RR * s, a0, a0 + ((Math.PI * 2) / RN) * 0.58); rc.stroke();
  }
  if (root.dataset.fx !== 'lite') { bc.clearRect(0, 0, W, W); bc.drawImage(ringSharp, 0, 0); }
}

function makeNode(p) {
  const e = mk('div', 'node'); const hex = mk('div', 'hex'); hex.style.setProperty('--h', hueOf(p.ip));
  const tag = mk('div', 'tag'); tag.append(mk('b'), mk('span'));
  e.append(hex, tag); e.style.opacity = 0; $('#nodes').appendChild(e);
  e.addEventListener('click', () => copyText(p.ip, null));
  return { el: e, ip: p.ip, ang: null, enter: 0, seed: Math.random(), rtt: null, x: 0, y: 0 };
}
function syncNodes() {
  const peers = S ? S.peers : []; const shown = peers.slice(0, MAXN), seen = new Set();
  nodeList = [];
  shown.forEach((p) => {
    seen.add(p.ip); let nd = nodes.get(p.ip); if (!nd) { nd = makeNode(p); nodes.set(p.ip, nd); }
    nd.rtt = p.rtt; nd.el.dataset.q = quality(p.rtt); nd.el.title = p.nick + '  ' + p.ip;
    nd.el.firstChild.textContent = initial(p.nick); nd.el.querySelector('b').textContent = p.nick;
    nd.el.querySelector('span').textContent = p.rtt == null ? '—' : Math.round(p.rtt) + ' ms';
    nodeList.push(nd);
  });
  const extra = peers.length - shown.length;
  if (extra > 0) {
    seen.add('+'); let nd = nodes.get('+'); if (!nd) { nd = makeNode({ ip: '+' }); nd.el.classList.add('more'); nodes.set('+', nd); }
    nd.rtt = null; nd.el.firstChild.textContent = '+' + extra; nd.el.querySelector('b').textContent = ''; nd.el.querySelector('span').textContent = ''; nodeList.push(nd);
  }
  for (const [ip, nd] of nodes) if (!seen.has(ip)) { nodes.delete(ip); nd.el.style.transition = 'opacity .4s'; nd.el.style.opacity = 0; setTimeout(() => nd.el.remove(), 450); }
}
const angDiff = (a, b) => { let d = (a - b) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2; return d; };
const easeOutBack = (x) => { const c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };

function drawStage(tm, dt) {
  const w = G.w, h = G.h; if (!w) return;
  cctx.setTransform(G.dpr, 0, 0, G.dpr, 0, 0); cctx.clearRect(0, 0, w, h);
  const st = S ? S.status : 'idle', live = st === 'online';
  cctx.save(); cctx.strokeStyle = 'rgba(141,153,192,.10)'; cctx.setLineDash([2, 7]); cctx.lineWidth = 1.2;
  cctx.beginPath(); cctx.ellipse(G.cx, G.cy, G.rx, G.ry, 0, 0, Math.PI * 2); cctx.stroke(); cctx.restore();
  drift += dt * 0.03; const n = nodeList.length;
  nodeList.forEach((nd, i) => {
    const target = -Math.PI / 2 + (n ? (i / n) * Math.PI * 2 : 0) + drift;
    nd.ang = nd.ang == null ? target : nd.ang + angDiff(target, nd.ang) * (1 - Math.exp(-dt * 5));
    nd.enter = Math.min(1, nd.enter + dt / 0.8);
    const e = easeOutBack(nd.enter), mult = lerp(1.55, 1, e), ca = Math.cos(nd.ang), sa = Math.sin(nd.ang), depth = (sa + 1) / 2;
    nd.x = G.cx + G.rx * ca * mult; nd.y = G.cy + G.ry * sa * mult; nd.depth = depth;
    const sc = (0.84 + 0.26 * depth) * clamp(G.k, 0.82, 1.05);
    nd.sc = sc; nd.el.style.transform = 'translate(' + nd.x.toFixed(1) + 'px,' + nd.y.toFixed(1) + 'px) scale(' + sc.toFixed(3) + ')';
    nd.el.style.opacity = ((0.66 + 0.34 * depth) * clamp(nd.enter * 2, 0, 1)).toFixed(3); nd.el.style.zIndex = 2 + Math.round(depth * 10);
  });
  cctx.globalCompositeOperation = 'lighter';
  nodeList.forEach((nd) => {
    if (nd.ip === '+') return;
    const dx = nd.x - G.cx, dy = nd.y - G.cy, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
    const x0 = G.cx + ux * (G.R + 4), y0 = G.cy + uy * (G.R + 4), nr = 30 * nd.sc, x1 = nd.x - ux * nr, y1 = nd.y - uy * nr - 4;
    const col = QC[quality(nd.rtt)], alpha = live ? 1 : 0.3;
    const g = cctx.createLinearGradient(x0, y0, x1, y1); g.addColorStop(0, col + '10'); g.addColorStop(1, col + (live ? '66' : '22'));
    cctx.strokeStyle = g; cctx.lineWidth = 1.6; cctx.beginPath(); cctx.moveTo(x0, y0); cctx.lineTo(x1, y1); cctx.stroke();
    if (!live) return;
    const T = clamp(0.8 + (nd.rtt == null ? 300 : nd.rtt) / 70, 0.9, 4.2), ph = ((tm / T + nd.seed) % 1), pos = ph < 0.5 ? ph * 2 : 2 - ph * 2;
    const dir = ph < 0.5 ? 1 : -1;
    for (let j = 0; j < 7; j++) {                      // short comet tail
      const q = clamp(pos - dir * j * 0.022, 0, 1), px = lerp(x0, x1, q), py = lerp(y0, y1, q), rr = (j === 0 ? 4.2 : 3.2 - j * 0.35) * alpha;
      if (rr <= 0) continue; cctx.fillStyle = col + (j === 0 ? 'ff' : Math.max(10, 90 - j * 13).toString(16).padStart(2, '0')); cctx.beginPath(); cctx.arc(px, py, rr, 0, 7); cctx.fill();
    }
    const hx = lerp(x0, x1, pos), hy = lerp(y0, y1, pos), rg = cctx.createRadialGradient(hx, hy, 0, hx, hy, 14); rg.addColorStop(0, col + '88'); rg.addColorStop(1, col + '00');
    cctx.fillStyle = rg; cctx.beginPath(); cctx.arc(hx, hy, 14, 0, 7); cctx.fill();
  });
  cctx.globalCompositeOperation = 'source-over';
}
function frame(ts) {
  requestAnimationFrame(frame); if (document.hidden) return;
  const tm = ts / 1000, dt = Math.min(0.1, tm - lastT || 0.016); lastT = tm;
  if (booting && bootP < 1) bootP = Math.min(1, bootP + dt / 1.3);
  flash = Math.max(0, flash - dt * 1.1);
  drawRing(tm, dt); drawStage(tm, dt);
}

/* ------------------------------------------------------------------ log console */
function addLog(line, scroll) {
  logs.push(line); if (logs.length > 300) logs.shift();
  const box = $('#logbox'); const row = mk('div', 'l ' + line.lv); row.append(mk('span', null, line.ts), mk('span', null, line.msg)); box.appendChild(row);
  while (box.children.length > 300) box.firstChild.remove();
  if (scroll) { box.scrollTop = box.scrollHeight; tickLast(); }
}
function tickLast() { const l = logs[logs.length - 1]; $('#tick').textContent = l ? l.ts + '  ' + l.msg : ''; }

/* ------------------------------------------------------------------ modals + settings */
function openModal(sel) {
  const m = $(sel); if (!m.hidden) return;
  if (sel === '#mSettings') fillSettings();
  m.hidden = false; requestAnimationFrame(() => m.classList.add('show'));
  const first = m.querySelector('input'); if (first && sel === '#mSettings') setTimeout(() => first.focus(), 60);
}
function closeModals() { $$('.modal').forEach((m) => { m.classList.remove('show'); setTimeout(() => { if (!m.classList.contains('show')) m.hidden = true; }, 180); }); }
function fillSettings() {
  if (!S) return; const c = S.cfg;
  $('#fServer').value = c.serverUrl; $('#fNetwork').value = c.network; $('#fPassword').value = c.password; $('#fNick').value = c.nickname; $('#fKey').value = c.accessKey;
  $('#fAuto').checked = c.autoConnect; $('#fFirewall').checked = c.firewall; $('#fSound').checked = c.sound; $('#fLite').checked = c.fx === 'lite';
  $('#fProxy').value = c.proxy; $('#fMtu').value = c.mtu; $('#testRes').textContent = ''; $('#testRes').className = 'testres';
}
function saveSettings() {
  send({ cmd: 'save', cfg: { serverUrl: $('#fServer').value, network: $('#fNetwork').value, password: $('#fPassword').value, nickname: $('#fNick').value, accessKey: $('#fKey').value,
    autoConnect: $('#fAuto').checked, firewall: $('#fFirewall').checked, sound: $('#fSound').checked, fx: $('#fLite').checked ? 'lite' : 'full', proxy: $('#fProxy').value, mtu: Number($('#fMtu').value) || 1400 } });
  closeModals();
}
function showTestResult(m) {
  const r = $('#testRes');
  if (m.ok) { r.className = 'testres ok'; r.textContent = '✓ ' + t('testOk') + (m.ms != null ? ' - ' + Math.round(m.ms) + ' ms' : '') + (m.proto_ok === false ? ' (!)' : ''); }
  else { r.className = 'testres bad'; r.textContent = '✕ ' + errText({ code: m.code, detail: m.detail }) + (errDetail({ code: m.code, detail: m.detail }) ? '  [' + errDetail({ code: m.code, detail: m.detail }) + ']' : ''); }
}

/* ------------------------------------------------------------------ wiring */
$('#btnConnect').addEventListener('click', () => {
  if (!S) return; const st = S.status;
  if (st === 'idle' || st === 'error') { if (!S.cfg.serverUrl) openModal('#mSettings'); else send({ cmd: 'connect' }); }
  else send({ cmd: 'disconnect' });
});
$('#btnConnect').addEventListener('mouseenter', () => { hoverCore = true; if (S) renderAll(false); });
$('#btnConnect').addEventListener('mouseleave', () => { hoverCore = false; if (S) renderAll(false); });
$('#ipText').addEventListener('click', () => S && S.ip && copyText(S.ip, $('#ipText')));
$('#btnSettings').addEventListener('click', () => openModal('#mSettings'));
$('#btnAbout').addEventListener('click', () => openModal('#mAbout'));
$('#btnSave').addEventListener('click', saveSettings);
$('#btnTest').addEventListener('click', () => { $('#testRes').className = 'testres'; $('#testRes').textContent = t('testing'); send({ cmd: 'test', url: $('#fServer').value, key: $('#fKey').value, proxy: $('#fProxy').value }); });
$('#btnEye').addEventListener('click', () => { const i = $('#fPassword'); i.type = i.type === 'password' ? 'text' : 'password'; });
$('#btnLang').addEventListener('click', () => { lang = lang === 'fa' ? 'en' : 'fa'; langTouched = true; send({ cmd: 'save', quiet: true, cfg: { lang } }); applyLang(); });
$('#btnSound').addEventListener('click', () => { if (S) { const on = !S.cfg.sound; S.cfg.sound = on; send({ cmd: 'save', quiet: true, cfg: { sound: on } }); renderAll(false); if (on) SND.join(); } });
$('#btnLog').addEventListener('click', () => { const c = $('#console'); c.hidden = !c.hidden; if (!c.hidden) $('#logbox').scrollTop = $('#logbox').scrollHeight; });
$('#btnCloseLog').addEventListener('click', () => { $('#console').hidden = true; });
$('#btnOpenLog').addEventListener('click', () => send({ cmd: 'openlog' }));
$$('[data-close]').forEach((b) => b.addEventListener('click', closeModals));
$$('.modal').forEach((m) => m.addEventListener('mousedown', (e) => { if (e.target === m) closeModals(); }));
addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModals(); if (e.key === 'Enter' && !$('#mSettings').hidden && e.target.tagName === 'INPUT') saveSettings(); });
addEventListener('beforeunload', (e) => { if (S && (S.status === 'online' || S.status === 'reconnecting')) { e.preventDefault(); e.returnValue = ''; } });

/* ------------------------------------------------------------------ start: splash, then the ring ignites */
applyLang(); connectWS(); requestAnimationFrame(frame);
const skip = qs.has('nosplash');
setTimeout(() => { $('#splash').classList.add('out'); booting = true; }, skip ? 30 : 2400);
if (skip) $('#splash').style.display = 'none';
})();
