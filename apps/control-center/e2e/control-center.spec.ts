import { test, expect } from "@playwright/test";

const baseURL = process.env.MYSTIC_CONSOLE_E2E_URL;
const token = process.env.MYSTIC_CONSOLE_E2E_ADMIN_TOKEN;
test.describe("Mystic Control Center live workflow", () => {
  test.skip(!baseURL || !token, "requires an explicitly configured production-safe console target and admin credential");
  test("authenticates and loads live diagnostics without exposing credentials", async ({ page }) => {
    await page.goto(baseURL!);
    await page.getByLabel("Administrator credential").fill(token!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    await page.getByRole("link", { name: "MCP diagnostics" }).click();
    await expect(page.getByRole("heading", { name: "MCP diagnostics" })).toBeVisible();
    const html = await page.content();
    expect(html).not.toContain(token!);
  });
});
