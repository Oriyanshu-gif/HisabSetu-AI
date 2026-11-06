// Records the HisabSetu AI demo segment by segment with headless Edge.
// Each segment gets its own browser + fake microphone WAV, so the real
// MediaRecorder -> /api/stt -> Gnani Prisma -> parser path runs for real.
//
// Writes demo/raw/<segment>/frames/*.jpg + frames.json + events.json
import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8000/";
const OUT = resolve(ROOT, "demo/raw");
const AUDIO = process.env.AUDIO_DIR ? resolve(ROOT, process.env.AUDIO_DIR) : resolve(ROOT, "demo/audio/voice");
const VIEWPORT = { width: 1440, height: 810 };
const SCALE = 2;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function waitForHttp(url, timeoutMs = 20000) {
  const started = Date.now();
  return (async () => {
    while (Date.now() - started < timeoutMs) {
      try {
        const res = await fetch(url);
        if (res.ok) return await res.json();
      } catch { /* not up yet */ }
      await sleep(200);
    }
    throw new Error(`timeout waiting for ${url}`);
  })();
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const listeners = new Set();
  const ready = new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
      return;
    }
    for (const fn of listeners) fn(msg);
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  return { ws, ready, send, on: (fn) => listeners.add(fn) };
}

function captionScript() {
  const style = document.createElement("style");
  style.textContent = `
    #demo-caption {
      position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%);
      max-width: 1000px; width: max-content; z-index: 9999;
      padding: 13px 24px; border-radius: 14px; text-align: center;
      font: 500 21px/1.45 "Segoe UI", system-ui, sans-serif;
      color: #f6faf8; background: rgba(6, 14, 11, 0.86);
      border: 1px solid rgba(134, 239, 172, 0.22);
      box-shadow: 0 18px 40px -18px rgba(0,0,0,.8);
      opacity: 0; transition: opacity .3s ease; pointer-events: none;
    }
    #demo-caption.on { opacity: 1; }
    #demo-brand {
      position: fixed; right: 18px; top: 16px; z-index: 9999;
      font: 700 13px/1 "Segoe UI", system-ui, sans-serif; letter-spacing: .08em;
      color: #86efac; background: rgba(6, 14, 11, 0.7);
      border: 1px solid rgba(134, 239, 172, 0.25); border-radius: 999px;
      padding: 7px 12px; pointer-events: none; opacity: .9;
    }
  `;
  document.head.appendChild(style);
  const hide = document.createElement("style");
  hide.textContent = '[class*="toast"], [id*="toast"] { display: none !important; }';
  document.head.appendChild(hide);
  const caption = document.createElement("div");
  caption.id = "demo-caption";
  document.body.appendChild(caption);
  const brand = document.createElement("div");
  brand.id = "demo-brand";
  brand.textContent = "#GnaniAI";
  document.body.appendChild(brand);
  window.__demoCaption = (text) => {
    const el = document.getElementById("demo-caption");
    if (!el) return;
    if (!text) { el.classList.remove("on"); return; }
    el.textContent = text;
    el.classList.add("on");
  };
  window.__demoScroll = (y, ms = 600) => new Promise((done) => {
    if (ms <= 0) { window.scrollTo(0, y); done(true); return; }
    const start = window.scrollY;
    const delta = y - start;
    const t0 = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - t0) / ms);
      const eased = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      window.scrollTo(0, start + delta * eased);
      if (p < 1) requestAnimationFrame(step); else done(true);
    };
    requestAnimationFrame(step);
  });
  window.__demoScrollToEl = (selector, offset = 90, ms = 700) => {
    const el = document.querySelector(selector);
    if (!el) return -1;
    const y = el.getBoundingClientRect().top + window.scrollY - offset;
    return window.__demoScroll(Math.max(0, y), ms).then(() => Math.round(window.scrollY));
  };
}

