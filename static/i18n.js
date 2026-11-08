/* Interface strings: one JSON file per language under /static/i18n/.
 *
 * `hisabsetu_lang` (the ten Gnani codes) is the single source of truth for both
 * the spoken language and the interface. A file is fetched on demand, cached in
 * memory and by the service worker, so switching language costs a fetch at most
 * once per session. English is the fallback for any key a translation misses.
 */

const I18N_PATH = "/static/i18n/";
const I18N_FALLBACK = "en";

const DICT_CACHE = new Map();
let ACTIVE_DICT = {};

/* "hi-IN" -> "hi"; Hinglish is the Roman-script variant of Hindi. */
function dictFileFor(code, hinglish) {
  if (hinglish && code === "hi-IN") return "hing";
  return String(code || "hi-IN").split("-")[0];
}

async function fetchDict(file) {
  if (DICT_CACHE.has(file)) return DICT_CACHE.get(file);
  let dict = {};
  try {
    // "no-cache" (revalidate against the server) rather than "force-cache":
    // a translation fix must reach the shopkeeper without a manual cache clear.
    const response = await fetch(`${I18N_PATH}${file}.json`, { cache: "no-cache" });
    if (response.ok) dict = await response.json();
  } catch {
    // Offline or blocked: English/raw keys are better than a blank screen.
    dict = {};
  }
  DICT_CACHE.set(file, dict);
  return dict;
}

async function loadDict(file) {
  const english = await fetchDict(I18N_FALLBACK);
  const own = file === I18N_FALLBACK ? english : await fetchDict(file);
  ACTIVE_DICT = { ...english, ...own };
  return ACTIVE_DICT;
}

/* Look up a key and fill {placeholders}. An unknown key returns the key itself
   so the parity test can spot it, never an empty label. */
function t(key, vars) {
  let value = ACTIVE_DICT[key];
  if (value === undefined) value = key;
  if (vars) {
    for (const [name, replacement] of Object.entries(vars)) {
      value = value.split(`{${name}}`).join(String(replacement));
    }
  }
  return value;
}

function dictLoaded() {
  return Object.keys(ACTIVE_DICT).length > 0;
}
