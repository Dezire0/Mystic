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
  test("lists live data and rejects a stale scene revision", async ({ page }) => {
    await page.goto(baseURL!);
    await page.getByLabel("Administrator credential").fill(token!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    const created = await page.evaluate(async () => {
      const call = async (path: string, init?: RequestInit) => {
        const response = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) }, credentials: "same-origin" });
        return { status: response.status, body: await response.json() as Record<string, unknown> };
      };
      const sessions = await call("/api/research");
      const createdSession = await call("/api/research", { method: "POST", body: JSON.stringify({ problem: "E2E revision guard", domain: "physics", goal: "Verify conflict handling", mode: "cheap", participants: ["e2e"] }) });
      const sessionId = String(createdSession.body.session_id);
      const createdScene = await call("/api/scenes", { method: "POST", body: JSON.stringify({ sessionId, title: "E2E revision scene" }) });
      return { sessions, createdSession, createdScene };
    });
    expect(created.sessions.status).toBe(200);
    expect(created.createdSession.status).toBe(200);
    expect(created.createdScene.status).toBe(201);
    const sceneId = String((created.createdScene.body.scene as Record<string, unknown>).sceneId);
    const result = await page.evaluate(async ({ sceneId }) => {
      const call = async (path: string, init?: RequestInit) => {
        const response = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) }, credentials: "same-origin" });
        return { status: response.status, body: await response.json() as Record<string, unknown> };
      };
      const scene = await call(`/api/scenes/${encodeURIComponent(sceneId)}`);
      const revision = String((scene.body.scene as Record<string, unknown>).revision);
      const object = { id: `e2e-object-${Date.now()}`, type: "box", label: "E2E box", transform: { position: { x: 0, y: 0, z: 0 }, rotation: { x: 0, y: 0, z: 0 }, scale: { x: 1, y: 1, z: 1 } }, geometry: {}, material: { color: "#45d6a8", metalness: 0, roughness: 0.5, opacity: 1, wireframe: false }, physics: { type: "fixed", mass: 1, restitution: 0, friction: 0.5 }, data: {}, metadata: {}, visible: true };
      const saved = await call(`/api/scenes/${encodeURIComponent(sceneId)}/objects`, { method: "POST", headers: { "if-match": revision }, body: JSON.stringify({ object }) });
      const stale = await call(`/api/scenes/${encodeURIComponent(sceneId)}/objects`, { method: "POST", headers: { "if-match": revision }, body: JSON.stringify({ ...object, id: `${object.id}-stale` }) });
      const scenes = await call("/api/scenes");
      const activity = await call("/api/activity");
      return { saved, stale, scenes, activity };
    }, { sceneId });
    expect(result.saved.status).toBe(200);
    expect(result.stale.status).toBe(409);
    expect(result.stale.body.code).toBe("scene_conflict");
    expect(Array.isArray(result.scenes.body.scenes)).toBe(true);
    expect(Array.isArray(result.activity.body.events)).toBe(true);
  });
});
