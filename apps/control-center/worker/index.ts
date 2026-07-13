import { z } from "zod";

interface Env {
  ASSETS: Fetcher;
  MYSTIC?: Fetcher;
  MYSTIC_API_ORIGIN: string;
  MYSTIC_SERVICE_TOKEN?: string;
  MYSTIC_CONSOLE_SESSION_SECRET: string;
  MYSTIC_CONSOLE_ADMIN_TOKEN: string;
  MYSTIC_CONSOLE_ALLOWED_EMAILS?: string;
  MYSTIC_CONSOLE_SESSION_TTL_SECONDS?: string;
}

const encoder = new TextEncoder();
const safeErrorCodes = new Set(["backend_offline", "unauthorized", "session_expired", "scene_not_found", "object_not_found", "scene_conflict", "invalid_scene_document", "simulation_invalid_parameters", "simulation_engine_required", "simulation_failed", "asset_storage_required", "webgl_unavailable", "renderer_failed", "export_failed"]);
const createSceneInput = z.object({ sessionId: z.string().min(1), title: z.string().min(1).max(160), description: z.string().max(2000).optional() });
const objectInput = z.object({ object: z.object({ id: z.string().min(1), type: z.string().min(1), label: z.string().min(1), transform: z.object({ position: z.object({ x: z.number(), y: z.number(), z: z.number() }), rotation: z.object({ x: z.number(), y: z.number(), z: z.number() }), scale: z.object({ x: z.number(), y: z.number(), z: z.number() }) }), geometry: z.record(z.string(), z.unknown()), material: z.object({ color: z.string(), metalness: z.number(), roughness: z.number(), opacity: z.number(), wireframe: z.boolean(), emissive: z.string().optional() }), physics: z.object({ type: z.enum(["fixed", "dynamic", "kinematic"]), mass: z.number(), restitution: z.number(), friction: z.number() }), data: z.record(z.string(), z.unknown()), metadata: z.record(z.string(), z.unknown()), visible: z.boolean() }) });
const patchInput = z.object({ patch: z.record(z.string(), z.unknown()) });
const simulationInput = z.object({ adapterId: z.enum(["math.sympy", "physics.simple_projectile", "physics.simple_collision"]), inputs: z.record(z.string(), z.unknown()) });

function json(value: unknown, status = 200, headers: HeadersInit = {}) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers } }); }
function diagnosticId() { return crypto.randomUUID().slice(0, 12); }
function error(code: string, message: string, status = 500) { return json({ code: safeErrorCodes.has(code) ? code : "backend_offline", message, diagnosticId: diagnosticId() }, status); }
function cookie(name: string, value: string, maxAge?: number) { return `${name}=${value}; Path=/; HttpOnly; Secure; SameSite=Strict${maxAge ? `; Max-Age=${maxAge}` : "; Max-Age=0"}`; }
function textEqual(left: string, right: string) { const a = encoder.encode(left); const b = encoder.encode(right); if (a.length !== b.length) return false; let diff = 0; for (let i = 0; i < a.length; i += 1) diff |= a[i] ^ b[i]; return diff === 0; }
async function hmac(secret: string, value: string) { const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]); return btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(value))))).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", ""); }
async function signSession(env: Env, email?: string) { const ttl = Math.min(86400, Math.max(300, Number(env.MYSTIC_CONSOLE_SESSION_TTL_SECONDS ?? 28800))); const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + ttl, email: email ?? "" })).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", ""); return { value: `${payload}.${await hmac(env.MYSTIC_CONSOLE_SESSION_SECRET, payload)}`, ttl }; }
async function validSession(request: Request, env: Env) { const raw = request.headers.get("cookie")?.split(";").map((value) => value.trim()).find((value) => value.startsWith("mystic_console_session="))?.slice("mystic_console_session=".length); if (!raw || !env.MYSTIC_CONSOLE_SESSION_SECRET) return false; const [payload, signature] = raw.split("."); if (!payload || !signature || !textEqual(signature, await hmac(env.MYSTIC_CONSOLE_SESSION_SECRET, payload))) return false; try { return Number((JSON.parse(atob(payload.replaceAll("-", "+").replaceAll("_", "/"))) as { exp?: number }).exp) > Date.now() / 1000; } catch { return false; } }
function allowedEmail(env: Env, email: string | undefined) { const allowlist = (env.MYSTIC_CONSOLE_ALLOWED_EMAILS ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean); return allowlist.length === 0 || (email !== undefined && allowlist.includes(email.trim().toLowerCase())); }
function clientSceneObject(object: Record<string, unknown>) { const position = object.position as Record<string, number>; const rotation = object.rotation as Record<string, number>; const scale = object.scale as Record<string, number>; const data = (object.data as Record<string, unknown>) ?? {}; const rawType = String((object.geometry as Record<string, unknown>)?.kind ?? object.type ?? "box"); const type = rawType === "cube" || rawType === "rigid_body" ? "box" : ["box", "sphere", "cylinder", "cone", "plane", "line", "arrow", "point", "label", "light", "camera"].includes(rawType) ? rawType : "box"; return { id: String(object.id), type, label: String(object.label), transform: { position, rotation, scale }, geometry: (object.geometry as Record<string, unknown>) ?? {}, material: { color: "#45d6a8", metalness: 0.08, roughness: 0.58, opacity: 1, wireframe: false, ...((object.material as Record<string, unknown>) ?? {}) }, physics: { type: data.physics_type === "fixed" || data.physics_type === "kinematic" ? data.physics_type : "dynamic", mass: Number(data.mass ?? 1), restitution: Number(data.restitution ?? 0.25), friction: Number(data.friction ?? 0.55) }, data, metadata: (object.metadata as Record<string, unknown>) ?? {}, visible: data.visible !== false }; }
function normalizeScene(payload: unknown) {
  const bundle = payload as { scene?: Record<string, unknown>; objects?: Record<string, unknown>[]; simulations?: Record<string, unknown>[] };
  const scene = bundle.scene ?? {};
  const revision = String(scene.updated_at ?? scene.created_at ?? "unknown");
  return { scene: { sceneId: String(scene.scene_id), sessionId: String(scene.session_id), title: String(scene.title), description: String(scene.description ?? ""), revision, units: (scene.units as Record<string, unknown>) ?? {}, parameters: (scene.parameters as Record<string, unknown>) ?? {}, environment: {}, camera: { projection: "perspective", position: { x: 7, y: 6, z: 7 }, target: { x: 0, y: 0, z: 0 } }, objects: (bundle.objects ?? []).map(clientSceneObject), simulations: (bundle.simulations ?? []).map((item) => ({ simulationId: String(item.simulation_id), adapterId: item.adapter_id, status: String(item.status), inputs: item.inputs ?? {}, outputs: item.outputs ?? {}, evidence: item.evidence ?? {}, attachedObjectIds: item.attached_object_ids ?? [], createdAt: String(item.created_at ?? "") })), metadata: (scene.metadata as Record<string, unknown>) ?? {}, createdAt: String(scene.created_at ?? ""), updatedAt: revision } };
}
function backendObject(object: z.infer<typeof objectInput>["object"]) { return { id: object.id, type: object.type, label: object.label, position: object.transform.position, rotation: object.transform.rotation, scale: object.transform.scale, geometry: { ...object.geometry, kind: object.type }, material: object.material, data: { ...object.data, physics_type: object.physics.type, mass: object.physics.mass, restitution: object.physics.restitution, friction: object.physics.friction, visible: object.visible }, metadata: object.metadata }; }

