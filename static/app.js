/* KhataVaani — frontend logic
   All money figures shown come from the SQLite ledger via the API.
   A transaction is only posted after an explicit confirm click. */

"use strict";

const MAX_SECONDS = 30;

const state = {
  health: null,
  customers: [],
  transactions: [],
  daily: null,
  dashboard: null,
  lastTranscript: "",
  lastSource: "text",
  lastSpeech: "",
  lastCustomerName: "",
  proposal: null,
  pendingId: null,
  ackStep: false,
  recording: false,
  recorder: null,
  stream: null,
  chunks: [],
  timerId: null,
  startedAt: 0,
  recordingUrl: null,
  audio: null,
  ttsCache: new Map(),
  search: "",
  manualOpen: false,
};

const $ = (selector) => document.querySelector(selector);

/* ------------------------------------------------------------------ */
/* Theme (light / dark)                                               */
/* ------------------------------------------------------------------ */

const THEME_KEY = "vk-theme";

function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  const toggle = $("#theme-toggle");
  if (toggle) {
    toggle.setAttribute("aria-label", dark ? "Light mode" : "Dark mode");
    const moon = toggle.querySelector(".icon-moon");
    const sun = toggle.querySelector(".icon-sun");
    if (moon) moon.hidden = dark;
    if (sun) sun.hidden = !dark;
  }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#0d1512" : "#0b6b4f");
}

function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch { /* storage blocked */ }
  if (saved !== "dark" && saved !== "light") {
    saved = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  applyTheme(saved);
}

function toggleTheme() {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  const next = dark ? "light" : "dark";
  applyTheme(next);
  try { localStorage.setItem(THEME_KEY, next); } catch { /* storage blocked */ }
}

/* ------------------------------------------------------------------ */
/* UI language: Hindi / Hinglish / English                            */
/* Only client-side labels change. Money figures and ledger data come */
/* from the API and are never translated or recomputed here.          */
/* ------------------------------------------------------------------ */

const UI_LANG_KEY = "vk-ui-lang";

const I18N = {
  hing: {
    app_name: "HisabSetu AI",
    tagline: "बोलिए, हिसाब लिख जाएगा",
    total_outstanding: "Kul udhaar baaki", today_credit: "Aaj ka udhaar",
    today_credit_foot: "Aaj diya gaya credit", today_payment: "Aaj ka jama",
    voice_khata: "HisabSetu AI", voice_title: "Boliye, main likh dunga",
    voice_sub: "Sirf confirm karne ke baad hi hisaab badlega.",
    mic_label: "Dabaiye aur boliye", mic_hint: "Jaise: “Ramesh ko dedh sau ka udhaar likh do”",
    mic_label_rec: "Sun rahe hain… band karne ke liye dabaiye",
    mic_hint_rec: "Saaf Hindi ya Hinglish mein bolein",
    step1: "Bolein", step2: "Transcript dekhein", step3: "Confirm karein",
    send: "Bhejein", input_ph: "Ya yahan likhein: Mohan ka kitna udhaar baaki hai?",
    help_summary: "Mic kaam nahi kar raha?",
    customer_khata: "Customer khata", sabke_hisaab: "Sabke hisaab", search_ph: "Naam dhoondein",
    aaj_ka_hisaab: "Aaj ka hisaab", aaj: "Aaj", udhaar_diya: "Udhaar diya",
    jama_hua: "Jama hua", net_badlav: "Net badlav", kul_baaki: "Kul baaki",
    sabse_zyada: "Sabse zyada udhaar", poochhein: "Poochhein",
    reminder_title: "Yaad dilane ke liye",
    reminder_fineprint: "Yeh sirf aapke liye sujhav hain. Kisi customer ko message nahi bheja jaata.",
    hisaab_voice: "Aaj ka hisaab voice mein poochhein",
    txn_history: "Transaction history", recent_entries: "Recent entries",
    setup: "Setup", voice_audio: "Voice aur audio",
    install_title: "Phone par app jaisa laga lein",
    install_sub: "Home screen par icon aa jaayega — roz kholna aasan.",
    install_cta: "App lagaayein",
    install_later: "Baad mein",
    install_done: "App lag gaya — home screen par icon dekhein.",
    install_how: "Safari mein neeche Share dabaein → Add to Home Screen chunein.",
    nav_bolo: "Bolo", nav_grahak: "Grahak", nav_hisaab: "Hisaab",
    footer_tag: "HisabSetu AI",
    footer_note: "Ledger hamesha transaction history se banta hai.",
    footer_fineprint: "Demo data kalpanik customers ka hai — koi asli phone, Aadhaar ya PAN number store nahi hota. Reminders sirf sujhav hain.",
  },
  hi: {
    tagline: "बोलिए, हिसाब लिख जाएगा",
    total_outstanding: "कुल बाकी", today_credit: "आज दिया उधार",
    today_credit_foot: "आज दिया गया उधार", today_payment: "आज मिले पैसे",
    voice_khata: "हिसाबसेतु ए आई", voice_title: "बोलिए, मैं लिख दूँगा",
    voice_sub: "पहले जाँचें, फिर पक्का करें — तभी हिसाब बदलेगा।",
    mic_label: "बोलने के लिए दबाएँ", mic_hint: "जैसे: रमेश को डेढ़ सौ उधार",
    mic_label_rec: "सुन रहे हैं… रोकने के लिए दबाइए",
    mic_hint_rec: "साफ़ हिंदी या हिंग्लिश में बोलिए",
    step1: "बोलिए", step2: "जाँचें", step3: "पक्का करें",
    send: "भेजें", input_ph: "या यहाँ लिखें: मोहन का कितना उधार बाकी है?",
    help_summary: "माइक काम नहीं कर रहा?",
    customer_khata: "ग्राहक खाता", sabke_hisaab: "सबका हिसाब", search_ph: "नाम से खोजें",
    aaj_ka_hisaab: "आज का हिसाब", aaj: "आज", udhaar_diya: "उधार दिया",
    jama_hua: "जमा हुआ", net_badlav: "नेट बदलाव", kul_baaki: "कुल बाकी",
    sabse_zyada: "सबसे ज़्यादा उधार", poochhein: "पूछें",
    reminder_title: "याद दिलाने के लिए",
    reminder_fineprint: "यह सिर्फ़ आपके लिए सुझाव हैं। किसी ग्राहक को संदेश नहीं भेजा जाता।",
    hisaab_voice: "आज का हिसाब वॉइस में पूछें",
    txn_history: "पुरानी एंट्री", recent_entries: "हाल की एंट्री",
    setup: "तकनीकी जानकारी", voice_audio: "वॉइस और ऑडियो",
    install_title: "फ़ोन में ऐप की तरह लगाएँ",
    install_sub: "होम स्क्रीन पर आइकन आ जाएगा — रोज़ खोलना आसान।",
    install_cta: "ऐप लगाएँ",
    install_later: "बाद में",
    install_done: "ऐप लग गया — होम स्क्रीन पर आइकन देखें।",
    install_how: "Safari में नीचे Share दबाएँ → Add to Home Screen चुनें।",
    nav_bolo: "बोलिए", nav_grahak: "ग्राहक", nav_hisaab: "हिसाब",
    footer_tag: "हिसाबसेतु ए आई",
    footer_note: "खाता हमेशा लेन-देन के इतिहास से बनता है।",
    footer_fineprint: "डेमो डेटा काल्पनिक ग्राहकों का है — कोई असली फ़ोन, आधार या पैन नंबर स्टोर नहीं होता। रिमाइंडर सिर्फ़ सुझाव हैं।",
  },
  en: {
    tagline: "Speak, the ledger is written",
    total_outstanding: "Total outstanding", today_credit: "Credit given today",
    today_credit_foot: "Credit issued today", today_payment: "Payments today",
    voice_khata: "HisabSetu AI", voice_title: "Just speak, I'll write it",
    voice_sub: "The ledger changes only after you confirm.",
    mic_label: "Tap and speak", mic_hint: "Like: “Give Ramesh ₹150 on credit”",
    mic_label_rec: "Listening… tap to stop",
    mic_hint_rec: "Speak clearly in Hindi or Hinglish",
    step1: "Speak", step2: "Review transcript", step3: "Confirm",
    send: "Send", input_ph: "Or type here: How much does Mohan owe?",
    help_summary: "Microphone not working?",
    customer_khata: "Customer ledger", sabke_hisaab: "Everyone's account", search_ph: "Search name",
    aaj_ka_hisaab: "Today's summary", aaj: "Today", udhaar_diya: "Credit given",
    jama_hua: "Payments received", net_badlav: "Net change", kul_baaki: "Total left",
    sabse_zyada: "Highest outstanding", poochhein: "Ask",
    reminder_title: "Reminders",
    reminder_fineprint: "These are just suggestions for you. No customer is messaged.",
    hisaab_voice: "Hear today's summary",
    txn_history: "Transaction history", recent_entries: "Recent entries",
    setup: "Setup", voice_audio: "Voice and audio",
    install_title: "Put this on your phone",
    install_sub: "It gets a home-screen icon — easier to open every day.",
    install_cta: "Install app",
    install_later: "Later",
    install_done: "Installed — look for the icon on your home screen.",
    install_how: "In Safari tap Share → Add to Home Screen.",
    nav_bolo: "Speak", nav_grahak: "Customers", nav_hisaab: "Ledger",
    footer_tag: "HisabSetu AI",
    footer_note: "The ledger is always built from transaction history.",
    footer_fineprint: "Demo data uses fictional customers — no real phone, Aadhaar or PAN numbers are stored. Reminders are suggestions only.",
  },
};

