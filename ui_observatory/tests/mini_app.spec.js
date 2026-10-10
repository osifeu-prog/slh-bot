const fs = require('fs');
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const screens = [
  ['home', 'בית', 'bh'],
  ['balance', 'Balance', 'bb'],
  ['move', 'Move', 'bm'],
  ['growth', 'Grow', 'bg'],
  ['investor', 'Investor', 'binv'],
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
    if (url.pathname === '/api/v1/exchange/order' && route.request().method() === 'POST') {
      body = {
        order_id: 'O000000042',
        filled: '2.00000000',
        remaining: '0.00000000',
        status: 'filled',
        trade_ids: ['T000000043'],
        execution_check: {
          status: 'PASS',
          checked_at: '2026-10-09T09:00:00Z',
          public_gate: 'OPEN',
          verdict: 'OPEN',
          execution_ready: true,
          public_ready: true,
          order_book_integrity: true,
          trade_integrity: true,
          money_invariants: true,
          open_orders_before: 1
        }
      };
    } else if (url.pathname === '/api/v1/me') {
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
  const entry = screens.find(([, text]) => text === label);
  if (!entry) throw new Error('Unknown primary navigation label: ' + label);
  await page.locator('#' + entry[2]).click();
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
  // Wait for asynchronous boot/loadMe work to settle before user-driven navigation;
  // otherwise its initial-screen render can race a click and reset the active screen.
  await page.waitForLoadState('networkidle');
  await expect(page.locator('#home')).toHaveClass(/active/);
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

test('market clearly distinguishes store grants, Credits, internal SLH and on-chain SLH', async ({ page }) => {
  await page.evaluate(() => show('market'));
  const guide = page.locator('#marketAssetGuide');
  await expect(guide).toContainText('קורסים מעניקים גישה');
  await expect(guide).toContainText('Credits הם יתרה פנימית');
  await expect(guide).toContainText('רכישה בחנות אינה מקנה זכות הצבעה אוטומטית');
  await expect(guide.getByRole('button', { name: /הצעות והצבעות/ })).toBeVisible();
});

test('governance explains role-based vote weight before the user votes', async ({ page }) => {
  await page.evaluate(() => show('governance'));
  const notice = page.locator('#governanceRulesNotice');
  await expect(notice).toContainText('משקל ההצבעה נגזר מתפקיד החשבון');
  await expect(notice).toContainText('לא מיתרת SLH');
});

test('visible Governance entry records a vote and shows the canonical receipt', async ({ page }) => {
  let voteRecorded = false;
  let submittedVote = null;
  const proposal = {
    id: 7,
    title: 'Canonical UI test proposal',
    description: 'Exercise the visible Governance path with mocked canonical responses.',
    status: 'open',
    votes: { yes: voteRecorded ? 1 : 0, no: 0, abstain: 0, weighted_yes: voteRecorded ? 1 : 0, weighted_no: 0 },
    my_vote: null,
  };

  await page.route('**/api/v1/governance', async route => {
    const currentProposal = {
      ...proposal,
      votes: { ...proposal.votes, yes: voteRecorded ? 1 : 0, weighted_yes: voteRecorded ? 1 : 0 },
      my_vote: voteRecorded
        ? { choice: 'yes', weight: 1, timestamp: '2026-10-10T08:00:00Z' }
        : null,
    };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        agents: 2,
        proposal_count: 1,
        open_proposals: 1,
        source_of_truth: 'state/db.json',
        proposals: [currentProposal],
      }),
    });
  });

  await page.route('**/api/v1/governance/vote', async route => {
    submittedVote = route.request().postDataJSON();
    voteRecorded = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'recorded',
        proposal_id: 7,
        choice: submittedVote.choice,
        weight: 1,
        points_awarded: 5,
        timestamp: '2026-10-10T08:00:00Z',
      }),
    });
  });

  // Begin on Home and use the visible user flow: Buy tile → Governance button → Vote.
  const buyTile = page.locator('.ux-tile.actionable').filter({ hasText: 'Buy' });
  await expect(buyTile).toBeVisible();
  await buyTile.click();
  await expect(page.locator('#market')).toHaveClass(/active/);

  const governanceEntry = page.locator('#marketAssetGuide').getByRole('button', { name: /הצעות והצבעות/ });
  await expect(governanceEntry).toBeVisible();
  await governanceEntry.click();
  await expect(page.locator('#governance')).toHaveClass(/active/);
  await expect(page.locator('#governanceBody')).toContainText('Canonical UI test proposal');

  const voteRequestPromise = page.waitForRequest(request =>
    request.url().endsWith('/api/v1/governance/vote') && request.method() === 'POST'
  );
  await page.locator('#governanceBody').getByRole('button', { name: /בעד/ }).click();
  const voteRequest = await voteRequestPromise;

  expect(submittedVote).toEqual({ proposal_id: 7, choice: 'yes' });
  expect(voteRequest.postDataJSON()).toEqual({ proposal_id: 7, choice: 'yes' });
  await expect(page.locator('#governance')).toHaveClass(/active/);
  await expect(page.locator('#governanceBody')).toContainText('ההצבעה שלך נרשמה');
  await expect(page.locator('#governanceBody')).toContainText('yes · משקל 1');
});