async function runSegment(segment, index) {
  const dir = resolve(OUT, segment.name);
  const framesDir = resolve(dir, "frames");
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(framesDir, { recursive: true });

  const port = 9360 + index;
  const profile = resolve(ROOT, `.tmp-demo/${segment.name}`);
  rmSync(profile, { recursive: true, force: true });
  mkdirSync(profile, { recursive: true });

  const wav = segment.wav ? resolve(AUDIO, `${segment.wav}.wav`) : resolve(ROOT, "demo/audio/silence.wav");
  const child = spawn(EDGE, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    `--force-device-scale-factor=${SCALE}`,
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${wav}`,
    "--autoplay-policy=no-user-gesture-required",
    "--no-first-run", "--no-default-browser-check",
    "about:blank",
  ], { stdio: "ignore" });

  const version = await waitForHttp(`http://127.0.0.1:${port}/json/version`);
  const browser = connect(version.webSocketDebuggerUrl);
  await browser.ready;
  const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  const target = pages.find((t) => t.type === "page");
  const page = connect(target.webSocketDebuggerUrl);
  await page.ready;

  const events = [];
  const frames = [];
  let t0 = 0;
  const now = () => (Date.now() - t0) / 1000;
  const event = (name, extra = {}) => {
    events.push({ name, t: Number(now().toFixed(3)), ...extra });
    console.log(`  [${segment.name}] ${name} @ ${now().toFixed(2)}s`);
  };
  const evaluate = async (expression) => {
    const res = await page.send("Runtime.evaluate", {
      expression, returnByValue: true, awaitPromise: true,
    });
    if (res.exceptionDetails) throw new Error(res.exceptionDetails.text + " :: " + expression.slice(0, 120));
    return res.result.value;
  };
  const until = async (seconds) => {
    const delta = seconds - now();
    if (delta > 0) await sleep(delta * 1000);
  };
  const waitText = async (needle, timeout = 20) => {
    const deadline = now() + timeout;
    while (now() < deadline) {
      const text = await evaluate("document.getElementById('result-card')?.innerText || ''");
      if (text && text.toLowerCase().includes(needle.toLowerCase())) return text;
      await sleep(200);
    }
    return "";
  };
  const click = async (selector) => {
    const rect = await evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    if (!rect) throw new Error(`missing element ${selector}`);
    await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: rect.x, y: rect.y });
    await sleep(120);
    await page.send("Input.dispatchMouseEvent", { type: "mousePressed", x: rect.x, y: rect.y, button: "left", clickCount: 1 });
    await sleep(60);
    await page.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: rect.x, y: rect.y, button: "left", clickCount: 1 });
    await sleep(120);
  };
  const hover = async (selector) => {
    const rect = await evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    if (rect) await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: rect.x, y: rect.y });
  };
  const caption = (text) => evaluate(`window.__demoCaption(${JSON.stringify(text)})`);
  const submitText = async (text) => {
    await evaluate(`(() => {
      const input = document.getElementById('command-input');
      input.focus();
      input.value = ${JSON.stringify(text)};
      input.dispatchEvent(new Event('input', { bubbles: true }));
      document.getElementById('text-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      return true;
    })()`);
  };

  await page.send("Page.enable");
  await page.send("Runtime.enable");
  await page.send("Network.enable");
  await page.send("Emulation.setDeviceMetricsOverride", {
    width: VIEWPORT.width, height: VIEWPORT.height, deviceScaleFactor: SCALE, mobile: false,
  });

  // capture the real /api/tts response bytes so the final mix uses the actual audio the app played
  let ttsIndex = 0;
  page.on(async (msg) => {
    if (msg.method === "Network.responseReceived" && msg.params.response.url.includes("/api/tts")) {
      const requestId = msg.params.requestId;
      const stamp = now();
      try {
        const body = await page.send("Network.getResponseBody", { requestId });
        if (body.base64Encoded) {
          const file = resolve(dir, `tts_${ttsIndex++}.wav`);
          writeFileSync(file, Buffer.from(body.body, "base64"));
          events.push({ name: "tts_audio", t: Number(stamp.toFixed(3)), file });
        }
      } catch { /* body gone, non-fatal */ }
    }
  });

  await page.send("Page.navigate", { url: BASE });
  await sleep(3200);
  await evaluate(`(${captionScript.toString()})()`);
  await until(0.4);

  t0 = Date.now();
  await page.send("Page.startScreencast", {
    format: "jpeg", quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1,
  });
  page.on((msg) => {
    if (msg.method !== "Page.screencastFrame") return;
    const { data, metadata, sessionId } = msg.params;
    const name = `f${String(frames.length).padStart(5, "0")}.jpg`;
    writeFileSync(resolve(framesDir, name), Buffer.from(data, "base64"));
    frames.push({ file: name, t: Number(((metadata.timestamp * 1000 - performance.timeOrigin) / 1000).toFixed(3)) });
    page.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });

  const ctx = { evaluate, until, waitText, click, hover, caption, submitText, event, sleep, now };
  try {
    await segment.run(ctx);
  } finally {
    event("end");
    await page.send("Page.stopScreencast").catch(() => {});
    // normalise frame timestamps: ScreencastFrame metadata.timestamp is a monotonic clock,
    // so recompute offsets from the capture start instead.
    const first = frames.length ? frames[0].t : 0;
    const offset = events[0]?.t ?? 0;
    for (const f of frames) f.t = Math.max(0, Number((f.t - first).toFixed(3)));
    for (const e of events) e.t = Number(e.t.toFixed(3));
    writeFileSync(resolve(dir, "frames.json"), JSON.stringify({ frames, start: offset }, null, 1));
    writeFileSync(resolve(dir, "events.json"), JSON.stringify({ events, duration: Number(now().toFixed(3)) }, null, 1));
    console.log(`  [${segment.name}] ${frames.length} frames, ${now().toFixed(2)}s`);
    await browser.send("Browser.close").catch(() => {});
    try { child.kill(); } catch { /* already gone */ }
    await sleep(1200);
  }
}

