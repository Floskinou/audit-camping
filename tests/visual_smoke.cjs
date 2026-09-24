const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const output = path.join(root, '.hermes', 'previews');
const origin = 'http://127.0.0.1:8765/';
const audits = JSON.parse(fs.readFileSync(path.join(root, 'data', 'audits.json'), 'utf8'));
const alertCount = audits.filter(row => row.invalid_google_ads_purchase).length;
fs.mkdirSync(output, { recursive: true });

async function verify(browser, name, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await page.goto(origin, { waitUntil: 'domcontentloaded' });
  assert.equal(response.status(), 200);
  await page.evaluate(() => document.fonts.ready);

  const state = await page.evaluate(() => ({
    heading: document.querySelector('h1')?.textContent.trim(),
    h1: document.querySelectorAll('h1').length,
    best: document.querySelectorAll('[data-ranking="best"]').length,
    worst: document.querySelectorAll('[data-ranking="worst"]').length,
    rankLinks: [...document.querySelectorAll('.rank-entry a')].map(a => a.getAttribute('href')),
    catalogOpen: document.querySelector('#campings').open,
    logoWidth: document.querySelector('.site-header img').naturalWidth,
    cssLoaded: [...document.styleSheets].some(sheet => sheet.href?.endsWith('/redesign.css')),
    scrollWidth: document.documentElement.scrollWidth,
    viewport: innerWidth,
    heroLink: document.querySelector('.hero-cta').href,
    offerLink: document.querySelector('.offer-card .cta-button').href,
  }));
  assert.equal(state.h1, 1);
  assert.equal(state.best, 10);
  assert.equal(state.worst, 10);
  assert.equal(new Set(state.rankLinks).size, 20);
  assert.equal(state.catalogOpen, false);
  assert.equal(state.logoWidth, 560);
  assert.equal(state.cssLoaded, true);
  assert.ok(state.scrollWidth <= state.viewport + 1, `horizontal overflow ${name}: ${state.scrollWidth} > ${state.viewport}`);
  assert.ok(state.heroLink.startsWith('https://calendly.com/escaleads/30min'));
  assert.ok(state.offerLink.startsWith('https://calendly.com/escaleads/30min'));
  for (const href of state.rankLinks) assert.ok(fs.existsSync(path.join(root, href, 'index.html')), `missing ${href}`);

  await page.screenshot({ path: path.join(output, `home-${name}.png`) });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => document.getElementById('classements').scrollIntoView({ block: 'start' }));
  const rankAnchor = await page.evaluate(() => ({
    sectionTop: document.getElementById('classements').getBoundingClientRect().top,
    headerBottom: document.querySelector('.site-header').getBoundingClientRect().bottom,
  }));
  assert.ok(rankAnchor.sectionTop >= rankAnchor.headerBottom - 1,
            `anchor hidden by header ${name}: ${JSON.stringify(rankAnchor)}`);
  await page.screenshot({ path: path.join(output, `rankings-${name}.png`) });
  await page.evaluate(() => document.getElementById('offre').scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: path.join(output, `offer-${name}.png`) });

  await page.locator('.hero-secondary').click();
  assert.equal(await page.locator('#campings').evaluate(el => el.open), true);
  await page.locator('#filter-camping').fill('ÉMERAUDE');
  const searchMatches = await page.locator('.camping-card:not([hidden])').count();
  assert.ok(searchMatches >= 1 && searchMatches < 10, `accented search ${name}: ${searchMatches}`);
  await page.locator('#filter-camping').fill('');
  await page.locator('[data-filter-alerts]').click();
  assert.equal(await page.locator('#filter-score').inputValue(), 'critical');
  const filtered = await page.locator('.camping-card:not([hidden])').count();
  assert.equal(filtered, alertCount);
  assert.equal((await page.locator('#results-count').textContent()).trim(), `${alertCount} campings`);
  assert.equal(errors.length, 0, `browser errors ${name}: ${errors.join(' | ')}`);

  await page.goto(new URL(state.rankLinks[0], origin).href, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => document.fonts.ready);
  assert.ok((await page.locator('.camping-detail .cta-button').getAttribute('href')).startsWith('https://calendly.com/escaleads/30min'));
  assert.equal(await page.locator('.site-header img').evaluate(el => el.naturalWidth), 560);
  await page.screenshot({ path: path.join(output, `detail-${name}.png`) });
  const detailOverflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  assert.ok(detailOverflow <= 1, `detail overflow ${name}: ${detailOverflow}`);
  await context.close();
  console.log(JSON.stringify({ name, ...state, searchMatches, filtered, detailOverflow, errors }));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    await verify(browser, 'desktop', { width: 1440, height: 900 });
    await verify(browser, 'mobile', { width: 390, height: 844 });
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
