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
  ['bscswap', '🔄 Swap'],
];

async function mockTelegramWebApp(page) {
  await page.route('https://telegram.org/js/telegram-web-app.js', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: `window.Telegram={WebApp:{
        initData:'ui-test-init-data',
        initDataUnsafe:{user:{id:999999999}},
        platform:'test',
        version:'8.0',
        ready:function(){},
        expand:function(){},
        close:function(){},
        openTelegramLink:function(){},
        openInvoice:function(){},
        showPopup:function(){},
        BackButton:{show:function(){},hide:function(){},onClick:function(){}},
        HapticFeedback:{notificationOccurred:function(){}}
      }};`,
    });
  });
}

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
    } else if (url.pathname === '/api/v1/execution/policy') {
      body = { enabled: false, network: 'bsc-testnet', chain_id: 97, router: '0x9Ac64Cc6e4415144C455BD8E4837Fea55603e5c3', wbnb: '0xae13d989daC2f0dEbFf460aC112a837C89BAa7cd', usdt_configured: true, broadcast: false, custody: false };
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

async function clickPrimaryNav(page, label) {
  const desktopButton = page.locator('.nav').getByRole('button', { name: label, exact: true });
  if (await desktopButton.isVisible().catch(() => false)) {
    await desktopButton.click();
    return;
  }
  const screenByLabel = Object.fromEntries(screens.map(([id, text]) => [text, id]));
  const id = screenByLabel[label];
  const bottomId = { home: 'bh', wallet: 'bw', transfer: 'bt' }[id];
  if (bottomId) {
    await page.locator('#' + bottomId).click();
    return;
  }
  await page.locator('#bmore').click();
  await page.locator('.more-grid button').filter({ hasText: label }).click();
}

test.beforeEach(async ({ page }) => {
  // The production Mini App must require real Telegram initData.
  // The browser test supplies a deterministic Telegram WebApp stub and mocks API calls.
  await mockTelegramWebApp(page);
  await mockBackend(page);
  await page.goto('/mini-app');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(() => window.Telegram?.WebApp?.initData === 'ui-test-init-data');
  await expect(page.locator('#authGate')).toBeHidden();
  await expect(page.locator('.app')).toBeVisible();
  await expect(page.locator('#slh-splash')).toBeHidden({ timeout: 5000 });
});

test('all primary screens are reachable', async ({ page }) => {
  const seen = [];
  for (const [id, label] of screens) {
    await clickPrimaryNav(page, label);
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

  await clickPrimaryNav(page, '💸 העברה');
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
  await clickPrimaryNav(page, '🏠 בית');
  await assertOrCreateScreenshot(page, testInfo, 'home.png');
});

test('visual baseline: wallet', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '👛 ארנק');
  await assertOrCreateScreenshot(page, testInfo, 'wallet.png');
});

test('visual baseline: transfer', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '💸 העברה');
  await assertOrCreateScreenshot(page, testInfo, 'transfer.png');
});

test('visual baseline: buy', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '💳 קנייה');
  await assertOrCreateScreenshot(page, testInfo, 'buy.png');
});

test('visual baseline: staking', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '🔒 סטייקינג');
  await assertOrCreateScreenshot(page, testInfo, 'stake.png');
});

test('visual baseline: alpha', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '🚀 Alpha');
  await assertOrCreateScreenshot(page, testInfo, 'alpha.png');
});

test('visual baseline: academy', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, '🎓 Academy');
  await assertOrCreateScreenshot(page, testInfo, 'academy.png');
});


test('display theme selection is interactive and persistent', async ({ page }) => {
  await clickPrimaryNav(page, '⚙️ הגדרות').catch(async () => {
    await page.locator('#bmore').click();
    const settingsButton = page.locator('.more-grid button').filter({ hasText: 'הגדרות' });
    if (await settingsButton.count()) await settingsButton.click();
    else await page.locator('[onclick*="show(\\'settings\\')"]').first().click();
  });
  await expect(page.locator('#settings')).toHaveClass(/active/);
  await expect(page.locator('#themeChoices button')).toHaveCount(4);

  const contrast = page.locator('#themeChoices button.contrast');
  await expect(contrast).toBeVisible();
  await contrast.click();

  await expect(page.locator('html')).toHaveAttribute('data-slh-theme', 'contrast');
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'night');
  await expect(page.locator('#settingsThemeMeta')).toContainText('ניגודיות גבוהה');

  const saved = await page.evaluate(() => localStorage.getItem('slh.theme'));
  expect(saved).toBe('contrast');
  await expect(contrast).toHaveAttribute('aria-selected', 'true');
});

test('BSC swap screen is reachable and remains execution-gated', async ({ page }) => {
  await clickPrimaryNav(page, '🔄 Swap');
  await expect(page.locator('#bscswap')).toHaveClass(/active/);
  await expect(page.locator('#bscSwapBadge')).toHaveText('🔒 CLOSED');
  await expect(page.locator('#bscSwapQuoteButton')).toBeDisabled();
  await expect(page.locator('#bscSwapPrepareButton')).toBeDisabled();
  await expect(page.locator('#bscSwapSendButton')).toBeDisabled();
  await expect(page.locator('#bscSwapGateText')).toHaveText('Execution סגור · אין חתימה או שידור');
});
