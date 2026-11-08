// Verifies every interface string the HTML/JS asks for actually exists in a
// dictionary, so a missing key can never render as a raw identifier.
// Dictionaries now live in static/i18n/<code>.json (en is the reference set).
const fs = require("fs");

const app = fs.readFileSync("static/app.js", "utf8");
const html = fs.readFileSync("templates/index.html", "utf8");

const codes = ["en", "hi", "hing", "mr", "bn", "gu", "kn", "ml", "pa", "ta", "te"];
const dicts = {};
for (const code of codes) {
  dicts[code] = JSON.parse(fs.readFileSync(`static/i18n/${code}.json`, "utf8"));
}
const reference = Object.keys(dicts.en);

let problems = 0;
for (const code of codes) {
  const missing = reference.filter((key) => !(key in dicts[code]));
  if (missing.length) {
    console.error(`${code}.json missing: ${missing.join(", ")}`);
    problems += missing.length;
  }
}

const used = new Set();
for (const match of html.matchAll(/data-i18n(?:-aria|-ph|-title)?="([^"]+)"/g)) used.add(match[1]);
for (const match of app.matchAll(/\bt\("([a-z][a-z0-9_]*)"\)/g)) used.add(match[1]);

const missing = [...used].filter((key) => !(key in dicts.en)).sort();
console.log(`i18n keys: ${reference.length} defined (en), ${used.size} used`);
console.log(`missing from en: ${missing.length ? missing.join(", ") : "none"}`);
problems += missing.length;

process.exit(problems ? 1 : 0);