test('exchange receipt shows every fresh canonical gate item', async ({ page }) => {
  // Exercise the Mini App's real send handler directly; screen-navigation
  // coverage is tested separately and this test focuses on receipt semantics.
  await page.evaluate(async () => {
    document.querySelectorAll('.screen').forEach(screen => screen.classList.remove('active'));
    document.querySelector('#exchange').classList.add('active');
    await sendExchangeOrder('buy', '2', '1');
  });
  const receipt = page.locator('#exchange [data-exchange-receipt="true"]');
  await expect(receipt).toContainText('Fresh Exchange check: PASS');
  await expect(receipt).toContainText('שער ציבורי');
  await expect(receipt).toContainText('ספר פקודות');
  await expect(receipt).toContainText('תקינות עסקאות');
  await expect(receipt).toContainText('אינווריאנטים כספיים');
});

test('visible Buy button submits directly through the fresh Exchange endpoint', async ({ page }) => {
  await page.evaluate(() => show('move'));
  const exchangeButton = page.locator('#move').getByRole('button', { name: /Exchange/ });
  await expect(exchangeButton).toBeVisible();
  await exchangeButton.click();
  await expect(page.locator('#exchange')).toHaveClass(/active/);

  await page.locator('#buyAmount').fill('2');
  await page.locator('#buyPrice').fill('1');
  const requestPromise = page.waitForRequest(request =>
    request.url().endsWith('/api/v1/exchange/order') && request.method() === 'POST'
  );
  await page.locator('#exchange').getByRole('button', { name: /קנה SLH/ }).click();
  const request = await requestPromise;
  const payload = request.postDataJSON();

  expect(payload.side).toBe('buy');
  expect(payload.amount).toBe('2');
  expect(payload.price).toBe('1');
  expect(payload.client_request_id).toBeTruthy();
  await expect(page.locator('#exchange [data-exchange-receipt="true"]'))
    .toContainText('Fresh Exchange check: PASS');
  expect(page.url()).toContain('/mini-app');
});

