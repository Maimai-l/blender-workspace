// render.js - rasterize SVG files with Chromium. usage: node render.js W H scale in1.svg out1.png [in2.svg out2.png ...]
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [W, H, scale, ...pairs] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: +W, height: +H }, deviceScaleFactor: +scale });
  for (let i = 0; i < pairs.length; i += 2) {
    const t = Date.now();
    await page.goto('file://' + path.resolve(pairs[i]));
    const src = require('fs').readFileSync(pairs[i], 'utf8');
    await page.waitForTimeout(src.includes('fonts.googleapis') ? 2500 : 100);
    await page.screenshot({ path: pairs[i + 1], clip: { x: 0, y: 0, width: +W, height: +H } });
    console.log(pairs[i + 1], (Date.now() - t) + 'ms');
  }
  await browser.close();
})();
