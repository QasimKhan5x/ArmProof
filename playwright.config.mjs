import { defineConfig } from '@playwright/test';

const testPort = Number(process.env.SURGEDESK_TEST_PORT || 20000 + Math.floor(Math.random() * 20000));
process.env.SURGEDESK_TEST_PORT = String(testPort);

export default defineConfig({
  workers: 1,
  reporter: 'line',
  webServer: {
    command: `SURGEDESK_TEST_PORT=${testPort} PYTHONPATH=src:. python3.12 tests/fixtures/surgedesk_live_gateway.py`,
    url: `http://127.0.0.1:${testPort}/surgedesk/`,
    reuseExistingServer: false,
  },
  use: {
    browserName: 'chromium',
    headless: true,
  },
});