test('visible Sell button submits directly through the fresh Exchange endpoint', async ({ page }) => {
  await page.evaluate(() => show('move'));
  const exchangeButton = page.locator('#move').getByRole('button', { name: /Exchange/ });
  await expect(exchangeButton).toBeVisible();
  await exchangeButton.click();
  await expect(page.locator('#exchange')).toHaveClass(/active/);

  await page.locator('#sellAmount').fill('2');
  await page.locator('#sellPrice').fill('1');
  const requestPromise = page.waitForRequest(request =>
    request.url().endsWith('/api/v1/exchange/order') && request.method() === 'POST'
  );
  await page.locator('#exchange').getByRole('button', { name: /מכור SLH/ }).click();
  const request = await requestPromise;
  const payload = request.postDataJSON();

  expect(payload.side).toBe('sell');
  expect(payload.amount).toBe('2');
  expect(payload.price).toBe('1');
  expect(payload.client_request_id).toBeTruthy();
  await expect(page.locator('#exchange [data-exchange-receipt="true"]'))
    .toContainText('Fresh Exchange check: PASS');
  expect(page.url()).toContain('/mini-app');
});

test('partial Exchange receipt never shows a green fresh-check status', async ({ page }) => {
  await page.route('**/api/v1/exchange/order', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        order_id: 'O000000099',
        filled: '0.00000000',
        remaining: '2.00000000',
        status: 'open',
        trade_ids: [],
        execution_check: {
          status: 'PASS',
          public_gate: 'OPEN',
          verdict: 'OPEN',
          public_ready: true,
          order_book_integrity: true,
          trade_integrity: true,
          money_invariants: true
        }
      })
    });
  });
  await page.evaluate(async () => {
    document.querySelectorAll('.screen').forEach(screen => screen.classList.remove('active'));
    document.querySelector('#exchange').classList.add('active');
    await sendExchangeOrder('buy', '2', '1');
  });
  const receipt = page.locator('#exchange [data-exchange-receipt="true"]');
  await expect(receipt).toContainText('Fresh Exchange receipt incomplete');
  await expect(receipt).not.toContainText('✅ Fresh Exchange check: PASS');
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

  await clickPrimaryNav(page, 'Move');
  await page.locator('#move').getByRole('button', { name: /Send Credits/i }).click();
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
  await clickPrimaryNav(page, 'בית');
  await assertOrCreateScreenshot(page, testInfo, 'home.png');
});

test('visual baseline: wallet', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, 'Balance');
  await page.locator('#balance').getByRole('button', { name: /Advanced Wallet/i }).click();
  await assertOrCreateScreenshot(page, testInfo, 'wallet.png');
});

test('visual baseline: transfer', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, 'Move');
  await page.locator('#move').getByRole('button', { name: /Send Credits/i }).click();
  await assertOrCreateScreenshot(page, testInfo, 'transfer.png');
});

test('visual baseline: buy', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, 'Move');
  await page.locator('#move').getByRole('button', { name: /Add Funds · Credits/i }).click();
  await assertOrCreateScreenshot(page, testInfo, 'buy.png');
});

test('visual baseline: staking', async ({ page }, testInfo) => {
  await page.evaluate(() => show('stake'));
  await assertOrCreateScreenshot(page, testInfo, 'stake.png');
});

test('visual baseline: alpha', async ({ page }, testInfo) => {
  await page.evaluate(() => show('alpha'));
  await assertOrCreateScreenshot(page, testInfo, 'alpha.png');
});

test('visual baseline: academy', async ({ page }, testInfo) => {
  await clickPrimaryNav(page, 'Grow');
  await page.getByRole('button', { name: /🎓 Earn/i }).click();
  await assertOrCreateScreenshot(page, testInfo, 'academy.png');
});


test('advanced BSC swap screen remains execution-gated', async ({ page }) => {
  await page.evaluate(() => show('bscswap'));
  await expect(page.locator('#bscswap')).toHaveClass(/active/);
  await expect(page.locator('#bscSwapBadge')).toHaveText('🔒 CLOSED');
  await expect(page.locator('#bscSwapQuoteButton')).toBeDisabled();
  await expect(page.locator('#bscSwapPrepareButton')).toBeDisabled();
  await expect(page.locator('#bscSwapSendButton')).toBeDisabled();
  await expect(page.locator('#bscSwapGateText')).toHaveText('Execution סגור · אין חתימה או שידור');
});
