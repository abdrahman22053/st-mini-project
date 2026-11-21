#!/usr/bin/env bash
# Régénère rapport.pdf à partir de rapport.md (nécessite pandoc + Node.js avec Playwright/Chromium).
set -euo pipefail
cd "$(dirname "$0")"
pandoc rapport.md -s --embed-resources --css style.css -o rapport.html
node -e '
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage();
  await pg.goto("file://" + process.cwd() + "/rapport.html", { waitUntil: "load" });
  await pg.pdf({ path: "rapport.pdf", format: "A4", printBackground: true });
  await b.close();
})();'
rm rapport.html
echo "rapport.pdf généré"
