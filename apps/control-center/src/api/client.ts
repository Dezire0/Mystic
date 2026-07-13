import { z } from "zod";
import { providerListSchema, safeErrorSchema, sceneEnvelopeSchema, type Provider } from "./contracts";
import type { SceneDocument } from "../engine/scene-types";

export class ApiError extends Error { constructor(public readonly code: string, message: string, public readonly diagnosticId?: string) { super(message); } }
async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) }, credentials: "same-origin" });
  const body: unknown = await response.json().catch(() => ({}));
  if (!response.ok) { const error = safeErrorSchema.safeParse(body); throw new ApiError(error.success ? error.data.code : "backend_offline", error.success ? error.data.message : "The console could not complete the request.", error.success ? error.data.diagnosticId : undefined); }
  return schema.parse(body);
}
export const api = {
  session: () => request("/api/auth/session", z.object({ authenticated: z.boolean() })),
  login: (token: string, email?: string) => request("/api/auth/login", z.object({ authenticated: z.literal(true) }), { method: "POST", body: JSON.stringify({ token, email }) }),
  logout: () => request("/api/auth/logout", z.object({ authenticated: z.literal(false) }), { method: "POST", body: "{}" }),
  health: () => request("/api/health", z.record(z.string(), z.unknown())),
  status: () => request("/api/status", z.record(z.string(), z.unknown())),
  mcp: () => request("/api/mcp", z.object({ health: z.record(z.string(), z.unknown()), status: z.record(z.string(), z.unknown()), tools: z.array(z.object({ name: z.string() })) })),
  providers: () => request("/api/providers", providerListSchema),
  research: () => request("/api/research", z.record(z.string(), z.unknown())),
  scenes: () => request("/api/scenes", z.record(z.string(), z.unknown())),
  activity: () => request("/api/activity", z.record(z.string(), z.unknown())),
  getResearch: (sessionId: string) => request(`/api/research/${encodeURIComponent(sessionId)}`, z.record(z.string(), z.unknown())),
  advanceResearch: (sessionId: string) => request(`/api/research/${encodeURIComponent(sessionId)}/advance`, z.record(z.string(), z.unknown()), { method: "POST", body: "{}" }),
  reportResearch: (sessionId: string) => request(`/api/research/${encodeURIComponent(sessionId)}/report`, z.record(z.string(), z.unknown()), { method: "POST", body: "{}" }),
  verifyProvider: (providerId: string) => request(`/api/providers/${encodeURIComponent(providerId)}/verify`, z.object({ provider: z.custom<Provider>() }), { method: "POST", body: "{}" }),
  getScene: (sceneId: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}`, sceneEnvelopeSchema).then((data) => data.scene),
  createScene: (input: { sessionId: string; title: string; description?: string }) => request("/api/scenes", sceneEnvelopeSchema, { method: "POST", body: JSON.stringify(input) }).then((data) => data.scene),
  addObject: (sceneId: string, object: unknown, revision: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}/objects`, sceneEnvelopeSchema, { method: "POST", headers: { "if-match": revision }, body: JSON.stringify({ object }) }).then((data) => data.scene),
  updateObject: (sceneId: string, objectId: string, patch: unknown, revision: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}/objects/${encodeURIComponent(objectId)}`, sceneEnvelopeSchema, { method: "PATCH", headers: { "if-match": revision }, body: JSON.stringify({ patch }) }).then((data) => data.scene),
  removeObject: (sceneId: string, objectId: string, revision: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}/objects/${encodeURIComponent(objectId)}`, sceneEnvelopeSchema, { method: "DELETE", headers: { "if-match": revision } }).then((data) => data.scene),
  runSimulation: (sceneId: string, adapterId: string, inputs: unknown, revision: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}/simulations`, z.object({ simulation: z.record(z.string(), z.unknown()), scene: z.custom<SceneDocument>() }), { method: "POST", headers: { "if-match": revision }, body: JSON.stringify({ adapterId, inputs }) }),
  attachSimulation: (sceneId: string, simulationId: string, revision: string) => request(`/api/scenes/${encodeURIComponent(sceneId)}/simulations/${encodeURIComponent(simulationId)}/attach`, z.custom<SceneDocument>(), { method: "POST", headers: { "if-match": revision }, body: JSON.stringify({ applyObjectUpdates: true }) }),
};
