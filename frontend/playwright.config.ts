import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined },
  },
  webServer: {
    command: process.env.CI ? "npm run start" : "npm run dev",
    timeout: 120_000,
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
  workers: 1,
});