async function invoke(env: Env, tool: string, arguments_: Record<string, unknown>) {
  const request = new Request(`${env.MYSTIC_API_ORIGIN.replace(/\/$/, "")}/mcp`, { method: "POST", headers: { "content-type": "application/json", "accept": "application/json", ...(env.MYSTIC_SERVICE_TOKEN ? { authorization: `Bearer ${env.MYSTIC_SERVICE_TOKEN}` } : {}) }, body: JSON.stringify({ jsonrpc: "2.0", id: crypto.randomUUID(), method: "tools/call", params: { name: tool, arguments: arguments_ } }) });
  let response: Response;
  try { response = env.MYSTIC ? await env.MYSTIC.fetch(request) : await fetch(request); } catch { throw new ApiFailure("backend_offline", "Mystic backend is unavailable.", 503); }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiFailure(response.status === 401 ? "unauthorized" : "backend_offline", response.status === 401 ? "Mystic authorization is unavailable." : "Mystic backend did not accept the request.", response.status);
  const rpc = payload as { error?: { message?: string }; result?: { structuredContent?: unknown } };
  if (rpc.error) throw new ApiFailure("backend_offline", "Mystic backend returned a safe operation error.", 502);
  return rpc.result?.structuredContent ?? rpc.result ?? {};
}
class ApiFailure extends Error { constructor(public readonly code: string, message: string, public readonly status: number) { super(message); } }
async function sceneWithRevision(env: Env, sceneId: string, request: Request) { const scene = normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId })); const expected = request.headers.get("if-match"); if (expected && expected !== scene.scene.revision) throw new ApiFailure("scene_conflict", "The scene changed remotely. Refresh or resolve the conflict before saving.", 409); return scene; }

