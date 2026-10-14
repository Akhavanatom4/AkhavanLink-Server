// AkhavanLink — Created by Alireza Akhavan
// Interop test: talks to a running relay server using Node's built-in (independent) WebSocket client.
//   node tests/node_interop.js 18765
const port = process.argv[2] || 18765;
const URL_ = `ws://127.0.0.1:${port}/ws`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const ok = (c, m) => { if (!c) { failures++; console.log("  FAIL:", m); } else console.log("  ok:", m); };

function client(name) {
  return new Promise((resolve, reject) => {
    const w = new WebSocket(URL_);
    w.binaryType = "arraybuffer";
    const c = { w, name, texts: [], bins: [], waiters: [] };
    w.onmessage = (ev) => {
      if (typeof ev.data === "string") c.texts.push(JSON.parse(ev.data)); else c.bins.push(new Uint8Array(ev.data));
      for (const f of c.waiters.splice(0)) f();
    };
    w.onopen = () => resolve(c);
    w.onerror = (e) => reject(new Error("ws error " + name));
    c.closed = new Promise((r) => (w.onclose = (e) => r(e)));
  });
}
async function waitFor(c, pred, ms = 1500) {
  const t0 = Date.now();
  for (;;) {
    const m = c.texts.find(pred);
    if (m) return m;
    if (Date.now() - t0 > ms) return null;
    await new Promise((r) => { c.waiters.push(r); setTimeout(r, 50); });
  }
}
function ipv4(src, dst, payloadLen = 8) {
  const p = new Uint8Array(20 + payloadLen);
  p[0] = 0x45; p[2] = (p.length >> 8) & 255; p[3] = p.length & 255; p[8] = 64; p[9] = 17;
  src.split(".").forEach((v, i) => (p[12 + i] = +v));
  dst.split(".").forEach((v, i) => (p[16 + i] = +v));
  for (let i = 20; i < p.length; i++) p[i] = i & 255;
  return p;
}
const eq = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
const join = (c, id, net = "InteropNet", pw = "", nick = c.name) =>
  c.w.send(JSON.stringify({ t: "join", v: 1, net, pw, id, nick }));

(async () => {
  console.log("1. hello + join");
  const A = await client("Ali"), B = await client("Sara");
  ok(await waitFor(A, (m) => m.t === "hello" && m.app === "AkhavanLink" && m.creator === "Alireza Akhavan"), "hello carries app + creator");
  join(A, "a".repeat(32));
  const wa = await waitFor(A, (m) => m.t === "welcome");
  ok(wa && wa.ip === "10.77.0.2" && wa.prefix === 16 && wa.mask === "255.255.0.0", "A welcomed with 10.77.0.2/16");
  join(B, "b".repeat(32), "interopnet");            // network names are case-insensitive
  const wb = await waitFor(B, (m) => m.t === "welcome");
  ok(wb && wb.ip === "10.77.0.3" && wb.peers.length === 1 && wb.peers[0].ip === "10.77.0.2", "B welcomed with 10.77.0.3 and sees A");
  ok(await waitFor(A, (m) => m.t === "peer+" && m.p.ip === "10.77.0.3" && m.p.nick === "Sara"), "A notified about B");

  console.log("2. unicast / broadcast / multicast / spoof");
  const u = ipv4("10.77.0.2", "10.77.0.3"); A.w.send(u); await sleep(200);
  ok(B.bins.length === 1 && eq(B.bins[0], u), "unicast A->B delivered unchanged");
  ok(A.bins.length === 0, "sender does not get its own packet");
  const b = ipv4("10.77.0.2", "10.77.255.255"); A.w.send(b); await sleep(200);
  ok(B.bins.length === 2 && eq(B.bins[1], b), "directed broadcast flooded to B");
  const lb = ipv4("10.77.0.3", "255.255.255.255"); B.w.send(lb); await sleep(200);
  ok(A.bins.length === 1 && eq(A.bins[0], lb), "limited broadcast B->A");
  const mc = ipv4("10.77.0.2", "224.0.2.60"); A.w.send(mc); await sleep(200);
  ok(B.bins.length === 3 && eq(B.bins[2], mc), "multicast flooded");
  A.w.send(ipv4("10.77.0.9", "10.77.0.3")); await sleep(200);
  ok(B.bins.length === 3, "spoofed source address dropped");
  A.w.send(ipv4("10.77.0.2", "10.77.0.77")); await sleep(150);
  ok(B.bins.length === 3, "packet to an offline address goes nowhere");
  const big = ipv4("10.77.0.2", "10.77.0.3", 60000); A.w.send(big); await sleep(300);
  ok(B.bins.length === 4 && eq(B.bins[3], big), "60 KB packet (64-bit length frame) delivered");

  console.log("3. ping / peer ping relay / nick");
  A.w.send(JSON.stringify({ t: "ping", n: 5 }));
  ok(await waitFor(A, (m) => m.t === "pong" && m.n === 5), "server pong");
  A.w.send(JSON.stringify({ t: "pp", to: "10.77.0.3", n: 77 }));
  const pp = await waitFor(B, (m) => m.t === "pp" && m.from === "10.77.0.2" && m.n === 77);
  ok(pp, "peer ping reaches B");
  B.w.send(JSON.stringify({ t: "pr", to: "10.77.0.2", n: 77 }));
  ok(await waitFor(A, (m) => m.t === "pr" && m.from === "10.77.0.3" && m.n === 77), "peer pong returns to A");
  B.w.send(JSON.stringify({ t: "nick", nick: "Sara \u200c Jaan" }));
  ok(await waitFor(A, (m) => m.t === "peer~" && m.p.nick.includes("Jaan")), "nick change broadcast");

  console.log("4. wrong password / wrong version / bad key");
  const C = await client("Eve"); join(C, "c".repeat(32), "InteropNet", "nope");
  const er = await waitFor(C, (m) => m.t === "error");
  ok(er && er.code === "bad_password", "wrong password rejected");
  const d = await client("Dan"); d.w.send(JSON.stringify({ t: "join", v: 99, net: "x", id: "d".repeat(32) }));
  ok((await waitFor(d, (m) => m.t === "error")).code === "bad_version", "wrong protocol version rejected");

  console.log("5. reconnect keeps the IP, old connection replaced");
  const A2 = await client("Ali"); join(A2, "a".repeat(32));
  const w2 = await waitFor(A2, (m) => m.t === "welcome");
  ok(w2 && w2.ip === "10.77.0.2", "same client id gets the same address");
  const ce = await Promise.race([A.closed, sleep(1500).then(() => null)]);
  ok(ce && ce.code === 4001, "stale duplicate connection was closed (4001)");
  A2.w.send(ipv4("10.77.0.2", "10.77.0.3")); await sleep(200);
  ok(B.bins.length === 5, "traffic works after reconnect");

  console.log("6. leave notification");
  A2.w.close(); 
  ok(await waitFor(B, (m) => m.t === "peer-" && m.ip === "10.77.0.2"), "peer- sent when A leaves");
  B.w.close(); C.w.close(); d.w.close();
  console.log(failures ? `\n${failures} FAILED` : "\nALL OK");
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
