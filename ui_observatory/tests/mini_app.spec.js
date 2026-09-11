const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { AxeBuilder } = require('@axe-core/playwright');

const screens = [
  ['home', 'nh'],
  ['wallet', 'nw'],
  ['transfer', 'nt'],
  ['buy', 'nb'],
  ['stake', 'ns'],
  ['alpha', 'na'],
  ['academy', 'nc'],
];

async function mockBackend(page) {
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    let body = {};
    if (url.pathname === '/api/v1/me') {
      body = { name: 'UI Test User', credits: 21994384, token_balance: 21650000, staked: 1, points: 110, referrals: 0 };
    } else if (url.pathname.startsWith('/api/wallet/')) {
      body = { name: 'UI Test User', credits: 21994384, staked: 1, token_balance: 21650000, ton_wallet: null };
    } else if (url.pathname === '/api/onchain/status') {
      body = { bnb: { status: 'pending' }, ton: { status: 'pending' } };
    } else if (url.pathname.includes('leaderboard')) {
      body = [];
    } else if (url.pathname.includes('tasks')) {
      body = [];
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

async function assertOrCreateScreenshot(page, testInfo, name) {
  const snapshot = testInfo.snapshotPath(name);
  if (fs.existsSync(snapshot)) {
    await expect(page).toHaveScreenshot(name, { fullPage: true });
  } else {
    await page.screenshot({ path: snapshot, fullPage: true });
  }
}

async function clickScreen(page, id) {
  await page.locator(`#${id}`).click();
  await expect(page.locator(`#${id.replace(/^n/, '')}`)).toHaveClass(/active/);
}

test.beforeEach(async ({ page }) => {
  await mockBackend(page);
  await page.goto(process.env.SLH_UI_BASE_URL || '/mini-app');
  await page.waitForLoadState('domcontentloaded');
});

test('all primary screens are reachable', async ({ page }) => {
  const seen = [];
  for (const [id, buttonId] of screens) {
    await page.locator(`#${buttonId}`).click();
    await expect(page.locator(`#${id}`)).toHaveClass(/active/);
    seen.push(id);
  }
  expect(seen).toEqual(screens.map(([id]) => id));
});

test('mobile layout has no horizontal overflow', async ({ page }) => {
  const metrics = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewport + 2);
  expect(metrics.bodyWidth).toBeLessThanOrEqual(metrics.viewport + 2);
});

test('interactive controls have usable names and form fields are labelled', async ({ page }) => {
  const unnamed = await page.locator('button').evaluateAll(buttons => buttons.filter(b => !(b.innerText || b.getAttribute('aria-label') || '').trim()).length);
  expect(unnamed).toBe(0);

  await page.locator('#nt').click();
  await expect(page.locator('#recipient')).toHaveAttribute('id', 'recipient');
  await expect(page.locator('label[for="recipient"]')).toBeVisible();
  await expect(page.locator('label[for="amount"]')).toBeVisible();
});

test('accessibility audit has no serious or critical violations', async ({ page }) => {
  const results = await new AxeBuilder({ page }).analyze();
  const seriousOrCritical = results.violations.filter(v => ['serious', 'critical'].includes(v.impact));
  expect(seriousOrCritical).toEqual([]);
});

test('visual baseline: home', async ({ page }, testInfo) => {
  await page.locator('#nh').click();
  await assertOrCreateScreenshot(page, testInfo, 'home.png');
});

test('visual baseline: wallet', async ({ page }, testInfo) => {
  await page.locator('#nw').click();
  await assertOrCreateScreenshot(page, testInfo, 'wallet.png');
});

test('visual baseline: transfer', async ({ page }, testInfo) => {
  await page.locator('#nt').click();
  await assertOrCreateScreenshot(page, testInfo, 'transfer.png');
});

test('visual baseline: buy', async ({ page }, testInfo) => {
  await page.locator('#nb').click();
  await assertOrCreateScreenshot(page, testInfo, 'buy.png');
});

test('visual baseline: staking', async ({ page }, testInfo) => {
  await page.locator('#ns').click();
  await assertOrCreateScreenshot(page, testInfo, 'stake.png');
});

test('visual baseline: alpha', async ({ page }, testInfo) => {
  await page.locator('#na').click();
  await assertOrCreateScreenshot(page, testInfo, 'alpha.png');
});

test('visual baseline: academy', async ({ page }, testInfo) => {
  await page.locator('#nc').click();
  await assertOrCreateScreenshot(page, testInfo, 'academy.png');
});