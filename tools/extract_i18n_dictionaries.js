// One-off: dump the dictionaries currently embedded in static/app.js into
// static/i18n/<lang>.json so they can be edited as data instead of code.
const fs = require("fs");
const path = require("path");

const app = fs.readFileSync("static/app.js", "utf8");

function grab(name) {
  const marker = `const ${name} = `;
  const start = app.indexOf(marker);
  if (start < 0) throw new Error(`${name} not found`);
  const open = app.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < app.length; i++) {
    const ch = app[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return app.slice(open, i + 1);
    }
  }
  throw new Error(`${name} unbalanced`);
}

const base = Function(`"use strict"; return (${grab("I18N")});`)();
const card = Function(`"use strict"; return (${grab("CARD_I18N")});`)();
const extra = Function(`"use strict"; return (${grab("EXTRA_I18N")});`)();

const outDir = path.join("static", "i18n");
fs.mkdirSync(outDir, { recursive: true });

for (const lang of Object.keys(base)) {
  const dict = { ...base[lang], ...(card[lang] || {}), ...(extra[lang] || {}) };
  const sorted = {};
  for (const key of Object.keys(dict).sort()) sorted[key] = dict[key];
  fs.writeFileSync(
    path.join(outDir, `${lang}.json`),
    JSON.stringify(sorted, null, 2) + "\n",
    "utf8"
  );
  console.log(lang, Object.keys(sorted).length);
}
