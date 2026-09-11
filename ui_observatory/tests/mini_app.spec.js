const { test, expect } = require('@playwright/test');
const { checkA11y, injectAxe } = require('@axe-core/playwright');

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

test.beforeEach(async ({ page }) => {
  await mockBackend(page);
  await page.goto('/');
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
  await injectAxe(page);
  const results = await checkA11y(page, undefined, {
    includedImpacts: ['serious', 'critical'],
    detailedReport: true,
    detailedReportOptions: { html: true },
  });
  expect(results.violations).toEqual([]);
});

test('visual baseline: home', async ({ page }) => {
  await page.getByRole('button', { name: '🏠 בית' }).click();
  await expect(page).toHaveScreenshot('home.png', { fullPage: true });
});

test('visual baseline: wallet', async ({ page }) => {
  await page.getByRole('button', { name: '👛 ארנק' }).click();
  await expect(page).toHaveScreenshot('wallet.png', { fullPage: true });
});

test('visual baseline: transfer', async ({ page }) => {
  await page.getByRole('button', { name: '💸 העברה' }).click();
  await expect(page).toHaveScreenshot('transfer.png', { fullPage: true });
});

test('visual baseline: buy', async ({ page }) => {
  await page.getByRole('button', { name: '💳 קנייה' }).click();
  await expect(page).toHaveScreenshot('buy.png', { fullPage: true });
});

test('visual baseline: staking', async ({ page }) => {
  await page.getByRole('button', { name: '🔒 סטייקינג' }).click();
  await expect(page).toHaveScreenshot('stake.png', { fullPage: true });
});

test('visual baseline: alpha', async ({ page }) => {
  await page.getByRole('button', { name: '🚀 Alpha' }).click();
  await expect(page).toHaveScreenshot('alpha.png', { fullPage: true });
});

test('visual baseline: academy', async ({ page }) => {
  await page.getByRole('button', { name: '🎓 Academy' }).click();
  await expect(page).toHaveScreenshot('academy.png', { fullPage: true });
});
