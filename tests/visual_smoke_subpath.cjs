// Smoke test du miroir escale-ads.com/tracking-camping servi sous /tracking-camping/.
// Usage: serveur racine du worktree cible sur 127.0.0.1:8767, puis node tests/...
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const origin = 'http://127.0.0.1:8767/tracking-camping/';

async function verify(browser, name, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400) errors.push(`HTTP ${response.status()} ${response.url()}`);
  });

  const response = await page.goto(origin, { waitUntil: 'domcontentloaded' });
  assert.equal(response.status(), 200);
  await page.evaluate(() => document.fonts.ready);

  const state = await page.evaluate(() => ({
    canonical: document.querySelector('link[rel="canonical"]')?.href,
    best: document.querySelectorAll('[data-ranking="best"]').length,
    worst: document.querySelectorAll('[data-ranking="worst"]').length,
    cssLoaded: [...document.styleSheets].some(sheet => sheet.href?.includes('/tracking-camping/assets/css/redesign.css')),
    overflow: document.documentElement.scrollWidth - innerWidth,
    rankHrefs: [...document.querySelectorAll('.rank-entry a')].map(a => a.getAttribute('href')),
  }));
  assert.equal(state.canonical, 'https://escale-ads.com/tracking-camping/');
  assert.equal(state.best, 10);
  assert.equal(state.worst, 10);
  assert.equal(state.cssLoaded, true);
  assert.ok(state.overflow <= 1, `overflow ${name}: ${state.overflow}`);
  assert.ok(state.rankHrefs.length === 20 && state.rankHrefs.every(href => href.startsWith('campings/') && href.endsWith('index.html')));

  await page.locator('.rank-entry a').first().click();
  await page.waitForLoadState('domcontentloaded');
  assert.match(page.url(), /\/tracking-camping\/campings\/[^/]+\/index\.html$/);
  const detail = await page.evaluate(() => ({
    canonical: document.querySelector('link[rel="canonical"]')?.href,
    h1: document.querySelectorAll('h1').length,
    cssLoaded: [...document.styleSheets].some(sheet => sheet.href?.includes('/tracking-camping/assets/css/redesign.css')),
    overflow: document.documentElement.scrollWidth - innerWidth,
  }));
  assert.ok(detail.canonical?.startsWith('https://escale-ads.com/tracking-camping/campings/'), detail.canonical);
  assert.equal(detail.h1, 1);
  assert.equal(detail.cssLoaded, true);
  assert.ok(detail.overflow <= 1, `detail overflow ${name}: ${detail.overflow}`);

  // Le fil d'Ariane est visible en desktop comme en mobile (la nav d'en-tête
  // est masquée sous 860px par la refonte).
  await page.locator('.breadcrumb a').first().click();
  await page.waitForLoadState('domcontentloaded');
  const backUrl = new URL(page.url());
  assert.equal(backUrl.origin + backUrl.pathname, origin);

  await page.locator('[data-filter-alerts]').click();
  const filtered = await page.locator('.camping-card:not([hidden])').count();
  assert.equal(filtered, 17, `alert filter ${name}: ${filtered}`);

  assert.deepEqual(errors, [], `browser errors ${name}: ${errors.join(' | ')}`);
  await context.close();
  return { name, ...state, filtered, detailCanonical: detail.canonical };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    console.log(JSON.stringify(await verify(browser, 'desktop', { width: 1440, height: 900 })));
    console.log(JSON.stringify(await verify(browser, 'mobile', { width: 390, height: 844 })));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