async function routeApi(request: Request, env: Env, url: URL) {
  const pathname = url.pathname;
  if (pathname === "/api/auth/session") return json({ authenticated: await validSession(request, env) });
  if (pathname === "/api/auth/login" && request.method === "POST") {
    const body = z.object({ token: z.string().min(1), email: z.string().email().optional() }).safeParse(await request.json().catch(() => ({})));
    if (!body.success || !env.MYSTIC_CONSOLE_ADMIN_TOKEN || !textEqual(body.data.token, env.MYSTIC_CONSOLE_ADMIN_TOKEN) || !allowedEmail(env, body.data.email)) return error("unauthorized", "Login was not accepted.", 401);
    const session = await signSession(env, body.data.email); return json({ authenticated: true }, 200, { "set-cookie": cookie("mystic_console_session", session.value, session.ttl) });
  }
  if (pathname === "/api/auth/logout" && request.method === "POST") return json({ authenticated: false }, 200, { "set-cookie": cookie("mystic_console_session", "", 0) });
  if (!(await validSession(request, env))) return error("session_expired", "Sign in is required to use the Mystic Control Center.", 401);
  try {
    if (pathname === "/api/health" && request.method === "GET") return json(await invoke(env, "health_check", {}));
    if (pathname === "/api/status" && request.method === "GET") return json(await invoke(env, "mystic_status", {}));
    if (pathname === "/api/mcp" && request.method === "GET") { const [health, status] = await Promise.all([invoke(env, "health_check", {}), invoke(env, "mystic_status", {})]); return json({ health, status, tools: Object.entries(((status as { tools?: Record<string, unknown> }).tools ?? {})).map(([name, state]) => ({ name, state })) }); }
    if (pathname === "/api/providers" && request.method === "GET") return json(await invoke(env, "provider_list", {}));
    const providerMatch = pathname.match(/^\/api\/providers\/([^/]+)\/verify$/);
    if (providerMatch && request.method === "POST") return json({ provider: await invoke(env, "provider_verify", { provider_id: decodeURIComponent(providerMatch[1]) }) });
    if (pathname === "/api/research" && request.method === "POST") { const body = z.object({ problem: z.string().min(1), domain: z.string().min(1), goal: z.string().min(1), mode: z.string().min(1).default("cheap"), participants: z.array(z.string()).min(1) }).parse(await request.json()); return json(await invoke(env, "lab_session_create", body)); }
    const sessionMatch = pathname.match(/^\/api\/research\/([^/]+)(?:\/(advance|report))?$/);
    if (sessionMatch) { const sessionId = decodeURIComponent(sessionMatch[1]); if (!sessionMatch[2] && request.method === "GET") return json(await invoke(env, "lab_session_get", { session_id: sessionId })); if (sessionMatch[2] === "advance" && request.method === "POST") return json(await invoke(env, "lab_session_advance", { session_id: sessionId, max_steps: 1 })); if (sessionMatch[2] === "report" && request.method === "POST") return json(await invoke(env, "lab_report_generate", { session_id: sessionId, format: "markdown", include_failures: true, include_next_actions: true })); }
    if (pathname === "/api/scenes" && request.method === "POST") { const body = createSceneInput.parse(await request.json()); const created = await invoke(env, "create_lab_scene", { session_id: body.sessionId, title: body.title, description: body.description ?? "" }); return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: (created as { scene_id: string }).scene_id })), 201); }
    const sceneMatch = pathname.match(/^\/api\/scenes\/([^/]+)(?:\/objects(?:\/([^/]+))?|\/simulations(?:\/([^/]+)\/attach)?)?$/);
    if (sceneMatch) { const sceneId = decodeURIComponent(sceneMatch[1]); const objectId = sceneMatch[2] ? decodeURIComponent(sceneMatch[2]) : undefined; const simulationId = sceneMatch[3] ? decodeURIComponent(sceneMatch[3]) : undefined;
      if (!sceneMatch[2] && !sceneMatch[3] && request.method === "GET") return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId })));
      if (pathname.endsWith("/objects") && request.method === "POST") { await sceneWithRevision(env, sceneId, request); const body = objectInput.parse(await request.json()); await invoke(env, "add_lab_object", { scene_id: sceneId, object: backendObject(body.object) }); return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId }))); }
      if (objectId && request.method === "PATCH") { await sceneWithRevision(env, sceneId, request); const body = patchInput.parse(await request.json()); await invoke(env, "update_lab_object", { scene_id: sceneId, object_id: objectId, patch: body.patch }); return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId }))); }
      if (objectId && request.method === "DELETE") { await sceneWithRevision(env, sceneId, request); await invoke(env, "remove_lab_object", { scene_id: sceneId, object_id: objectId }); return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId }))); }
      if (pathname.endsWith("/simulations") && request.method === "POST") { const body = simulationInput.parse(await request.json()); const result = await invoke(env, "run_lab_simulation", { scene_id: sceneId, adapter_id: body.adapterId, inputs: body.inputs }); return json({ simulation: result }); }
      if (simulationId && request.method === "POST") { await invoke(env, "attach_simulation_to_scene", { scene_id: sceneId, simulation_id: simulationId, apply_object_updates: true }); return json(normalizeScene(await invoke(env, "get_lab_scene", { scene_id: sceneId }))); }
    }
    return error("scene_not_found", "The requested console operation is not available.", 404);
  } catch (caught) { if (caught instanceof ApiFailure) return error(caught.code, caught.message, caught.status); if (caught instanceof z.ZodError) return error("invalid_scene_document", "The submitted data is not valid for this operation.", 400); return error("backend_offline", "The console could not complete the request.", 502); }
}

export default { async fetch(request: Request, env: Env) { const url = new URL(request.url); if (url.pathname.startsWith("/api/")) return routeApi(request, env, url); return env.ASSETS.fetch(request); } } satisfies ExportedHandler<Env>;