let UI_LANG = "hing";

function t(key) {
  const dict = I18N[UI_LANG] || I18N.hing;
  return dict[key] ?? I18N.hing[key] ?? key;
}

function applyLanguage(lang) {
  if (!I18N[lang]) lang = "hing";
  UI_LANG = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const value = t(el.dataset.i18n);
    if (value != null) el.textContent = value;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    const value = t(el.dataset.i18nPh);
    if (value != null) el.setAttribute("placeholder", value);
  });
  const select = $("#ui-lang");
  if (select && select.value !== lang) select.value = lang;
  refreshDynamicLabels();
}

/* Re-render text that is generated by JS so it follows the language. */
function refreshDynamicLabels() {
  const words = {
    en: { net: "Net", entries: "entries", customers: "customers" },
    hi: { net: "बदलाव", entries: "एंट्री", customers: "ग्राहक" },
    hing: { net: "Net", entries: "entry", customers: "customer" },
  }[UI_LANG] || { net: "Net", entries: "entry", customers: "customer" };
  if (state.dashboard) {
    $("#today-net").textContent = `${words.net} ${state.dashboard.today_net_text} · ${state.dashboard.today_transaction_count} ${words.entries}`;
    $("#outstanding-customer-count").textContent = `${state.dashboard.customer_count} ${words.customers}`;
  }
  if (state.recording) {
    $("#mic-label").textContent = t("mic_label_rec");
    $("#mic-hint").textContent = t("mic_hint_rec");
  } else {
    $("#mic-label").textContent = t("mic_label");
    $("#mic-hint").textContent = t("mic_hint");
  }
  const stepSpans = document.querySelectorAll(".voice-steps span");
  if (stepSpans.length === 3) {
    stepSpans[0].innerHTML = `<b>1</b> ${escapeHtml(t("step1"))}`;
    stepSpans[1].innerHTML = `<b>2</b> ${escapeHtml(t("step2"))}`;
    stepSpans[2].innerHTML = `<b>3</b> ${escapeHtml(t("step3"))}`;
  }
  if (state.daily) renderDaily(state.daily);
  if (state.customers.length) renderCustomers();
  if (state.transactions.length) renderTransactions();
}

function initLanguage() {
  let saved = null;
  try { saved = localStorage.getItem(UI_LANG_KEY); } catch { /* storage blocked */ }
  // Hindi first: a first-time shopkeeper should not have to switch anything.
  applyLanguage(saved && I18N[saved] ? saved : "hi");
}

/* ------------------------------------------------------------------ */
/* Sections: Bolo / Grahak / Hisaab                                   */
/* One screen at a time — a first-time shopkeeper should never have to */
/* scroll past things they did not ask for.                            */
/* ------------------------------------------------------------------ */

const VIEW_KEY = "vk-view";
const VIEWS = ["bolo", "grahak", "hisaab"];

function viewFromUrl() {
  try {
    const value = new URLSearchParams(window.location.search).get("view");
    return VIEWS.includes(value) ? value : null;
  } catch {
    return null;
  }
}

function setView(name, options = {}) {
  const view = VIEWS.includes(name) ? name : "bolo";
  const scroll = options.scroll !== false;
  document.querySelectorAll(".view[data-view]").forEach((section) => {
    section.classList.toggle("is-active", section.dataset.view === view);
  });
  document.querySelectorAll("[data-goto]").forEach((button) => {
    const isCurrent = button.dataset.goto === view;
    button.classList.toggle("is-active", isCurrent);
    if (isCurrent) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  state.view = view;
  if (options.remember !== false) {
    try { localStorage.setItem(VIEW_KEY, view); } catch { /* storage blocked */ }
  }
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function initViews() {
  let saved = null;
  try { saved = localStorage.getItem(VIEW_KEY); } catch { /* storage blocked */ }
  // A manifest shortcut (?view=hisaab) wins over the last screen used.
  setView(viewFromUrl() || (VIEWS.includes(saved) ? saved : "bolo"), { scroll: false });

  const nav = $("#bottom-nav");
  if (nav) {
    nav.addEventListener("click", (event) => {
      const button = event.target.closest("[data-goto]");
      if (button) setView(button.dataset.goto);
    });
  }
  const chip = $("#balance-chip");
  if (chip) chip.addEventListener("click", () => setView("hisaab"));
}

const INTENT_LABELS = {
  add_credit: "Udhaar likhna",
  record_payment: "Payment jama",
  balance_query: "Balance sawal",
  top_debtor: "Sabse zyada udhaar",
  daily_summary: "Aaj ka hisaab",
  unknown: "Samajh nahi aaya",
};

const ICONS = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 3 2.8 20h18.4z"/><path d="M12 9v5"/><path d="M12 17h.01"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 8a5 5 0 0 1 0 8"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>',
  minus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M5 12h14"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>',
  checkCircle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.6 2.6L16 9.5"/></svg>',
};

/* ------------------------------------------------------------------ */
/* Utilities                                                          */
/* ------------------------------------------------------------------ */

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part.charAt(0)).join("").toUpperCase() || "?";
}

function moneyAbs(text) {
  return String(text || "₹0").replace("-", "");
}

function whenLabel(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("en-IN", {
      day: "2-digit", month: "short", hour: "numeric", minute: "2-digit",
      timeZone: "Asia/Kolkata",
    }).format(date);
  } catch {
    return date.toLocaleString();
  }
}

