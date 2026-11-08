/* HisabSetu AI — frontend logic
   All money figures shown come from the SQLite ledger via the API.
   A transaction is only posted after an explicit confirm click. */

"use strict";

const MAX_SECONDS = 30;

const state = {
  hinglish: false, // Hinglish = hi-IN voice, Roman interface
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
  voiceLang: "hi-IN",
  voiceFallbackNoted: new Set(),
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

/* Interface strings live in /static/i18n/<lang>.json; see i18n.js. */

/* ------------------------------------------------------------------ */
/* One language: voice + interface                                     */
/* `hisabsetu_lang` is the only setting. Choosing a language changes    */
/* the spoken language, the TTS voice and every label on screen at      */
/* once — no reload, no second dropdown.                                */
/* ------------------------------------------------------------------ */

const LANGUAGE_KEY = "hisabsetu_lang"; // single source of truth (10 Gnani codes)
const SCRIPT_KEY = "hisabsetu_script"; // "latn" = Hinglish, spoken as hi-IN
const LEGACY_UI_KEY = "vk-ui-lang"; // removed setting, migrated once
const DEFAULT_LANGUAGE = "hi-IN";

const LANGUAGES = [
  { code: "hi-IN", name: "हिन्दी" },
  { code: "en-IN", name: "English" },
  { code: "bn-IN", name: "বাংলা" },
  { code: "gu-IN", name: "ગુજરાતી" },
  { code: "kn-IN", name: "ಕನ್ನಡ" },
  { code: "ml-IN", name: "മലയാളം" },
  { code: "mr-IN", name: "मराठी" },
  { code: "pa-IN", name: "ਪੰਜਾਬੀ" },
  { code: "ta-IN", name: "தமிழ்" },
  { code: "te-IN", name: "తెలుగు" },
];

function isKnownLanguage(code) {
  return LANGUAGES.some((entry) => entry.code === code);
}

function languageMeta(code) {
  return LANGUAGES.find((entry) => entry.code === code) || LANGUAGES[0];
}

/* Storage can be blocked (private mode, embedded browsers). Never throw. */
function storageAvailable() {
  try {
    const probe = "__hisabsetu_probe";
    localStorage.setItem(probe, "1");
    localStorage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* in-memory only */
  }
}

function readStoredLanguage() {
  const saved = readStored(LANGUAGE_KEY);
  return saved && isKnownLanguage(saved) ? saved : null;
}

/* Older builds kept a second, interface-only setting in `vk-ui-lang`
   (hi / hing / en / mr). Fold it into the one setting and delete it. */
function migrateLegacyLanguage() {
  const legacy = readStored(LEGACY_UI_KEY);
  if (legacy !== null) {
    const map = { hi: "hi-IN", hing: "hi-IN", mr: "mr-IN", en: "en-IN" };
    if (map[legacy] && !readStoredLanguage()) writeStored(LANGUAGE_KEY, map[legacy]);
    if (legacy === "hing") writeStored(SCRIPT_KEY, "latn");
    writeStored(LEGACY_UI_KEY, null);
  }
}

function usesRomanScript(code) {
  return (code || state.voiceLang) === "hi-IN" && state.hinglish === true;
}

let UI_FILE = "hi";

/* Load a dictionary, then put its text everywhere in the document. */
async function applyLanguage(file) {
  UI_FILE = file;
  await loadDict(file);
  document.documentElement.lang = state.voiceLang || DEFAULT_LANGUAGE;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.setAttribute("placeholder", t(el.dataset.i18nPh));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.setAttribute("title", t(el.dataset.i18nTitle));
  });

  document.title = t("app_title");
  const manifest = document.querySelector('link[rel="manifest"]');
  if (manifest) {
    const params = new URLSearchParams({ lang: state.voiceLang || DEFAULT_LANGUAGE });
    if (state.hinglish) params.set("script", "latn");
    manifest.setAttribute("href", `/manifest.webmanifest?${params.toString()}`);
  }
  refreshDynamicLabels();
}

