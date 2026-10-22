import { defineConfig } from "@playwright/test";
import base from "./playwright.config";
export default defineConfig({
  ...base,
  testDir: "e2e-real",
  webServer: {
    ...base.webServer,
    command: "npm run start",
    reuseExistingServer: false,
  },
});
