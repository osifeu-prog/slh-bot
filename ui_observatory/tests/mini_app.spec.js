const fs = require('fs');
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const screens = [
  ['home', '🏠 בית'],
  ['wallet', '👛 ארנק'],
  ['transfer', '💸 העברה'],
  ['buy', '💳 קנייה'],
  ['stake', '🔒 סטייקינג'],
  ['alpha', '🚀 Alpha'],
  ['academy', '🎓 Academy'],
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

test.beforeEach(async ({ page }) => {
  await mockBackend(page);
  await page.goto('/mini-app');
  await page.waitForLoadState('domcontentloaded');
});

test('all primary screens are reachable', async ({ page }) => {
  const seen = [];
  for (const [id, label] of screens) {
    await page.getByRole('button', { name: label }).click();
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

  await page.getByRole('button', { name: '💸 העברה' }).click();
  await expect(page.locator('#recipient')).toHaveAttribute('id', 'recipient');
  await expect(page.locator('label[for="recipient"]')).toBeVisible();
  await expect(page.locator('label[for="amount"]')).toBeVisible();
});

test('accessibility audit has no serious or critical violations', async ({ page }) => {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter(v => ['serious', 'critical'].includes(v.impact));
  expect(blocking).toEqual([]);
});

test('visual baseline: home', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '🏠 בית' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'home.png');
});

test('visual baseline: wallet', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '👛 ארנק' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'wallet.png');
});

test('visual baseline: transfer', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '💸 העברה' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'transfer.png');
});

test('visual baseline: buy', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '💳 קנייה' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'buy.png');
});

test('visual baseline: staking', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '🔒 סטייקינג' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'stake.png');
});

test('visual baseline: alpha', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '🚀 Alpha' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'alpha.png');
});

test('visual baseline: academy', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: '🎓 Academy' }).click();
  await assertOrCreateScreenshot(page, testInfo, 'academy.png');
});
