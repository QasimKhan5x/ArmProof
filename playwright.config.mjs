import { defineConfig } from '@playwright/test';

export default defineConfig({
  workers: 1,
  reporter: 'line',
  webServer: {
    command: 'python3.12 -m http.server 8765 --bind 127.0.0.1',
    url: 'http://127.0.0.1:8765/surgedesk/',
    reuseExistingServer: true,
  },
  use: {
    browserName: 'chromium',
    headless: true,
  },
});
