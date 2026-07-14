import { expect, test } from "@playwright/test";

const baseURL = process.env.MYSTIC_CONSOLE_E2E_URL;
const token = process.env.MYSTIC_CONSOLE_E2E_ADMIN_TOKEN;
const enabled = process.env.MYSTIC_RUN_3D_PERF_BENCHMARK === "1";

test.describe("Mystic 3D renderer @performance", () => {
  test.skip(!enabled || !baseURL || !token, "requires an explicit production-safe target, credential, and MYSTIC_RUN_3D_PERF_BENCHMARK=1");
  test("measures a deterministic 100-primitive scene and selection", async ({ page }, testInfo) => {
    test.setTimeout(45_000);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(baseURL!);
    await page.getByLabel("Administrator credential").fill(token!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    await page.goto(`${baseURL}/lab/benchmark`);
    await expect(page.getByTestId("benchmark-page")).toBeVisible();
    await expect(page.getByTestId("benchmark-metrics")).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Select benchmark object" }).click();
    await expect.poll(async () => JSON.parse(await page.getByTestId("benchmark-metrics").textContent() || "{}").selectionLatencyMs).toBeGreaterThanOrEqual(0);
    await page.getByRole("button", { name: "Hide result layers" }).click();
    await expect.poll(async () => JSON.parse(await page.getByTestId("benchmark-metrics").textContent() || "{}").layerToggleLatencyMs).toBeGreaterThanOrEqual(0);
    const metrics = JSON.parse(await page.getByTestId("benchmark-metrics").textContent() || "{}") as { objectCount: number; resultLayerCount: number; resultPointCount: number; frameCount: number; p50FrameMs: number; p95FrameMs: number; approximateFps: number; selectionLatencyMs: number; layerToggleLatencyMs: number };
    expect(metrics.objectCount).toBe(100);
    expect(metrics.resultLayerCount).toBe(5);
    expect(metrics.resultPointCount).toBe(359);
    expect(metrics.frameCount).toBeGreaterThan(100);
    expect(metrics.p50FrameMs).toBeGreaterThan(0);
    expect(metrics.p95FrameMs).toBeGreaterThanOrEqual(metrics.p50FrameMs);
    expect(metrics.approximateFps).toBeGreaterThan(0);
    expect(metrics.layerToggleLatencyMs).toBeGreaterThanOrEqual(0);
    await testInfo.attach("benchmark-metrics.json", { body: JSON.stringify(metrics, null, 2), contentType: "application/json" });
    expect(errors).toEqual([]);
  });

  test("repeated benchmark navigation does not retain duplicate canvases", async ({ page }) => {
    test.setTimeout(30_000);
    await page.goto(baseURL!);
    await page.getByLabel("Administrator credential").fill(token!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    for (let index = 0; index < 3; index += 1) {
      await page.goto(`${baseURL}/lab/benchmark`);
      await expect(page.locator("canvas")).toHaveCount(1);
      await page.goto(`${baseURL}/settings`);
      await expect(page.getByRole("heading", { name: "Console settings" })).toBeVisible();
    }
  });
});
