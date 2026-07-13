import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir: "./e2e", timeout: 30_000, use: { baseURL: process.env.MYSTIC_CONSOLE_E2E_URL, trace: "retain-on-failure" } });