const SCRIPT = {
  s1: "Jai Hind doston! Pichhle kuch hafton se main is par kaam kar raha hoon — ek khata, jo sirf bolne se chalta hai.",
  s2a: "Ye hai HisabSetu AI. Main sirf bolunga.",
  s2b: "Prisma ne suna, parser ne ₹150 ka udhaar bana diya — Ramesh ₹450 se ₹600. Aur sabse zaroori baat: ledger abhi nahi badla.",
  s2c: "Confirm dabaya — ab save hua. Total ₹4,750.",
  s3: "Bakaya poocha — jawab aaya, aur Timbre ne use Hindi mein bol kar sunaya.",
  s4: "Ek saans mein do hukm? Ye mana kar deta hai, dono dikhata hai, alag-alag karne ko kehta hai.",
  s5: "Galat suna ho, to main transcript sudharta hoon — database nahi.",
  s6: "Bina Confirm kuch nahi badalta. Yahi is app ka poora idea hai.",
};

const segments = [
  {
    name: "s1-dashboard",
    async run({ caption, until, evaluate, event }) {
      await caption(SCRIPT.s1);
      event("caption_n1");
      await until(0.9);
      await evaluate("window.__demoScroll(190, 0)");
      await until(7.6);
    },
  },
  {
    name: "s2-voice-credit",
    wav: "cmd1",
    async run({ caption, until, evaluate, click, hover, waitText, event, now }) {
      await caption(SCRIPT.s2a);
      event("caption_n2");
      await until(2.4);
      await hover("#mic-btn");
      await until(2.9);
      await click("#mic-btn");
      event("mic_press");
      await until(5.7);
      await click("#mic-btn");
      event("mic_stop");
      const preview = await waitText("transaction preview", 18);
      if (!preview) throw new Error("preview never appeared");
      event("preview");
      await evaluate("window.__demoScrollToEl('#result-card', 80, 0)");
      await caption(SCRIPT.s2b);
      event("caption_n3");
      await until(now() + 8.6);
      await click('[data-action="confirm"]');
      event("confirm");
      const success = await waitText("ledger update", 15);
      event("success", { ok: Boolean(success) });
      await until(now() + 0.5);
      await evaluate("window.__demoScroll(0, 0)");
      await caption(SCRIPT.s2c);
      event("caption_n4");
      await until(now() + 4.2);
    },
  },
  {
    name: "s3-balance",
    wav: "cmd2",
    async run({ caption, until, click, hover, waitText, evaluate, event, now }) {
      await until(0.5);
      await hover("#mic-btn");
      await until(0.9);
      await click("#mic-btn");
      event("mic_press");
      await until(3.1);
      await click("#mic-btn");
      event("mic_stop");
      const answer = await waitText("baaki", 18);
      if (!answer) throw new Error("answer never appeared");
      event("answer");
      await evaluate("window.__demoScrollToEl('#result-card', 80, 0)");
      await caption(SCRIPT.s3);
      event("caption_n5");
      await until(now() + 1.6);
      await click('[data-action="speak"]');
      event("speak");
      await until(now() + 4.6);
    },
  },
  {
    name: "s4-compound",
    wav: "cmd3",
    async run({ caption, until, click, hover, waitText, evaluate, event, now }) {
      await until(0.5);
      await hover("#mic-btn");
      await until(0.9);
      await click("#mic-btn");
      event("mic_press");
      await until(4.7);
      await click("#mic-btn");
      event("mic_stop");
      const refusal = await waitText("alag", 20);
      if (!refusal) throw new Error("compound refusal never appeared");
      event("refusal");
      await evaluate("window.__demoScrollToEl('#result-card', 80, 0)");
      await caption(SCRIPT.s4);
      event("caption_n6");
      await until(now() + 7.4);
    },
  },
  {
    name: "s5-correction",
    async run({ caption, until, click, waitText, evaluate, event, now, submitText }) {
      await until(0.5);
      await submitText("Ramesh ko do sau udhaar");
      event("typed_command");
      const preview = await waitText("transaction preview", 15);
      if (!preview) throw new Error("correction preview never appeared");
      event("preview");
      await evaluate("window.__demoScrollToEl('#result-card', 80, 0)");
      await until(now() + 1.2);
      await click("#edit-transcript");
      event("edit_transcript");
      await until(now() + 0.9);
      await submitText("Ramesh ko dhai sau udhaar");
      event("corrected");
      const rebuilt = await waitText("250", 15);
      if (!rebuilt) throw new Error("rebuilt preview never appeared");
      event("rebuilt");
      await caption(SCRIPT.s5);
      event("caption_n7");
      await until(now() + 4.5);
    },
  },
  {
    name: "s6-close",
    async run({ caption, evaluate, until, event, now }) {
      await until(0.6);
      await evaluate("window.__demoScroll(0, 0)");
      await until(1.9);
      await caption(SCRIPT.s6);
      event("caption_n8");
      await until(now() + 1.2);
      await evaluate("window.__demoScrollToEl('#transactions-list', 140, 0)");
      await until(now() + 4.0);
    },
  },
];

const only = process.argv[2];
for (const [index, segment] of segments.entries()) {
  if (only && segment.name !== only) continue;
  console.log(`recording ${segment.name}`);
  await runSegment(segment, index);
}
console.log("capture done");
