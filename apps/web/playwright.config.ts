import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 2,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'npm run dev -- --port 4173',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
      env: { BROWSER_API_ORIGIN: 'http://127.0.0.1:18005' },
    },
    ...(process.env.TEST_DATABASE_URL
      ? [
          {
            command: 'cd ../api && uv run --locked python tests/browser_server.py',
            url: 'http://127.0.0.1:18005/api/ready',
            reuseExistingServer: false,
            env: { PYTHONPATH: '.' },
          },
        ]
      : []),
  ],
});
