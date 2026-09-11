const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  reporter: [['list'], ['json', { outputFile: 'artifacts/ui-results.json' }]],
  use: {
    baseURL: process.env.SLH_UI_BASE_URL || 'http://127.0.0.1:8080/mini-app',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ...devices['iPhone 13'],
    locale: 'he-IL',
    timezoneId: 'Asia/Jerusalem'
  },
  outputDir: 'artifacts/test-output',
});