function todayLabel(isoDate) {
  if (!isoDate) return "Aaj";
  const date = new Date(`${isoDate}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return "Aaj";
  try {
    return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", weekday: "short" }).format(date);
  } catch {
    return isoDate;
  }
}

function toast(message, type = "info", ms = 4200) {
  const wrap = $("#toast-wrap");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  const icon = type === "error" ? ICONS.alert : type === "success" ? ICONS.checkCircle : type === "warn" ? ICONS.alert : ICONS.info;
  el.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
  wrap.appendChild(el);
  window.setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateY(6px)";
    el.style.transition = "opacity .2s, transform .2s";
    window.setTimeout(() => el.remove(), 220);
  }, ms);
}

function showBusy(text, sub) {
  $("#busy-text").textContent = text;
  $("#busy-sub").textContent = sub || "";
  $("#busy-overlay").classList.remove("hidden");
}

function hideBusy() {
  $("#busy-overlay").classList.add("hidden");
}

async function api(path, options = {}) {
  const config = { method: options.method || "GET", headers: {} };
  if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(path, config);
  } catch (networkError) {
    const error = new Error("Server se connection nahi bana. App chal rahi hai?");
    error.code = "network_error";
    throw error;
  }
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { /* non-JSON error */ }
    const error = new Error(payload?.error?.message || `Request fail hui (HTTP ${response.status}).`);
    error.code = payload?.error?.code || `http_${response.status}`;
    error.hint = payload?.error?.hint || null;
    error.status = response.status;
    throw error;
  }
  return response;
}

async function apiJson(path, options = {}) {
  const response = await api(path, options);
  return response.json();
}

/* ------------------------------------------------------------------ */
/* Boot / loading                                                     */
/* ------------------------------------------------------------------ */

function bindEvents() {
  $("#theme-toggle").addEventListener("click", toggleTheme);
  initViews();

  $("#ui-lang").addEventListener("change", (event) => {
    const lang = event.target.value;
    applyLanguage(lang);
    try { localStorage.setItem(UI_LANG_KEY, lang); } catch { /* storage blocked */ }
  });

  $("#mic-btn").addEventListener("click", () => {
    if (state.recording) stopRecording();
    else startRecording();
  });

  $("#text-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = $("#command-input").value.trim();
    if (!value) {
      toast("Pehle command likhein ya bolein.", "warn");
      $("#command-input").focus();
      return;
    }
    processText(value, { source: "text" });
  });

  $("#example-chips").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-example]");
    if (!chip) return;
    $("#command-input").value = chip.dataset.example;
    processText(chip.dataset.example, { source: "text" });
  });

  $("#retry-voice").addEventListener("click", () => startRecording());
  $("#edit-transcript").addEventListener("click", () => editTranscript());

  $("#play-recording").addEventListener("click", () => {
    const audio = $("#recording-audio");
    if (!audio.src) return;
    audio.currentTime = 0;
    audio.play().catch(() => toast("Recording play nahi ho saki.", "warn"));
  });

  $("#customer-search").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderCustomers();
  });

  $("#add-customer-toggle").addEventListener("click", () => openAddCustomerForm());
  $("#add-customer-cancel").addEventListener("click", () => closeAddCustomerForm());
  $("#add-customer-form").addEventListener("submit", handleAddCustomerSubmit);

  $("#customers-list").addEventListener("click", (event) => {
    const target = event.target.closest("[data-ask-customer]");
    if (!target) return;
    const name = target.dataset.askCustomer;
    if (!name) return;
    $("#command-input").value = `${name} ka kitna udhaar baaki hai`;
    processText(`${name} ka kitna udhaar baaki hai`, { source: "text" });
  });

  $("#speak-summary").addEventListener("click", () => {
    if (state.daily?.speech_text) speak(state.daily.speech_text);
  });

  $("#daily-voice").addEventListener("click", () => {
    processText("Aaj ka poora hisaab batao", { source: "text", autoSpeak: true });
  });

  $("#ask-top-debtor").addEventListener("click", () => {
    processText("Sabse zyada udhaar kis customer ka hai", { source: "text", autoSpeak: true });
  });

  $("#refresh-all").addEventListener("click", () => loadAll(true));
  $("#status-refresh").addEventListener("click", () => loadHealth(true));

  $("#result-card").addEventListener("click", handleResultClick);
  $("#result-card").addEventListener("submit", handleManualSubmit);

  setupInstall();
}

/* ------------------------------------------------------------------ */
/* PWA install: give a shopkeeper an icon, not a URL to remember      */
/* ------------------------------------------------------------------ */

const INSTALL_DISMISS_KEY = "vk-install-dismissed";
let installEvent = null;

function setupInstall() {
  const banner = $("#install-banner");
  const button = $("#install-app");
  const dismiss = $("#install-dismiss");
  if (!banner || !button) return;

  const standalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches)
    || window.navigator.standalone === true;
  if (standalone) return; // already installed: no banner inside the app

  let dismissed = false;
  try { dismissed = localStorage.getItem(INSTALL_DISMISS_KEY) === "1"; } catch { /* storage blocked */ }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installEvent = event;
    if (!dismissed) banner.classList.remove("hidden");
  });

  window.addEventListener("appinstalled", () => {
    installEvent = null;
    banner.classList.add("hidden");
    toast(t("install_done"), "success", 4500);
  });

  button.addEventListener("click", async () => {
    if (!installEvent) {
      toast(t("install_how"), "info", 8000);
      return;
    }
    installEvent.prompt();
    try { await installEvent.userChoice; } catch { /* dismissed */ }
    installEvent = null;
    banner.classList.add("hidden");
  });

  if (dismiss) {
    dismiss.addEventListener("click", () => {
      dismissed = true;
      banner.classList.add("hidden");
      try { localStorage.setItem(INSTALL_DISMISS_KEY, "1"); } catch { /* storage blocked */ }
    });
  }

  // iPhone/iPad never fires beforeinstallprompt — show the manual steps instead.
  if (/iphone|ipad|ipod/i.test(window.navigator.userAgent) && !dismissed) {
    banner.classList.remove("hidden");
  }
}

async function boot() {
  initTheme();
  initLanguage();
  bindEvents();
  const today = new Date();
  $("#today-date").textContent = today.toLocaleDateString("en-IN", { day: "numeric", month: "short", weekday: "short" });
  await loadAll(false);
}

async function loadAll(announce) {
  const tasks = [
    loadHealth(false),
    loadDashboard(),
    loadCustomers(),
    loadTransactions(),
    loadDaily(),
  ];
  const results = await Promise.allSettled(tasks);
  const failed = results.filter((result) => result.status === "rejected");
  if (failed.length) {
    const first = failed[0].reason;
    const message = first?.code === "network_error"
      ? "Server se connection nahi mila. `uvicorn main:app --reload` chalayein."
      : first?.message || "Kuch data load nahi ho saka.";
    toast(message, "error", 6000);
    if (!state.dashboard) {
      $("#total-outstanding").textContent = "—";
    }
  } else if (announce) {
    toast("Hisaab refresh ho gaya.", "success", 2400);
  }
}

async function loadHealth(announce) {
  const health = await apiJson("/api/health");
  state.health = health;
  renderHealth(health);
  if (announce) toast("Voice aur audio status refresh hua.", "success", 2400);
}

async function loadDashboard() {
  const data = await apiJson("/api/dashboard");
  state.dashboard = data;
  $("#total-outstanding").textContent = data.total_outstanding_text;
  const chipValue = $("#balance-chip-value");
  if (chipValue) chipValue.textContent = data.total_outstanding_text;
  $("#today-credit").textContent = data.today_credit_text;
  $("#today-payment").textContent = data.today_payment_text;
  $("#today-net").textContent = `Net ${data.today_net_text} · ${data.today_transaction_count} entries`;
  $("#outstanding-customer-count").textContent = `${data.customer_count} customers`;
  $("#txn-count").textContent = String(data.transaction_count);
  $("#today-date").textContent = todayLabel(data.today_date);
  $("#sample-badge").hidden = !data.sample_data;
}

async function loadCustomers() {
  const data = await apiJson("/api/customers");
  state.customers = data.customers || [];
  renderCustomers();
}

async function loadTransactions() {
  const data = await apiJson("/api/transactions?limit=20");
  state.transactions = data.transactions || [];
  renderTransactions();
}

async function loadDaily() {
  const data = await apiJson("/api/daily-summary");
  state.daily = data;
  renderDaily(data);
}

/* ------------------------------------------------------------------ */
/* Rendering: status, totals, ledger                                  */
/* ------------------------------------------------------------------ */

function renderHealth(health) {
  const gnani = health.gnani || {};
  const sttOk = Boolean(gnani.stt_configured);
  const ttsOk = Boolean(gnani.tts_configured);
  const ffmpegOk = Boolean(health.audio?.ffmpeg_available);

  $("#gnani-dot").className = `status-dot ${sttOk ? "ok" : "warn"}`;
  $("#tts-dot").className = `status-dot ${ttsOk ? "ok" : "warn"}`;
  $("#ffmpeg-dot").className = `status-dot ${ffmpegOk ? "ok" : "warn"}`;

  $("#stt-status").textContent = sttOk
    ? `Live · Prisma · ${gnani.stt_language || "hi-IN"}`
    : "Configure nahi — .env mein GNANI_API_KEY set karein";
  $("#tts-status").textContent = ttsOk
    ? `Live · ${gnani.tts_model || "timbre"} · ${gnani.tts_voice || "voice"}`
    : "Configure nahi — text reply kaam karega";
  $("#ffmpeg-status").textContent = ffmpegOk
    ? "Ready · WebM/MP4 ko WAV mein convert karta hai"
    : "Nahi mila — WebM recordings convert nahi hongi";

  const pill = $("#voice-status-pill");
  pill.classList.toggle("is-off", !sttOk);
  pill.innerHTML = `<span class="dot"></span>${sttOk ? "Voice ready" : "Text mode"}`;

  $("#status-note").innerHTML = sttOk
    ? "Mic se bolein ya text likhein. Har transaction confirm karne ke baad hi save hota hai."
    : "Voice ke liye <code>.env</code> mein <code>GNANI_API_KEY</code> set karke server restart karein. Text commands abhi bhi poore kaam karte hain.";
}

function balanceMeta(paise) {
  if (paise > 0) return { cls: "balance-baaki", label: "Baaki" };
  if (paise < 0) return { cls: "balance-advance", label: "Advance" };
  return { cls: "balance-clear", label: "Barabar" };
}

function renderCustomers() {
  const list = $("#customers-list");
  const query = state.search;
  const filtered = state.customers.filter((customer) => {
    if (!query) return true;
    const name = customer.name.toLowerCase();
    return name.includes(query) || name.replace(/\s+/g, "").includes(query.replace(/\s+/g, ""));
  });

  $("#customers-empty").classList.toggle("hidden", filtered.length > 0);
  if (!filtered.length) {
    list.innerHTML = "";
    return;
  }

  list.innerHTML = filtered.map((customer) => {
    const meta = balanceMeta(customer.balance_paise);
    const shown = customer.balance_paise < 0 ? moneyAbs(customer.balance_text) : customer.balance_text;
    return `
      <li class="customer-row">
        <button class="customer-row-btn" type="button" data-ask-customer="${escapeHtml(customer.name)}"
          aria-label="${escapeHtml(customer.name)} ka balance poochhein">
          <span class="avatar ${customer.balance_paise > 0 ? "warm" : ""}">${escapeHtml(initials(customer.name))}</span>
          <span>
            <span class="cust-name">${escapeHtml(customer.name)}</span>
            <span class="cust-sub">${meta.label}${customer.is_sample ? " · sample" : ""}</span>
          </span>
        </button>
        <span class="balance-pill ${meta.cls}">${escapeHtml(shown)}</span>
        <button class="cust-ask" type="button" data-ask-customer="${escapeHtml(customer.name)}">Poochho</button>
      </li>`;
  }).join("");
}

function renderTransactions() {
  const list = $("#transactions-list");
  const items = state.transactions;
  $("#transactions-empty").classList.toggle("hidden", items.length > 0);
  if (!items.length) {
    list.innerHTML = "";
    return;
  }
  list.innerHTML = items.map((txn) => {
    const isCredit = txn.type === "credit";
    const sign = isCredit ? "+" : "−";
    return `
      <li class="txn-row">
        <span class="txn-icon ${isCredit ? "credit" : "payment"}">${isCredit ? ICONS.plus : ICONS.minus}</span>
        <div class="txn-main">
          <div class="txn-name">${escapeHtml(txn.customer_name || "Customer")}</div>
          <div class="txn-meta">${escapeHtml(txn.type_label)} · ${escapeHtml(whenLabel(txn.created_at))}${txn.is_sample ? " · sample" : ""}</div>
        </div>
        <span class="txn-amt ${isCredit ? "credit" : "payment"}">${sign}${escapeHtml(txn.amount_text)}</span>
      </li>`;
  }).join("");
}

function renderDaily(summary) {
  $("#daily-date").textContent = summary.date_label || "Aaj";
  $("#daily-credit").textContent = summary.credit_text;
  $("#daily-payment").textContent = summary.payment_text;
  $("#daily-net").textContent = summary.net_text;
  $("#daily-outstanding").textContent = summary.total_outstanding_text;
  $("#daily-reply").textContent = summary.reply_text;

  const top = summary.top_debtors || [];
  $("#top-debtors").innerHTML = top.length
    ? top.map((customer, index) => `
        <li class="top-row">
          <span class="top-rank">${index + 1}</span>
          <span class="top-name">${escapeHtml(customer.name)}</span>
          <span class="top-amount">${escapeHtml(customer.balance_text)}</span>
        </li>`).join("")
    : '<li class="top-empty">Abhi kisi ka udhaar baaki nahi hai.</li>';

  const reminders = summary.reminders || [];
  $("#daily-reminders").innerHTML = reminders.length
    ? reminders.map((text) => `<li>${escapeHtml(text)}</li>`).join("")
    : "<li>Aaj yaad dilane ke liye koi baaki udhaar nahi.</li>";
}

/* ------------------------------------------------------------------ */
/* Transcript                                                         */
/* ------------------------------------------------------------------ */

function showTranscript(text, source) {
  state.lastTranscript = text;
  state.lastSource = source;
  // Every result lives on the talking screen, so any command jumps there.
  setView("bolo", { scroll: false });
  $("#transcript-text").textContent = text;
  $("#transcript-card").classList.remove("hidden");
  $("#transcript-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function editTranscript() {
  const text = state.lastTranscript || $("#transcript-text").textContent || "";
  if (!text.trim()) {
    toast("Pehle command bolein ya likhein.", "warn");
    return;
  }
  const input = $("#command-input");
  input.value = text;
  input.focus();
  input.setSelectionRange(text.length, text.length);
  input.scrollIntoView({ behavior: "smooth", block: "center" });
  toast(
    "Transcript theek karein aur Bhejein dabaiye. Naya preview banega — tab tak kuch save nahi hota.",
    "info",
    4500
  );
}

function renderTranscriptMeta(parser, source) {
  state.lastCustomerName = parser?.customer_name || "";
  const chips = [];
  chips.push(`<span class="meta-chip">${source === "voice" ? "Awaaz se" : "Text se"}</span>`);
  if (parser?.intent) {
    chips.push(`<span class="meta-chip"><b>Kaam:</b> ${escapeHtml(INTENT_LABELS[parser.intent] || parser.intent)}</span>`);
  }
  if (parser?.amount_text) {
    chips.push(`<span class="meta-chip"><b>Amount:</b> ${escapeHtml(parser.amount_text)}</span>`);
  }
  if (parser?.customer_name) {
    chips.push(`<span class="meta-chip"><b>Customer:</b> ${escapeHtml(parser.customer_name)}</span>`);
  }
  $("#transcript-meta").innerHTML = chips.join("");

  const confidence = Number(parser?.confidence || 0);
  const badge = $("#transcript-confidence");
  if (!confidence) {
    badge.hidden = true;
    return;
  }
  badge.hidden = false;
  badge.textContent = `${Math.round(confidence * 100)}% samajh`;
  badge.className = "badge " + (confidence >= 0.85 ? "" : confidence >= 0.6 ? "badge-mid" : "badge-low");
}

/* ------------------------------------------------------------------ */
/* Command flow                                                        */
/* ------------------------------------------------------------------ */

async function processText(text, options = {}) {
  const clean = String(text || "").trim();
  if (!clean) {
    toast("Kuch likhein ya bolein.", "warn");
    return;
  }
  if (!state.customers.length && !state.dashboard) {
    // Data may still be loading; the API works regardless.
  }

  // A corrected/re-sent command supersedes any preview still waiting for
  // confirmation, so the old pending row can never be confirmed by accident.
  cancelSupersededProposal(state.pendingId);

  showTranscript(clean, options.source === "voice" ? "voice" : "text");
  state.manualOpen = false;
  state.proposal = null;
  state.pendingId = null;
  state.ackStep = false;
  $("#result-card").classList.remove("hidden");
  $("#result-card").classList.remove("result-success");
  $("#result-card").innerHTML = `
    <div class="result-inner">
      <div class="result-head">
        <span class="result-kicker"><span class="k-dot"></span> Samajh rahe hain</span>
      </div>
      <div class="result-title">Ek second…</div>
      <p class="result-sub">Rule-based parser transcript ko padh raha hai.</p>
    </div>`;

  showBusy("Samajh rahe hain…", "Customer, amount aur kaam check ho raha hai");

  try {
    const payload = {
      text: clean,
      source: options.source === "voice" ? "voice" : "text",
    };
    if (options.customerId) payload.customer_id = options.customerId;
    const data = await apiJson("/api/command", { method: "POST", body: payload });
    hideBusy();
    renderResponse(data, options);
  } catch (error) {
    hideBusy();
    renderError(error);
  }
}

function renderResponse(data, options = {}) {
  renderTranscriptMeta(data.parser, data.transcript ? (options.source === "voice" ? "voice" : "text") : "text");
  state.lastSpeech = data.speech_text || "";
  if (data.kind === "proposal" && data.proposal) {
    renderProposal(data.proposal, data);
    if (options.source === "voice" || options.autoSpeak) speak(data.speech_text, { auto: true });
  } else if (data.kind === "clarification") {
    renderClarification(data);
    if (options.source === "voice") speak(data.speech_text, { auto: true });
  } else if (data.kind === "answer") {
    renderAnswer(data);
    if (options.autoSpeak || options.source === "voice" || data.answer?.kind === "balance") {
      speak(data.speech_text, { auto: true });
    }
  } else {
    renderClarification(data);
  }
}

/* ------------------------------------------------------------------ */
/* Result renderers                                                   */
/* ------------------------------------------------------------------ */

function resultShell({ accent = "", kicker = "", title = "", sub = "", body = "", foot = "" }) {
  const card = $("#result-card");
  card.classList.remove("hidden");
  card.innerHTML = `
    <div class="result-accent ${accent}"></div>
    <div class="result-inner">
      <div class="result-head">
        <div>
          <span class="result-kicker"><span class="k-dot"></span>${escapeHtml(kicker)}</span>
          <h2 class="result-title" style="margin-top:4px">${escapeHtml(title)}</h2>
          ${sub ? `<p class="result-sub">${escapeHtml(sub)}</p>` : ""}
        </div>
      </div>
      ${body}
      ${foot}
    </div>`;
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderProposal(proposal, response) {
  state.proposal = proposal;
  state.pendingId = proposal.pending_id;
  state.ackStep = false;
  const isCredit = proposal.type === "credit";
  const customer = proposal.customer || { name: "Customer", balance_text: "₹0", balance_paise: 0 };
  const ack = Boolean(proposal.requires_overpayment_ack);

  const body = `
    <div class="confirm-top">
      <div>
        <span class="type-pill ${isCredit ? "type-credit" : "type-payment"}">
          ${isCredit ? ICONS.plus : ICONS.minus}
          ${isCredit ? "Udhaar · credit" : "Payment · jama"}
        </span>
        <div class="confirm-amount">${escapeHtml(proposal.amount_text)}</div>
        <div class="result-sub">${isCredit ? "Customer ke khate mein udhaar badhega" : "Customer ka baaki hisaab ghatayega"}</div>
      </div>
      <span class="badge">Confirm baaki</span>
    </div>

    <div class="confirm-rows">
      <div class="confirm-row">
        <span class="k">Customer</span>
        <span class="customer-line">
          <span class="avatar">${escapeHtml(initials(customer.name))}</span>
          <span>
            <span class="name">${escapeHtml(customer.name)}</span>
            <span class="sub">Abhi ${escapeHtml(customer.balance_text)}</span>
          </span>
        </span>
      </div>
      <div class="confirm-row">
        <span class="k">Naya hisaab</span>
        <span class="v balance-flow">
          <span class="now">${escapeHtml(proposal.balance_before_text)}</span>
          <span class="arrow">${ICONS.arrow}</span>
          <span class="next">${escapeHtml(proposal.balance_after_text)}</span>
        </span>
      </div>
      <div class="confirm-row">
        <span class="k">Aapne kaha</span>
        <span class="v" style="font-weight:500;max-width:70%;overflow-wrap:anywhere">${escapeHtml(proposal.transcript)}</span>
      </div>
    </div>

    ${ack ? `
      <div class="warn-box" id="ack-warning">
        ${ICONS.alert}
        <div>
          <strong>Payment baaki raqam se zyada hai</strong>
          ${escapeHtml(customer.name)} ji ka abhi ${escapeHtml(customer.balance_text)} baaki hai. Itna jama karne par
          ${escapeHtml(moneyAbs(proposal.balance_after_text))} advance jama ho jayega. Aage badhne ke liye confirm dobara dabaiye.
        </div>
      </div>` : ""}

    <div class="result-message">${escapeHtml(proposal.message)}</div>

    <div class="confirm-actions">
      <button type="button" class="btn btn-primary" data-action="confirm" id="confirm-btn">
        ${ICONS.check} Confirm transaction
      </button>
      <button type="button" class="btn btn-secondary" data-action="cancel">Cancel</button>
      <button type="button" class="btn btn-ghost btn-correct" data-action="correct">Sahi karein — details badlein</button>
    </div>

    <div class="pending-foot">
      <span>${ICONS.shield} Sirf confirm ke baad save hoga · ${escapeHtml(whenLabel(proposal.expires_at))} tak valid</span>
      <button type="button" class="btn btn-ghost btn-sm" data-action="speak">${ICONS.speaker} Sunao</button>
    </div>`;

  resultShell({
    accent: ack ? "amber" : "",
    kicker: "Transaction preview",
    title: "Hisaab likhne se pehle confirm karein",
    sub: "Ledger abhi nahi badla hai.",
    body,
  });

  if (response?.message) {
    // The proposal message is already shown; keep the live region useful.
    $("#result-card").setAttribute("aria-label", response.message);
  }
}

function renderClarification(data) {
  const clarification = data.clarification || { needs: [], question: data.message, customers: [], examples: [] };
  const customers = clarification.customers || [];
  const examples = clarification.examples || [];
  const commands = clarification.commands || [];
  const isCompound = (clarification.needs || []).includes("compound");

  const picks = customers.length
    ? `<div class="customer-picks">${customers.map((customer) => `
        <button type="button" class="customer-pick" data-action="pick-customer" data-customer-id="${customer.id}">
          <span class="pick-left">
            <span class="avatar">${escapeHtml(initials(customer.name))}</span>
            <span>
              <span class="name">${escapeHtml(customer.name)}</span>
              <span class="sub" style="display:block;font-size:11px;color:var(--muted)">${escapeHtml(customer.balance_text)} baaki</span>
            </span>
          </span>
          <span class="pick-balance">Chunein ${ICONS.arrow}</span>
        </button>`).join("")}</div>`
    : "";

  // Compound utterance: every detected clause is listed, and each can be run on
  // its own so nothing is half-done or silently dropped.  Each run still needs
  // its own confirmation before anything reaches the ledger.
  const commandList = isCompound && commands.length
    ? `<ol class="compound-list">${commands.map((command, index) => `
        <li class="compound-item">
          <span class="compound-index">${index + 1}</span>
          <span class="compound-body">
            <span class="compound-label">${escapeHtml(command.intent_label || command.intent || "Kaam")}${command.amount_text ? ` · ${escapeHtml(command.amount_text)}` : ""}</span>
            <span class="compound-text">“${escapeHtml(command.text)}”</span>
          </span>
          <button type="button" class="btn btn-secondary btn-small" data-action="example" data-text="${escapeHtml(command.text)}">Isko alag chalayein</button>
        </li>`).join("")}</ol>`
    : "";

  const exampleChips = examples.length
    ? `<div class="chips" style="margin-top:12px">${examples.slice(0, 3).map((example) => `
        <button type="button" class="chip" data-action="example" data-text="${escapeHtml(example)}">${escapeHtml(example)}</button>`).join("")}</div>`
    : "";

  resultShell({
    accent: "amber",
    kicker: "Thoda clear karein",
    title: isCompound
      ? `${commands.length} kaam ek saath`
      : clarification.needs?.includes("customer") ? "Customer chunein" : "Detail chahiye",
    sub: "Bina poori jaankari ke koi transaction save nahi hoga.",
    body: `
      <div class="result-message speech">${escapeHtml(clarification.question || data.message)}</div>
      ${commandList}
      ${picks}
      ${exampleChips}
      <div class="answer-actions">
        ${clarification.needs?.includes("customer") ? '<button type="button" class="btn btn-secondary" data-action="add-customer">Naya customer banayein</button>' : ''}
        <button type="button" class="btn btn-secondary" data-action="correct">Khud details bharein</button>
        <button type="button" class="btn btn-ghost" data-action="new">Naya command</button>
      </div>`,
  });
}

function renderAnswer(data) {
  const answer = data.answer || {};
  const summary = answer.summary || {};
  let body = "";
  let title = "Jawab";
  let kicker = "Voice reply";
  let accent = "blue";

  if (answer.kind === "balance") {
    const customer = answer.customer || {};
    title = `${customer.name || "Customer"} ka hisaab`;
    const advance = answer.balance_paise < 0;
    body = `
      <div class="answer-value">${escapeHtml(advance ? moneyAbs(answer.balance_text) : answer.balance_text)}</div>
      <div class="answer-label">${advance ? "Advance jama hai" : answer.balance_paise === 0 ? "Hisaab barabar hai" : "Kul udhaar baaki"}</div>
      <div class="result-message speech">${escapeHtml(data.message)}</div>
      ${customer.id ? `
        <div class="answer-rows">
          <div class="answer-row"><span class="k">Customer</span><span class="v">${escapeHtml(customer.name)}</span></div>
          <div class="answer-row"><span class="k">Recent entries</span><span class="v">${(answer.transactions || []).length}</span></div>
        </div>` : ""}`;
  } else if (answer.kind === "top_debtor") {
    const customers = answer.customers || [];
    accent = "amber";
    title = "Sabse zyada udhaar";
    body = `
      ${customers.length ? `
        <div class="answer-value">${escapeHtml(customers[0].balance_text)}</div>
        <div class="answer-label">${escapeHtml(customers[0].name)} ji ka sabse zyada baaki</div>
        <div class="answer-rows">
          ${customers.map((customer, index) => `
            <div class="answer-row">
              <span class="k">${index + 1}. ${escapeHtml(customer.name)}</span>
              <span class="v">${escapeHtml(customer.balance_text)}</span>
            </div>`).join("")}
        </div>` : '<div class="result-message">Abhi kisi ka udhaar baaki nahi hai.</div>'}
      <div class="result-message speech">${escapeHtml(data.message)}</div>`;
  } else if (answer.kind === "daily_summary") {
    title = "Aaj ka poora hisaab";
    body = `
      <div class="answer-rows" style="margin-top:0">
        <div class="answer-row"><span class="k">Udhaar diya</span><span class="v credit-text">${escapeHtml(summary.credit_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">Jama hua</span><span class="v payment-text">${escapeHtml(summary.payment_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">Net badlav</span><span class="v">${escapeHtml(summary.net_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">Kul baaki</span><span class="v">${escapeHtml(summary.total_outstanding_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">Entries</span><span class="v">${Number(summary.transaction_count || 0)}</span></div>
      </div>
      <div class="result-message speech">${escapeHtml(data.message)}</div>
      ${(summary.reminders || []).length ? `
        <div class="reminder-box">
          <div class="reminder-title">${ICONS.info} Reminder sujhav</div>
          <ul>${summary.reminders.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
        </div>` : ""}`;
  } else {
    body = `<div class="result-message">${escapeHtml(data.message)}</div>`;
  }

  resultShell({
    accent,
    kicker,
    title,
    sub: "Yeh jawab SQLite ledger se bana hai.",
    body,
    foot: `
      <div class="answer-actions">
        <button type="button" class="btn btn-primary" data-action="speak">${ICONS.speaker} Sunao</button>
        <button type="button" class="btn btn-secondary" data-action="new">Naya command</button>
      </div>`,
  });
}

function renderSuccess(result) {
  state.proposal = null;
  state.pendingId = null;
  state.ackStep = false;
  const txn = result.transaction || {};
  const customer = result.customer || {};
  const isCredit = txn.type === "credit";
  const balance = customer.balance_paise ?? 0;
  const already = result.already_confirmed;

  resultShell({
    accent: "",
    kicker: already ? "Pehle se saved" : "Ho gaya",
    title: already ? "Yeh entry pehle hi save hai" : "Ledger update ho gaya",
    sub: "Database commit ke baad hi yeh dikhaya gaya hai.",
    body: `
      <div class="success-hero">
        <div class="success-badge">${ICONS.check}</div>
        <div class="success-amount">${isCredit ? "+" : "−"}${escapeHtml(txn.amount_text || "₹0")}</div>
        <div class="success-note">${escapeHtml(customer.name || "")} · ${isCredit ? "udhaar likha gaya" : "payment jama hua"}</div>
        <div class="success-balance">Ab ${balance < 0 ? "advance" : "baaki"} <strong>${escapeHtml(balance < 0 ? moneyAbs(customer.balance_text || "₹0") : customer.balance_text || "₹0")}</strong></div>
      </div>
      <div class="result-message speech">${escapeHtml(result.message)}</div>
      <div class="answer-actions">
        <button type="button" class="btn btn-primary" data-action="speak">${ICONS.speaker} Jawab sunao</button>
        <button type="button" class="btn btn-secondary" data-action="new">Aur bolein</button>
      </div>`,
  });
}

function renderError(error) {
  const setup = error.code === "gnani_not_configured";
  const title = setup ? "Voice setup baaki hai" : error.code === "network_error" ? "Server se connection nahi" : "Yeh request poori nahi hui";
  const body = `
    <div class="result-message ${setup ? "speech" : ""}">${escapeHtml(error.message)}</div>
    ${error.hint ? `<p class="result-sub" style="margin-top:10px">${escapeHtml(error.hint)}</p>` : ""}
    ${setup ? `
      <div class="answer-rows">
        <div class="answer-row"><span class="k">1</span><span class="v">.env mein GNANI_API_KEY daalein</span></div>
        <div class="answer-row"><span class="k">2</span><span class="v">Server restart karein</span></div>
        <div class="answer-row"><span class="k">3</span><span class="v">Yahan "Status refresh" dabaiye</span></div>
      </div>` : ""}
    <div class="answer-actions">
      <button type="button" class="btn btn-primary" data-action="setup-text">Text se command likhein</button>
      <button type="button" class="btn btn-secondary" data-action="retry">Phir try karein</button>
    </div>`;
  resultShell({
    accent: "red",
    kicker: "Error",
    title,
    sub: "Koi transaction save nahi hua — ledger safe hai.",
    body,
  });
}

function renderSetupNotice() {
  renderError({
    code: "gnani_not_configured",
    message: "Gnani Prisma STT configure nahi hai, isliye mic se transcript nahi aa sakta.",
    hint: "Project folder mein .env banayein, GNANI_API_KEY set karein aur server restart karein. Text commands poore kaam karte hain.",
  });
}

/* ------------------------------------------------------------------ */
/* Result actions                                                     */
/* ------------------------------------------------------------------ */

function handleResultClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;

  if (action === "confirm") confirmProposal(target);
  else if (action === "cancel") cancelProposal();
  else if (action === "correct") openManualForm();
  else if (action === "add-customer") openAddCustomerForm(state.lastCustomerName);
  else if (action === "speak") speak(state.lastSpeech);
  else if (action === "pick-customer") {
    const id = Number(target.dataset.customerId);
    if (!state.lastTranscript) {
      toast("Pehle command bolein ya likhein.", "warn");
      return;
    }
    processText(state.lastTranscript, { source: state.lastSource, customerId: id });
  } else if (action === "example") {
    const text = target.dataset.text || "";
    $("#command-input").value = text;
    processText(text, { source: "text" });
  } else if (action === "new") {
    resetConversation();
  } else if (action === "setup-text") {
    $("#command-input").focus();
    $("#command-input").scrollIntoView({ behavior: "smooth", block: "center" });
    toast("Text mein command likh kar Bhejein dabaiye.", "info");
  } else if (action === "retry") {
    processText(state.lastTranscript || $("#command-input").value, { source: "text" });
  } else if (action === "manual-cancel") {
    if (state.proposal) renderProposal(state.proposal, null);
    else resetConversation();
  }
}

async function confirmProposal(button) {
  if (!state.pendingId) return;
  const proposal = state.proposal;
  const needsAck = Boolean(proposal?.requires_overpayment_ack);

  if (needsAck && !state.ackStep) {
    state.ackStep = true;
    button.innerHTML = `${ICONS.check} Haan, advance jama karein`;
    const warning = $("#ack-warning");
    if (warning) warning.style.boxShadow = "0 0 0 3px rgba(180, 83, 9, .18)";
    toast("Payment baaki se zyada hai. Confirm dobara dabaiye to advance jama hoga.", "warn", 5000);
    return;
  }

  button.disabled = true;
  showBusy("Hisaab save ho raha hai…", "Database commit ke baad hi jawab milega");
  try {
    const result = await apiJson(`/api/pending/${state.pendingId}/confirm`, {
      method: "POST",
      body: { acknowledge_overpayment: needsAck && state.ackStep },
    });
    hideBusy();
    state.lastSpeech = result.speech_text || "";
    renderSuccess(result);
    await loadAll(false);
    speak(result.speech_text, { auto: true });
  } catch (error) {
    hideBusy();
    button.disabled = false;
    if (error.code === "overpayment_ack_required") {
      state.ackStep = false;
      if (proposal) {
        proposal.requires_overpayment_ack = true;
        renderProposal(proposal, null);
        const btn = $("#confirm-btn");
        if (btn) {
          btn.click();
        }
      }
      return;
    }
    if (error.code === "pending_expired" || error.code === "pending_cancelled" || error.code === "pending_not_found") {
      toast(error.message, "error", 5500);
      renderError(error);
      await loadAll(false);
      return;
    }
    toast(error.message, "error", 5500);
    renderError(error);
  }
}

function cancelSupersededProposal(pendingId) {
  if (!pendingId) return;
  // Fire-and-forget: the server marks it cancelled; the ledger is untouched.
  apiJson(`/api/pending/${encodeURIComponent(pendingId)}/cancel`, { method: "POST" })
    .catch(() => { /* already expired or cancelled — nothing to do */ });
}

async function cancelProposal() {
  if (!state.pendingId) {
    resetConversation();
    return;
  }
  const id = state.pendingId;
  showBusy("Cancel kar rahe hain…", "Ledger nahi badlega");
  try {
    await apiJson(`/api/pending/${id}/cancel`, { method: "POST" });
    hideBusy();
    state.proposal = null;
    state.pendingId = null;
    resultShell({
      accent: "amber",
      kicker: "Cancel ho gaya",
      title: "Koi transaction save nahi hua",
      sub: "Ledger bilkul waisa hi hai jaisa pehle tha.",
      body: `
        <div class="result-message">Aapne is entry ko cancel kar diya. Dobara bolne par naya preview banega.</div>
        <div class="answer-actions">
          <button type="button" class="btn btn-primary" data-action="new">Wapas bolein</button>
        </div>`,
    });
    toast("Transaction cancel — ledger nahi badla.", "success", 3200);
  } catch (error) {
    hideBusy();
    toast(error.message, "error");
    renderError(error);
  }
}

/* ------------------------------------------------------------------ */
/* Explicit customer creation                                         */
/* ------------------------------------------------------------------ */

function openAddCustomerForm(prefill = "") {
  const form = $("#add-customer-form");
  form.classList.remove("hidden");
  const input = $("#new-customer-name");
  if (prefill) input.value = prefill;
  form.scrollIntoView({ behavior: "smooth", block: "center" });
  window.setTimeout(() => input.focus({ preventScroll: true }), 250);
}

function closeAddCustomerForm() {
  $("#add-customer-form").classList.add("hidden");
  $("#new-customer-name").value = "";
}

async function handleAddCustomerSubmit(event) {
  event.preventDefault();
  const input = $("#new-customer-name");
  const name = input.value.trim();
  if (name.length < 2) {
    toast("Naam kam se kam 2 letters ka likhein.", "warn");
    return;
  }
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await apiJson("/api/customers", { method: "POST", body: { name } });
    toast(`${result.customer.name} ledger mein add ho gaye.`, "success", 3000);
    closeAddCustomerForm();
    await loadCustomers();
    state.lastCustomerName = result.customer.name;
  } catch (error) {
    toast(error.message, error.code === "customer_exists" ? "warn" : "error", 5000);
  } finally {
    button.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/* Manual correction                                                  */
/* ------------------------------------------------------------------ */

function openManualForm() {
  const proposal = state.proposal;
  const initialType = proposal?.type || "credit";
  const amount = proposal ? (proposal.amount_paise / 100).toFixed(2).replace(/\.00$/, "") : "";
  const transcript = state.lastTranscript || proposal?.transcript || "";

  const options = state.customers.map((customer) => `
    <option value="${customer.id}" ${proposal?.customer?.id === customer.id ? "selected" : ""}>
      ${escapeHtml(customer.name)} — ${escapeHtml(customer.balance_text)}
    </option>`).join("");

  const body = `
    <form class="manual-form" id="manual-form">
      <h3>Details theek karein</h3>
      <div class="form-grid">
        <label class="field full">Customer
          <select name="customer_id" required ${options ? "" : "disabled"}>
            ${options || '<option value="">Koi customer nahi</option>'}
          </select>
        </label>
        <div class="field full">Transaction type
          <div class="segmented" role="group" aria-label="Transaction type">
            <button type="button" class="seg-btn ${initialType === "credit" ? "is-active" : ""}" data-seg="credit">Udhaar diya</button>
            <button type="button" class="seg-btn ${initialType === "payment" ? "is-active" : ""}" data-seg="payment">Payment mila</button>
          </div>
        </div>
        <label class="field full">Amount (₹)
          <input name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" max="10000000" value="${escapeHtml(amount)}" placeholder="150" required />
        </label>
      </div>
      <input type="hidden" name="type" value="${initialType}" />
      <p class="fineprint">${transcript ? `Transcript: “${escapeHtml(transcript)}”` : "Yeh entry manual hai."}</p>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary">Preview banayein</button>
        <button type="button" class="btn btn-ghost" data-action="manual-cancel">Wapas</button>
      </div>
    </form>`;

  resultShell({
    accent: "amber",
    kicker: "Sahi karein",
    title: "Customer, type aur amount badlein",
    sub: "Preview phir bhi confirm karna zaroori hai.",
    body,
  });

  const form = $("#manual-form");
  if (!form) return;
  form.addEventListener("click", (event) => {
    const seg = event.target.closest("[data-seg]");
    if (!seg) return;
    form.querySelectorAll("[data-seg]").forEach((el) => el.classList.toggle("is-active", el === seg));
    form.querySelector('input[name="type"]').value = seg.dataset.seg;
  });
}

async function handleManualSubmit(event) {
  const form = event.target.closest("#manual-form");
  if (!form) return;
  event.preventDefault();
  const data = new FormData(form);
  const customerId = Number(data.get("customer_id"));
  const type = String(data.get("type") || "credit");
  const amount = Number(data.get("amount"));
  if (!customerId) {
    toast("Pehle customer chunein. Zarurat ho to pehle customer add karein.", "warn");
    return;
  }
  if (!Number.isFinite(amount) || amount <= 0) {
    toast("Amount zero se bada hona chahiye.", "warn");
    return;
  }
  showBusy("Preview ban raha hai…", "Koi transaction abhi save nahi hua");
  try {
    const response = await apiJson("/api/manual-proposal", {
      method: "POST",
      body: {
        customer_id: customerId,
        type,
        amount_rupees: amount.toFixed(2),
        transcript: state.lastTranscript || null,
      },
    });
    hideBusy();
    state.lastSpeech = response.speech_text || "";
    renderProposal(response.proposal, response);
  } catch (error) {
    hideBusy();
    toast(error.message, "error");
    renderError(error);
  }
}

function resetConversation() {
  state.proposal = null;
  state.pendingId = null;
  state.ackStep = false;
  state.manualOpen = false;
  $("#result-card").classList.add("hidden");
  $("#result-card").innerHTML = "";
  $("#transcript-card").classList.add("hidden");
  $("#transcript-meta").innerHTML = "";
  $("#transcript-confidence").hidden = true;
  $("#command-input").value = "";
  $("#voice-card").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#command-input").focus({ preventScroll: true });
}

/* ------------------------------------------------------------------ */
/* Recording                                                          */
/* ------------------------------------------------------------------ */

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

function pickMimeType() {
  if (!window.MediaRecorder || typeof MediaRecorder.isTypeSupported !== "function") return "";
  for (const mime of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(mime)) return mime;
    } catch { /* keep checking */ }
  }
  return "";
}

function setRecordingUI(active) {
  const mic = $("#mic-btn");
  mic.classList.toggle("is-recording", active);
  mic.setAttribute("aria-label", active ? "Recording band karein" : "Recording shuru karein");
  $("#waveform").classList.toggle("is-live", active);
  $("#mic-label").textContent = active ? t("mic_label_rec") : t("mic_label");
  $("#mic-hint").textContent = active ? t("mic_hint_rec") : t("mic_hint");
  if (!active) {
    $("#timer").textContent = "00:00";
  }
}

function updateTimer() {
  const elapsed = Math.min(MAX_SECONDS, (Date.now() - state.startedAt) / 1000);
  const seconds = Math.floor(elapsed);
  $("#timer").textContent = `00:${String(seconds).padStart(2, "0")}`;
  if (elapsed >= MAX_SECONDS && state.recording) {
    toast("30 second ho gaye — recording khud band ho gayi.", "info", 3500);
    stopRecording();
  }
}

async function startRecording() {
  if (state.recording) return;
  if (!state.health?.gnani?.stt_configured) {
    renderSetupNotice();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    toast("Is browser mein microphone recording support nahi hai. Neeche text box se likhein.", "error", 6000);
    $("#command-input").focus();
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    const name = error?.name;
    const message = name === "NotAllowedError"
      ? "Microphone permission nahi mili. Address bar ke mic icon se Allow karein."
      : name === "NotFoundError"
        ? "Koi microphone nahi mila. Mic jud kar page refresh karein."
        : name === "NotReadableError"
          ? "Microphone kisi aur app ne use kar liya hai. Doosri app band karein."
          : "Microphone shuru nahi ho paya. Text se command likh sakte hain.";
    toast(message, "error", 6500);
    return;
  }

  const mimeType = pickMimeType();
  let recorder;
  try {
    recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  } catch {
    stream.getTracks().forEach((track) => track.stop());
    toast("Recording shuru nahi ho payi. Browser ya FFmpeg setup check karein.", "error", 6000);
    return;
  }

  state.stream = stream;
  state.recorder = recorder;
  state.chunks = [];
  state.recording = true;
  state.startedAt = Date.now();
  setRecordingUI(true);

  recorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size > 0) state.chunks.push(event.data);
  });

  recorder.addEventListener("stop", () => {
    const blob = new Blob(state.chunks, { type: recorder.mimeType || mimeType || "audio/webm" });
    stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
    state.recorder = null;
    state.recording = false;
    window.clearInterval(state.timerId);
    state.timerId = null;
    setRecordingUI(false);
    if (blob.size < 900) {
      toast("Recording bahut chhoti thi. Mic paas rakh kar phir bolein.", "warn", 5000);
      return;
    }
    uploadRecording(blob);
  });

  try {
    recorder.start(250);
  } catch {
    state.recording = false;
    stream.getTracks().forEach((track) => track.stop());
    setRecordingUI(false);
    toast("Recording start nahi ho payi. Page refresh karein.", "error");
    return;
  }

  state.timerId = window.setInterval(updateTimer, 200);
  $("#timer").textContent = "00:00";
}

function stopRecording() {
  if (!state.recorder || !state.recording) return;
  state.recording = false;
  window.clearInterval(state.timerId);
  state.timerId = null;
  setRecordingUI(false);
  try {
    state.recorder.stop();
  } catch {
    toast("Recording band nahi ho payi.", "warn");
  }
}

async function uploadRecording(blob) {
  showBusy("Sun rahe hain…", "Gnani Prisma se transcript aa raha hai");
  const form = new FormData();
  const extension = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  form.append("file", blob, `voice.${extension}`);

  if (state.recordingUrl) URL.revokeObjectURL(state.recordingUrl);
  state.recordingUrl = URL.createObjectURL(blob);
  const audio = $("#recording-audio");
  audio.src = state.recordingUrl;
  $("#play-recording").hidden = false;

  try {
    const response = await fetch("/api/stt", { method: "POST", body: form });
    if (!response.ok) {
      let payload = null;
      try { payload = await response.json(); } catch { /* ignore */ }
      const error = new Error(payload?.error?.message || "Transcript nahi aaya.");
      error.code = payload?.error?.code || `http_${response.status}`;
      error.hint = payload?.error?.hint || null;
      throw error;
    }
    const result = await response.json();
    hideBusy();
    if (!result.transcript) {
      toast("Kuch samajh nahi aaya. Phir se saaf bolein.", "warn");
      return;
    }
    showTranscript(result.transcript, "voice");
    if (result.audio?.converted) {
      toast(`Awaaz ${String(result.audio.original_format || "").toUpperCase()} se WAV mein convert hui.`, "info", 2400);
    }
    await processText(result.transcript, { source: "voice" });
  } catch (error) {
    hideBusy();
    if (error.code === "gnani_not_configured") renderSetupNotice();
    else renderError(error);
  }
}

/* ------------------------------------------------------------------ */
/* Text to speech                                                     */
/* ------------------------------------------------------------------ */

async function speak(text, options = {}) {
  const clean = String(text || "").trim();
  if (!clean) return;

  if (!state.health?.gnani?.tts_configured) {
    if (!options.auto) {
      toast("Gnani Timbre configure nahi hai. Text reply screen par hai.", "warn", 4500);
    }
    return;
  }

  try {
    let url = state.ttsCache.get(clean);
    if (!url) {
      const response = await api("/api/tts", { method: "POST", body: { text: clean } });
      const blob = await response.blob();
      if (!blob.size) throw new Error("Awaaz khaali aayi.");
      url = URL.createObjectURL(blob);
      state.ttsCache.set(clean, url);
      if (state.ttsCache.size > 12) {
        const oldestKey = state.ttsCache.keys().next().value;
        const oldestUrl = state.ttsCache.get(oldestKey);
        if (oldestUrl) URL.revokeObjectURL(oldestUrl);
        state.ttsCache.delete(oldestKey);
      }
    }
    if (state.audio) {
      state.audio.pause();
      state.audio.currentTime = 0;
    }
    state.audio = new Audio(url);
    await state.audio.play();
  } catch (error) {
    if (!options.auto) toast(error.message || "Awaaz nahi aa saki. Text reply upar hai.", "warn", 5000);
  }
}

/* ------------------------------------------------------------------ */

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