/* Re-render text that is generated by JS so it follows the language. */
function refreshDynamicLabels() {
  if (state.dashboard) {
    const net = t("net_word");
    const entries = t("entries_word");
    const customers = t("customers_word");
    $("#today-net").textContent = `${net} ${state.dashboard.today_net_text} · ${state.dashboard.today_transaction_count} ${entries}`;
    $("#outstanding-customer-count").textContent = `${state.dashboard.customer_count} ${customers}`;
  }
  $("#mic-label").textContent = state.recording ? t("mic_label_rec") : t("mic_label");
  $("#mic-hint").textContent = state.recording ? t("mic_hint_rec") : t("mic_hint");
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

/* Switch language: voice, voice replies and every label, in one step. */
async function setLanguage(code, options = {}) {
  const next = isKnownLanguage(code) ? code : DEFAULT_LANGUAGE;
  const hinglish = Boolean(options.hinglish) && next === "hi-IN";
  state.voiceLang = next;
  state.hinglish = hinglish;
  if (options.persist !== false) {
    writeStored(LANGUAGE_KEY, next);
    writeStored(SCRIPT_KEY, hinglish ? "latn" : null);
  }
  // Voice replies are language specific: drop cached audio from the old one.
  for (const url of state.ttsCache.values()) URL.revokeObjectURL(url);
  state.ttsCache.clear();
  renderLangSwitch();
  markLanguageCards();
  await applyLanguage(dictFileFor(next, hinglish));
  return next;
}

/* Header switch: [chosen language] [English]. English is hidden when English
   is already the chosen language — there is nothing left to switch to. */
function renderLangSwitch() {
  const wrap = $("#lang-switch");
  const changeButton = $("#lang-change");
  if (!wrap || !changeButton) return;
  changeButton.hidden = false;
  const meta = languageMeta(state.voiceLang);
  // The first button is always the chosen language, the second is English.
  // (Finding "chosen" by excluding en-IN breaks after English is picked,
  // because the chosen button then carries en-IN too.)
  const buttons = wrap.querySelectorAll("button");
  const chosen = buttons[0] || null;
  const english = buttons[1] || null;
  if (chosen) {
    chosen.dataset.voiceLang = meta.code;
    chosen.textContent = state.hinglish ? t("hinglish_card") : meta.name;
    const active = meta.code !== "en-IN";
    chosen.classList.toggle("is-active", active);
    chosen.setAttribute("aria-pressed", active ? "true" : "false");
  }
  if (english) {
    const active = meta.code === "en-IN";
    english.classList.toggle("is-active", active);
    english.setAttribute("aria-pressed", active ? "true" : "false");
  }
  wrap.hidden = meta.code === "en-IN";
}

function buildLanguageGrid() {
  const grid = $("#lang-grid");
  if (!grid) return;
  const cards = LANGUAGES.map((entry) => `
    <button type="button" class="lang-card" role="radio" aria-checked="false"
      data-lang="${escapeHtml(entry.code)}">
      <span class="lang-card-name">${escapeHtml(entry.name)}</span>
      <span class="lang-card-code">${escapeHtml(entry.code)}</span>
    </button>`);
  // Hinglish writes Hindi in Roman script: same hi-IN voice and parser.
  cards.push(`
    <button type="button" class="lang-card" role="radio" aria-checked="false"
      data-lang="hi-IN" data-script="latn">
      <span class="lang-card-name">Hinglish</span>
      <span class="lang-card-code">hi-IN · Roman</span>
    </button>`);
  grid.innerHTML = cards.join("");
}

function markLanguageCards() {
  document.querySelectorAll("#lang-grid .lang-card").forEach((card) => {
    const sameLanguage = card.dataset.lang === state.voiceLang;
    const roman = card.dataset.script === "latn";
    const selected = sameLanguage && roman === Boolean(state.hinglish);
    card.classList.toggle("is-selected", selected);
    card.setAttribute("aria-checked", selected ? "true" : "false");
    card.tabIndex = selected ? 0 : -1;
  });
}

let langModalReturnFocus = null;

function openLanguageModal(options = {}) {
  buildLanguageGrid();
  const modal = $("#lang-modal");
  if (!modal) return;
  markLanguageCards();
  modal.dataset.firstRun = options.firstRun ? "1" : "0";
  modal.hidden = false;
  document.body.classList.add("lang-modal-open");
  langModalReturnFocus = document.activeElement;
  const selected = modal.querySelector(".lang-card.is-selected") || modal.querySelector(".lang-card");
  if (selected) selected.focus();
}

function closeLanguageModal() {
  const modal = $("#lang-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  modal.dataset.firstRun = "0";
  document.body.classList.remove("lang-modal-open");
  if (langModalReturnFocus && typeof langModalReturnFocus.focus === "function") {
    langModalReturnFocus.focus();
  }
  langModalReturnFocus = null;
}

async function chooseLanguage(code, hinglish = false) {
  if (!isKnownLanguage(code)) return;
  await setLanguage(code, { hinglish });
  closeLanguageModal();
  toast(t("toast_language_set", { name: languageMeta(code).name }), "success", 2600);
}

async function initLanguage() {
  migrateLegacyLanguage();
  const stored = readStoredLanguage();
  if (stored) {
    await setLanguage(stored, {
      persist: false,
      hinglish: readStored(SCRIPT_KEY) === "latn",
    });
    return;
  }
  await setLanguage(DEFAULT_LANGUAGE, { persist: false });
  openLanguageModal({ firstRun: true });
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

const INTENT_KEYS = {
  add_credit: "intent_credit",
  record_payment: "intent_payment",
  balance_query: "intent_balance",
  top_debtor: "intent_top",
  daily_summary: "intent_daily",
};

function intentLabel(intent) {
  return t(INTENT_KEYS[intent] || "cmd_label");
}

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

  // Voice language: segmented quick switch, change button and menu item.
  const langSwitch = $("#lang-switch");
  if (langSwitch) {
    langSwitch.addEventListener("click", (event) => {
      const button = event.target.closest("[data-voice-lang]");
      if (!button) return;
      if (button.dataset.voiceLang === "en-IN") setLanguage("en-IN");
      else openLanguageModal();
    });
  }
  const langChange = $("#lang-change");
  if (langChange) langChange.addEventListener("click", () => openLanguageModal());
  const langMenuItem = $("#lang-menu-item");
  if (langMenuItem) langMenuItem.addEventListener("click", () => openLanguageModal());

  const langModal = $("#lang-modal");
  if (langModal) {
    langModal.addEventListener("click", (event) => {
      const card = event.target.closest("[data-lang]");
      if (card) {
        chooseLanguage(card.dataset.lang, card.dataset.script === "latn");
        return;
      }
      // Clicking the backdrop closes it, except on the very first run.
      if (event.target === langModal && langModal.dataset.firstRun !== "1") closeLanguageModal();
    });
    langModal.addEventListener("keydown", (event) => {
      const cards = Array.from(langModal.querySelectorAll(".lang-card"));
      if (!cards.length) return;
      const index = cards.indexOf(document.activeElement);
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        cards[(index + 1 + cards.length) % cards.length].focus();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        cards[(index - 1 + cards.length) % cards.length].focus();
      } else if (event.key === "Escape" && langModal.dataset.firstRun !== "1") {
        event.preventDefault();
        closeLanguageModal();
      }
    });
  }

  $("#mic-btn").addEventListener("click", () => {
    if (state.recording) stopRecording();
    else startRecording();
  });

  $("#text-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = $("#command-input").value.trim();
    if (!value) {
      toast(t("toast_need_command"), "warn");
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
    audio.play().catch(() => toast(t("toast_play_failed"), "warn"));
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
  bindEvents();
  await initLanguage();
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
    toast(t("toast_refresh_done"), "success", 2400);
  }
}

async function loadHealth(announce) {
  const health = await apiJson("/api/health");
  state.health = health;
  renderHealth(health);
  if (announce) toast(t("toast_status_refreshed"), "success", 2400);
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
  pill.innerHTML = `<span class="dot"></span>${escapeHtml(sttOk ? t("voice_ready") : t("voice_text_mode"))}`;

  $("#status-note").innerHTML = sttOk
    ? "Mic se bolein ya text likhein. Har transaction confirm karne ke baad hi save hota hai."
    : "Voice ke liye <code>.env</code> mein <code>GNANI_API_KEY</code> set karke server restart karein. Text commands abhi bhi poore kaam karte hain.";
}

function balanceMeta(paise) {
  if (paise > 0) return { cls: "balance-baaki", label: t("balance_baaki") };
  if (paise < 0) return { cls: "balance-advance", label: t("balance_advance") };
  return { cls: "balance-clear", label: t("balance_clear") };
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
        <button class="cust-ask" type="button" data-ask-customer="${escapeHtml(customer.name)}">${escapeHtml(t("ask_customer"))}</button>
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
  $("#daily-date").textContent = summary.date_label || t("aaj");
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
    : `<li class="top-empty">${escapeHtml(t("top_empty"))}</li>`;

  const reminders = summary.reminders || [];
  $("#daily-reminders").innerHTML = reminders.length
    ? reminders.map((text) => `<li>${escapeHtml(text)}</li>`).join("")
    : `<li>${escapeHtml(t("reminder_empty"))}</li>`;
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
    toast(t("toast_need_command"), "warn");
    return;
  }
  const input = $("#command-input");
  input.value = text;
  input.focus();
  input.setSelectionRange(text.length, text.length);
  input.scrollIntoView({ behavior: "smooth", block: "center" });
  toast(t("toast_edit_transcript"), "info", 4500);
}

function renderTranscriptMeta(parser, source) {
  state.lastCustomerName = parser?.customer_name || "";
  const chips = [];
  chips.push(`<span class="meta-chip">${escapeHtml(source === "voice" ? t("meta_voice") : t("meta_text"))}</span>`);
  if (parser?.intent) {
    chips.push(`<span class="meta-chip"><b>${escapeHtml(t("meta_action"))}:</b> ${escapeHtml(intentLabel(parser.intent))}</span>`);
  }
  if (parser?.amount_text) {
    chips.push(`<span class="meta-chip"><b>${escapeHtml(t("meta_amount"))}:</b> ${escapeHtml(parser.amount_text)}</span>`);
  }
  if (parser?.customer_name) {
    chips.push(`<span class="meta-chip"><b>${escapeHtml(t("row_customer"))}:</b> ${escapeHtml(parser.customer_name)}</span>`);
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
    toast(t("toast_need_command"), "warn");
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

  showBusy(t("busy_understanding"), t("busy_understanding_sub"));

  try {
    const payload = {
      text: clean,
      source: options.source === "voice" ? "voice" : "text",
      language: state.voiceLang,
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
          ${escapeHtml(isCredit ? t("type_credit") : t("type_payment"))}
        </span>
        <div class="confirm-amount">${escapeHtml(proposal.amount_text)}</div>
        <div class="result-sub">${escapeHtml(isCredit ? t("credit_note") : t("payment_note"))}</div>
      </div>
      <span class="badge">${escapeHtml(t("pending_badge"))}</span>
    </div>

    <div class="confirm-rows">
      <div class="confirm-row">
        <span class="k">${escapeHtml(t("row_customer"))}</span>
        <span class="customer-line">
          <span class="avatar">${escapeHtml(initials(customer.name))}</span>
          <span>
            <span class="name">${escapeHtml(customer.name)}</span>
            <span class="sub">${escapeHtml(t("row_now"))} ${escapeHtml(customer.balance_text)}</span>
          </span>
        </span>
      </div>
      <div class="confirm-row">
        <span class="k">${escapeHtml(t("row_new"))}</span>
        <span class="v balance-flow">
          <span class="now">${escapeHtml(proposal.balance_before_text)}</span>
          <span class="arrow">${ICONS.arrow}</span>
          <span class="next">${escapeHtml(proposal.balance_after_text)}</span>
        </span>
      </div>
      <div class="confirm-row">
        <span class="k">${escapeHtml(t("row_said"))}</span>
        <span class="v" style="font-weight:500;max-width:70%;overflow-wrap:anywhere">${escapeHtml(proposal.transcript)}</span>
      </div>
    </div>

    ${ack ? `
      <div class="warn-box" id="ack-warning">
        ${ICONS.alert}
        <div>
          <strong>${escapeHtml(t("ack_title"))}</strong>
          ${escapeHtml(t("ack_body")
            .replace("{name}", customer.name)
            .replace("{balance}", customer.balance_text)
            .replace("{advance}", moneyAbs(proposal.balance_after_text)))}
        </div>
      </div>` : ""}

    <div class="result-message">${escapeHtml(proposal.message)}</div>

    <div class="confirm-actions">
      <button type="button" class="btn btn-primary" data-action="confirm" id="confirm-btn">
        ${ICONS.check} ${escapeHtml(t("btn_confirm"))}
      </button>
      <button type="button" class="btn btn-secondary" data-action="cancel">${escapeHtml(t("btn_cancel"))}</button>
      <button type="button" class="btn btn-ghost btn-correct" data-action="correct">${escapeHtml(t("btn_correct"))}</button>
    </div>

    <div class="pending-foot">
      <span>${ICONS.shield} ${escapeHtml(t("foot_save"))} · ${escapeHtml(whenLabel(proposal.expires_at))} ${escapeHtml(t("foot_valid"))}</span>
      <button type="button" class="btn btn-ghost btn-sm" data-action="speak">${ICONS.speaker} ${escapeHtml(t("btn_speak"))}</button>
    </div>`;

  resultShell({
    accent: ack ? "amber" : "",
    kicker: t("card_kicker"),
    title: t("card_title"),
    sub: t("card_sub"),
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
              <span class="sub" style="display:block;font-size:11px;color:var(--muted)">${escapeHtml(customer.balance_text)} ${escapeHtml(t("pick_due"))}</span>
            </span>
          </span>
          <span class="pick-balance">${escapeHtml(t("pick_choose"))} ${ICONS.arrow}</span>
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
            <span class="compound-label">${escapeHtml(command.intent_label || command.intent || t("cmd_label"))}${command.amount_text ? ` · ${escapeHtml(command.amount_text)}` : ""}</span>
            <span class="compound-text">“${escapeHtml(command.text)}”</span>
          </span>
          <button type="button" class="btn btn-secondary btn-small" data-action="example" data-text="${escapeHtml(command.text)}">${escapeHtml(t("compound_run"))}</button>
        </li>`).join("")}</ol>`
    : "";

  const exampleChips = examples.length
    ? `<div class="chips" style="margin-top:12px">${examples.slice(0, 3).map((example) => `
        <button type="button" class="chip" data-action="example" data-text="${escapeHtml(example)}">${escapeHtml(example)}</button>`).join("")}</div>`
    : "";

  resultShell({
    accent: "amber",
    kicker: t("clarify_kicker"),
    title: isCompound
      ? t("clarify_compound").replace("{count}", String(commands.length))
      : clarification.needs?.includes("customer") ? t("clarify_title_customer") : t("clarify_title_detail"),
    sub: t("clarify_sub"),
    body: `
      <div class="result-message speech">${escapeHtml(clarification.question || data.message)}</div>
      ${commandList}
      ${picks}
      ${exampleChips}
      <div class="answer-actions">
        ${clarification.needs?.includes("customer") ? `<button type="button" class="btn btn-secondary" data-action="add-customer">${escapeHtml(t("btn_add_customer"))}</button>` : ''}
        <button type="button" class="btn btn-secondary" data-action="correct">${escapeHtml(t("btn_fill_details"))}</button>
        <button type="button" class="btn btn-ghost" data-action="new">${escapeHtml(t("btn_new_command"))}</button>
      </div>`,
  });
}

function renderAnswer(data) {
  const answer = data.answer || {};
  const summary = answer.summary || {};
  let body = "";
  let title = t("answer_title");
  let kicker = t("answer_kicker");
  let accent = "blue";

  if (answer.kind === "balance") {
    const customer = answer.customer || {};
    title = t("ans_customer_title").replace("{name}", customer.name || t("row_customer"));
    const advance = answer.balance_paise < 0;
    body = `
      <div class="answer-value">${escapeHtml(advance ? moneyAbs(answer.balance_text) : answer.balance_text)}</div>
      <div class="answer-label">${escapeHtml(advance ? t("ans_advance") : answer.balance_paise === 0 ? t("ans_clear") : t("kul_baaki"))}</div>
      <div class="result-message speech">${escapeHtml(data.message)}</div>
      ${customer.id ? `
        <div class="answer-rows">
          <div class="answer-row"><span class="k">${escapeHtml(t("row_customer"))}</span><span class="v">${escapeHtml(customer.name)}</span></div>
          <div class="answer-row"><span class="k">${escapeHtml(t("recent_entries"))}</span><span class="v">${(answer.transactions || []).length}</span></div>
        </div>` : ""}`;
  } else if (answer.kind === "top_debtor") {
    const customers = answer.customers || [];
    accent = "amber";
    title = t("sabse_zyada");
    body = `
      ${customers.length ? `
        <div class="answer-value">${escapeHtml(customers[0].balance_text)}</div>
        <div class="answer-label">${escapeHtml(t("ans_top_label").replace("{name}", customers[0].name))}</div>
        <div class="answer-rows">
          ${customers.map((customer, index) => `
            <div class="answer-row">
              <span class="k">${index + 1}. ${escapeHtml(customer.name)}</span>
              <span class="v">${escapeHtml(customer.balance_text)}</span>
            </div>`).join("")}
        </div>` : `<div class="result-message">${escapeHtml(t("top_empty"))}</div>`}
      <div class="result-message speech">${escapeHtml(data.message)}</div>`;
  } else if (answer.kind === "daily_summary") {
    title = t("answer_daily_title");
    body = `
      <div class="answer-rows" style="margin-top:0">
        <div class="answer-row"><span class="k">${escapeHtml(t("udhaar_diya"))}</span><span class="v credit-text">${escapeHtml(summary.credit_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">${escapeHtml(t("jama_hua"))}</span><span class="v payment-text">${escapeHtml(summary.payment_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">${escapeHtml(t("net_badlav"))}</span><span class="v">${escapeHtml(summary.net_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">${escapeHtml(t("kul_baaki"))}</span><span class="v">${escapeHtml(summary.total_outstanding_text || "₹0")}</span></div>
        <div class="answer-row"><span class="k">${escapeHtml(t("entries_label"))}</span><span class="v">${Number(summary.transaction_count || 0)}</span></div>
      </div>
      <div class="result-message speech">${escapeHtml(data.message)}</div>
      ${(summary.reminders || []).length ? `
        <div class="reminder-box">
          <div class="reminder-title">${ICONS.info} ${escapeHtml(t("reminder_hint_title"))}</div>
          <ul>${summary.reminders.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
        </div>` : ""}`;
  } else {
    body = `<div class="result-message">${escapeHtml(data.message)}</div>`;
  }

  resultShell({
    accent,
    kicker,
    title,
    sub: t("answer_sub"),
    body,
    foot: `
      <div class="answer-actions">
        <button type="button" class="btn btn-primary" data-action="speak">${ICONS.speaker} ${escapeHtml(t("btn_speak"))}</button>
        <button type="button" class="btn btn-secondary" data-action="new">${escapeHtml(t("btn_new_command"))}</button>
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
    kicker: already ? t("success_kicker_saved") : t("success_kicker"),
    title: already ? t("success_title_saved") : t("success_title"),
    sub: t("success_sub"),
    body: `
      <div class="success-hero">
        <div class="success-badge">${ICONS.check}</div>
        <div class="success-amount">${isCredit ? "+" : "−"}${escapeHtml(txn.amount_text || "₹0")}</div>
        <div class="success-note">${escapeHtml(customer.name || "")} · ${escapeHtml(isCredit ? t("success_credit_note") : t("success_payment_note"))}</div>
        <div class="success-balance">${escapeHtml(balance < 0 ? t("success_now_advance") : t("success_now_baaki"))} <strong>${escapeHtml(balance < 0 ? moneyAbs(customer.balance_text || "₹0") : customer.balance_text || "₹0")}</strong></div>
      </div>
      <div class="result-message speech">${escapeHtml(result.message)}</div>
      <div class="answer-actions">
        <button type="button" class="btn btn-primary" data-action="speak">${ICONS.speaker} ${escapeHtml(t("btn_speak_again"))}</button>
        <button type="button" class="btn btn-secondary" data-action="new">${escapeHtml(t("btn_new"))}</button>
      </div>`,
  });
}

function renderError(error) {
  const setup = error.code === "gnani_not_configured";
  const title = setup ? t("err_setup_title") : error.code === "network_error" ? t("err_network_title") : t("err_generic_title");
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
      <button type="button" class="btn btn-primary" data-action="setup-text">${escapeHtml(t("err_text_cta"))}</button>
      <button type="button" class="btn btn-secondary" data-action="retry">${escapeHtml(t("err_retry"))}</button>
    </div>`;
  resultShell({
    accent: "red",
    kicker: t("err_kicker"),
    title,
    sub: t("err_sub"),
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
      toast(t("toast_need_command"), "warn");
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
    toast(t("toast_text_hint"), "info");
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
    toast(t("toast_overpay_ack"), "warn", 5000);
    return;
  }

  button.disabled = true;
  showBusy(t("busy_saving"), t("busy_saving_sub"));
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
  showBusy(t("busy_cancelling"), t("busy_cancelling_sub"));
  try {
    await apiJson(`/api/pending/${id}/cancel`, { method: "POST" });
    hideBusy();
    state.proposal = null;
    state.pendingId = null;
    resultShell({
      accent: "amber",
      kicker: t("cancel_kicker"),
      title: t("cancel_title"),
      sub: t("cancel_sub"),
      body: `
        <div class="result-message">${escapeHtml(t("cancel_body"))}</div>
        <div class="answer-actions">
          <button type="button" class="btn btn-primary" data-action="new">${escapeHtml(t("cancel_cta"))}</button>
        </div>`,
    });
    toast(t("toast_cancel_done"), "success", 3200);
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
    toast(t("toast_name_short"), "warn");
    return;
  }
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await apiJson("/api/customers", { method: "POST", body: { name } });
    toast(t("toast_customer_added", { name: result.customer.name }), "success", 3000);
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
    toast(t("toast_pick_customer"), "warn");
    return;
  }
  if (!Number.isFinite(amount) || amount <= 0) {
    toast(t("toast_amount_positive"), "warn");
    return;
  }
  showBusy(t("busy_preview"), t("busy_preview_sub"));
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
  showBusy(t("busy_listening"), t("busy_transcribing"));
  const form = new FormData();
  const extension = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  form.append("file", blob, `voice.${extension}`);
  form.append("language", state.voiceLang);

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
    const cacheKey = `${state.voiceLang}|${clean}`;
    let url = state.ttsCache.get(cacheKey);
    if (!url) {
      const response = await api("/api/tts", {
        method: "POST",
        body: { text: clean, language: state.voiceLang },
      });
      const blob = await response.blob();
      if (!blob.size) throw new Error("Awaaz khaali aayi.");
      // The server says when this language has no voice of its own.
      if (response.headers.get("x-voice-fallback") === "true") {
        const spokenIn = response.headers.get("x-voice-language") || "en-IN";
        if (!state.voiceFallbackNoted.has(state.voiceLang)) {
          state.voiceFallbackNoted.add(state.voiceLang);
          toast(
            `${languageMeta(state.voiceLang).name} ke liye awaaz nahi hai — jawab ${spokenIn} awaaz mein sunaya gaya.`,
            "warn",
            6000
          );
        }
      }
      url = URL.createObjectURL(blob);
      state.ttsCache.set(cacheKey, url);
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
