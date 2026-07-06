const CONFIG_URL = "https://gist.githubusercontent.com/Dezire0/778759ccca8f7d9a54c1f98662b6a9ec/raw/mystic-origin.json";
const DEFAULT_SCOPES = "tools:read tools:execute";
const DEFAULT_TOKEN_TTL_SECONDS = 3600;
const MANUAL_IMPORT_VERIFICATION_PATH = "/mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_import_verified.json";
const DEFAULT_SUPABASE_SCHEMA = "public";
const CLOUD_PHASE1_TOOL_DEFINITIONS = [
  {
    name: "mystic_status",
    title: "Mystic Status",
    description: "Return current Mystic cloud-worker and storage availability status.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "health_check",
    title: "Health Check",
    description: "Return a minimal cloud-native Mystic health summary.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "lab_session_create",
    title: "Create Lab Session",
    description: "Create a phase-1 Mystic Lab session in Supabase-backed cloud storage.",
    inputSchema: {
      type: "object",
      properties: {
        problem: { type: "string", minLength: 1 },
        domain: { type: "string", minLength: 1 },
        goal: { type: "string", minLength: 1 },
        mode: { type: "string", minLength: 1 },
        participants: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 8 },
      },
      required: ["problem", "domain", "goal", "mode", "participants"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_session_get",
    title: "Get Lab Session",
    description: "Load the current cloud-native lab session state from Supabase.",
    inputSchema: {
      type: "object",
      properties: { session_id: { type: "string", minLength: 1 } },
      required: ["session_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "lab_report_generate",
    title: "Generate Lab Report",
    description: "Generate a markdown report from Supabase-backed cloud-native lab data.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        format: { type: "string", enum: ["markdown"] },
        include_failures: { type: "boolean" },
        include_next_actions: { type: "boolean" },
      },
      required: ["session_id", "format", "include_failures", "include_next_actions"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
];
const CLOUD_PHASE1_TOOL_NAMES = new Set(CLOUD_PHASE1_TOOL_DEFINITIONS.map((tool) => tool.name));
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

function parseBoolean(value) {
  return String(value || "").trim().toLowerCase() === "true";
}

function normalizeBaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function oauthEnabled(env) {
  return parseBoolean(env.MYSTIC_OAUTH_ENABLED);
}

function oauthSigningSecret(env) {
  return String(
    env.MYSTIC_OAUTH_SIGNING_SECRET || env.MYSTIC_OAUTH_CLIENT_SECRET || env.MYSTIC_OAUTH_DEV_STATIC_TOKEN || "",
  ).trim();
}

function oauthIssuer(env, requestUrl) {
  const issuer = String(env.MYSTIC_OAUTH_ISSUER || "").trim();
  if (issuer) {
    return normalizeBaseUrl(issuer);
  }
  return new URL(requestUrl).origin;
}

function accessTokenTtlSeconds(env) {
  const raw = Number.parseInt(String(env.MYSTIC_OAUTH_ACCESS_TOKEN_TTL_SECONDS || ""), 10);
  if (Number.isFinite(raw) && raw > 0) {
    return raw;
  }
  return DEFAULT_TOKEN_TTL_SECONDS;
}

function allowedRedirectUris(env) {
  return String(env.MYSTIC_OAUTH_ALLOWED_REDIRECT_URIS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function oauthState(env, requestUrl) {
  const issuer = oauthIssuer(env, requestUrl);
  const enabled = oauthEnabled(env);
  const signingSecret = oauthSigningSecret(env);
  const dynamicClientRegistrationEnabled = parseBoolean(env.MYSTIC_OAUTH_DYNAMIC_CLIENT_REGISTRATION_ENABLED);
  const state = {
    enabled,
    issuer,
    resource: `${issuer}/mcp`,
    resourceMetadataUrl: `${issuer}/.well-known/oauth-protected-resource`,
    resourceMetadataPathUrl: `${issuer}/.well-known/oauth-protected-resource/mcp`,
    authorizationEndpoint: `${issuer}/oauth/authorize`,
    tokenEndpoint: `${issuer}/oauth/token`,
    registrationEndpoint: dynamicClientRegistrationEnabled ? `${issuer}/oauth/register` : "",
    jwksUri: parseBoolean(env.MYSTIC_OAUTH_EXPOSE_JWKS) ? `${issuer}/oauth/jwks` : "",
    allowedRedirectUris: allowedRedirectUris(env),
    tokenTtlSeconds: accessTokenTtlSeconds(env),
    devStaticToken: String(env.MYSTIC_OAUTH_DEV_STATIC_TOKEN || "").trim(),
    devStaticTokenConfigured: Boolean(String(env.MYSTIC_OAUTH_DEV_STATIC_TOKEN || "").trim()),
    configured: enabled && Boolean(signingSecret),
    metadataAvailable: enabled && Boolean(signingSecret),
    signingSecret,
    dynamicClientRegistrationEnabled,
  };
  return state;
}

function secretPreview(secret) {
  return secret ? "[configured]" : "[missing]";
}

async function loadOrigin(env) {
  if (String(env.MYSTIC_BACKEND_URL || "").trim()) {
    return String(env.MYSTIC_BACKEND_URL).trim();
  }
  const configUrl = new URL(CONFIG_URL);
  configUrl.searchParams.set("v", String(Math.floor(Date.now() / 10000)));
  const response = await fetch(configUrl, {
    cf: {
      cacheEverything: true,
      cacheTtl: 5,
    },
  });
  if (!response.ok) {
    throw new Error(`config fetch failed: ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.origin) {
    throw new Error("origin missing");
  }
  return payload.origin;
}

function jsonResponse(payload, status = 200, headers = {}) {
  const responseHeaders = new Headers(headers);
  responseHeaders.set("content-type", "application/json; charset=utf-8");
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: responseHeaders,
  });
}

function htmlResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function errorResponse(message, status = 400, headers = {}) {
  return jsonResponse({ error: message }, status, headers);
}

function storageBackend(env) {
  return String(env.MYSTIC_STORAGE_BACKEND || "").trim().toLowerCase() || "local";
}

function cloudPhase1Enabled(env) {
  return storageBackend(env) === "supabase";
}

function supabaseState(env) {
  const url = normalizeBaseUrl(env.MYSTIC_SUPABASE_URL || "");
  const serviceRoleKey = String(env.MYSTIC_SUPABASE_SERVICE_ROLE_KEY || "").trim();
  const schema = String(env.MYSTIC_SUPABASE_SCHEMA || DEFAULT_SUPABASE_SCHEMA).trim() || DEFAULT_SUPABASE_SCHEMA;
  return {
    url,
    serviceRoleKey,
    schema,
    configured: Boolean(url && serviceRoleKey),
    storageRoot: `supabase://${schema}/lab_sessions`,
  };
}

function cloudArtifactPaths(schema, sessionId) {
  return {
    session: `supabase://${schema}/lab_sessions/${sessionId}`,
    turns: `supabase://${schema}/lab_turns?session_id=${sessionId}`,
    claims: `supabase://${schema}/claims?session_id=${sessionId}`,
    experiments: `supabase://${schema}/lab_sessions/${sessionId}#experiments`,
    failures: `supabase://${schema}/failures?session_id=${sessionId}`,
    memory_edges: `supabase://${schema}/memory_edges?session_id=${sessionId}`,
    notebook: `supabase://${schema}/lab_sessions/${sessionId}#notebook`,
    report: `supabase://${schema}/reports/${sessionId}`,
  };
}

function phase1Blockers(state, supabase) {
  const blockers = [];
  if (!state.enabled) {
    blockers.push("OAUTH_NOT_CONFIGURED");
  } else if (!state.configured) {
    blockers.push("OAUTH_METADATA_MISSING");
  }
  if (!supabase.configured) {
    blockers.push("LAB_STORAGE_NOT_CONFIGURED");
  }
  blockers.push("MANUAL_IMPORT_NOT_VERIFIED");
  return blockers;
}

function phase1MysticStatus(state, supabase) {
  return {
    models: {},
    tools: {
      mystic_status: "ready",
      health_check: "ready",
      lab_session_create: supabase.configured ? "ready" : "blocked",
      lab_session_get: supabase.configured ? "ready" : "blocked",
      lab_report_generate: supabase.configured ? "ready" : "blocked",
    },
    lab_core_available: true,
    lab_tools_count: 3,
    phase_1_tools_count: CLOUD_PHASE1_TOOL_DEFINITIONS.length,
    storage_backend: "supabase",
    storage_status: {
      backend: "supabase",
      configured: supabase.configured,
      write_capable: supabase.configured,
      storage_root: supabase.storageRoot,
      storage_root_uri: supabase.storageRoot,
      schema: supabase.schema,
      project_url: supabase.url,
      missing_env: [
        ...(!supabase.url ? ["MYSTIC_SUPABASE_URL"] : []),
        ...(!supabase.serviceRoleKey ? ["MYSTIC_SUPABASE_SERVICE_ROLE_KEY"] : []),
      ],
    },
    lab_storage_root: supabase.storageRoot,
    remote_mcp_public_endpoint: `${state.issuer}/mcp`,
    oauth_configured: state.configured,
    oauth_enabled: state.enabled,
    oauth_metadata_available: state.metadataAvailable,
    chatgpt_remote_import_ready: false,
    chatgpt_remote_import_ready_candidate: state.metadataAvailable && supabase.configured,
    manual_import_verification_checked: false,
    manual_import_verified: false,
    manual_import_verification_path: MANUAL_IMPORT_VERIFICATION_PATH,
    manual_import_verification_summary: {},
    blockers: phase1Blockers(state, supabase),
    datasets: {},
    adapter_status: { available: [] },
    recent_runs: [],
    recent_errors: [],
    mcp_server_status: "ready",
    runtime_mode: "cloud_native_worker_phase_1",
  };
}

function phase1HealthCheck(state, supabase) {
  return {
    status: supabase.configured ? "ok" : "error",
    mode: "cloud_native_worker",
    storage_backend: "supabase",
    storage_status: {
      backend: "supabase",
      configured: supabase.configured,
      write_capable: supabase.configured,
      storage_root: supabase.storageRoot,
      storage_root_uri: supabase.storageRoot,
      schema: supabase.schema,
      project_url: supabase.url,
      missing_env: [
        ...(!supabase.url ? ["MYSTIC_SUPABASE_URL"] : []),
        ...(!supabase.serviceRoleKey ? ["MYSTIC_SUPABASE_SERVICE_ROLE_KEY"] : []),
      ],
    },
    oauth_enabled: state.enabled,
    oauth_configured: state.configured,
    phase_1_tools: CLOUD_PHASE1_TOOL_DEFINITIONS.map((tool) => tool.name),
  };
}

function jsonRpcResponse(requestId, result) {
  return jsonResponse({ jsonrpc: "2.0", id: requestId, result }, 200, { "cache-control": "no-store" });
}

function jsonRpcError(requestId, code, message, data = undefined) {
  const payload = {
    jsonrpc: "2.0",
    id: requestId,
    error: { code, message },
  };
  if (data !== undefined) {
    payload.error.data = data;
  }
  return jsonResponse(payload, 200, { "cache-control": "no-store" });
}

function validateCloudToolArguments(name, args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) {
    return ["arguments must be a JSON object"];
  }
  const errors = [];
  if (name === "lab_session_create") {
    if (typeof args.problem !== "string" || !args.problem.trim()) {
      errors.push("problem is required");
    }
    if (typeof args.domain !== "string" || !args.domain.trim()) {
      errors.push("domain is required");
    }
    if (typeof args.goal !== "string" || !args.goal.trim()) {
      errors.push("goal is required");
    }
    if (typeof args.mode !== "string" || !args.mode.trim()) {
      errors.push("mode is required");
    }
    if (!Array.isArray(args.participants) || args.participants.length < 1) {
      errors.push("participants must contain at least one entry");
    }
  }
  if (name === "lab_session_get" || name === "lab_report_generate") {
    if (typeof args.session_id !== "string" || !args.session_id.trim()) {
      errors.push("session_id is required");
    }
  }
  if (name === "lab_report_generate") {
    if (args.format !== "markdown") {
      errors.push("format must be markdown");
    }
    if (typeof args.include_failures !== "boolean") {
      errors.push("include_failures must be boolean");
    }
    if (typeof args.include_next_actions !== "boolean") {
      errors.push("include_next_actions must be boolean");
    }
  }
  return errors;
}

function makeCloudSessionId() {
  const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  const random = crypto.randomUUID().replace(/-/g, "").slice(0, 8);
  return `lab-${timestamp}-${random}`;
}

function makeCloudController() {
  return {
    model_id: "gpt_controller",
    provider: "controller",
    model_name: "GPT Controller",
    role: "judge",
  };
}

function makeCloudParticipants(participants) {
  return participants.map((item) => ({
    model_id: String(item),
    provider: "cloud_phase1",
    model_name: String(item),
    status: {
      state: "deferred",
      available: false,
      authenticated: false,
      message: "Phase-1 cloud-native mode stores the session without invoking live model providers.",
    },
  }));
}

function buildCloudSessionBundle({ sessionId, problem, domain, goal, mode, participants, schema }) {
  const createdAt = new Date().toISOString();
  const session = {
    session_id: sessionId,
    problem,
    domain,
    goal,
    mode,
    status: "created",
    current_phase: "problem_intake",
    active_room: "Control Panel",
    created_at: createdAt,
    updated_at: createdAt,
    controller: makeCloudController(),
    participants: makeCloudParticipants(participants),
    artifact_paths: cloudArtifactPaths(schema, sessionId),
    next_actions: [
      "Review the created lab session in ChatGPT.",
      "Use lab_report_generate to snapshot the current session state.",
    ],
    warnings: [
      "Phase-1 cloud-native mode stores sessions in Supabase and defers long-running model execution.",
    ],
  };
  return {
    session,
    turns: [],
    claims: [],
    experiments: [],
    failures: [],
    memory_edges: [],
    notebook_markdown: `# Lab Notebook ${sessionId}\n\nProblem: ${problem}\n\n`,
    report_markdown: "",
  };
}

function renderCloudReport(bundle) {
  const survivingClaims = bundle.claims.filter((claim) => ["PROVED", "TESTED", "HEURISTIC"].includes(claim.status));
  const failedClaims = bundle.claims.filter((claim) => ["FAILED", "REFUTED", "NEEDS_MORE_DETAIL"].includes(claim.status));
  const keyLessons = bundle.failures.slice(-5).map((failure) => failure.lesson);
  const survivingLines = survivingClaims.length ? survivingClaims.map((claim) => `- ${claim.text} [${claim.status}]`) : ["- None"];
  const failedLines = failedClaims.length ? failedClaims.map((claim) => `- ${claim.text} [${claim.status}]`) : ["- None"];
  const experimentLines = bundle.experiments.length
    ? bundle.experiments.map((experiment) => `- ${experiment.question} => ${experiment.verdict}`)
    : ["- None"];
  const lessonLines = keyLessons.length ? keyLessons.map((lesson) => `- ${lesson}`) : ["- None"];
  const nextActionLines = bundle.session.next_actions.length
    ? bundle.session.next_actions.map((item) => `- ${item}`)
    : ["- None"];
  const markdown = [
    `# Mystic Lab Report: ${bundle.session.session_id}`,
    "",
    `Problem: ${bundle.session.problem}`,
    `Domain: ${bundle.session.domain}`,
    "",
    "## Surviving Claims",
    ...survivingLines,
    "",
    "## Failed Claims",
    ...failedLines,
    "",
    "## Experiments",
    ...experimentLines,
    "",
    "## Key Lessons",
    ...lessonLines,
    "",
    "## Next Actions",
    ...nextActionLines,
    "",
  ].join("\n");
  return {
    session_id: bundle.session.session_id,
    title: `Mystic Lab Report ${bundle.session.session_id}`,
    problem: bundle.session.problem,
    domain: bundle.session.domain,
    surviving_claims: survivingClaims,
    failed_claims: failedClaims,
    experiments: bundle.experiments,
    key_lessons: keyLessons,
    next_actions: [...bundle.session.next_actions],
    markdown,
  };
}

function parseCloudBundle(sessionRow, turns, claims, failures, memoryEdges, reportRow) {
  const experiments = Array.isArray(sessionRow.experiments_json) ? sessionRow.experiments_json : [];
  return {
    session: {
      session_id: sessionRow.session_id,
      problem: sessionRow.problem,
      domain: sessionRow.domain,
      goal: sessionRow.goal,
      mode: sessionRow.mode,
      status: sessionRow.status,
      current_phase: sessionRow.current_phase,
      active_room: sessionRow.active_room,
      created_at: sessionRow.created_at,
      updated_at: sessionRow.updated_at,
      controller: sessionRow.controller || {},
      participants: Array.isArray(sessionRow.participants) ? sessionRow.participants : [],
      artifact_paths: sessionRow.artifact_paths || cloudArtifactPaths(DEFAULT_SUPABASE_SCHEMA, sessionRow.session_id),
      next_actions: Array.isArray(sessionRow.next_actions) ? sessionRow.next_actions : [],
      warnings: Array.isArray(sessionRow.warnings) ? sessionRow.warnings : [],
    },
    turns,
    claims,
    experiments,
    failures,
    memory_edges: memoryEdges,
    notebook_markdown: String(sessionRow.notebook_markdown || ""),
    report_markdown: String((reportRow && reportRow.markdown) || ""),
  };
}

async function supabaseRequest(env, method, table, options = {}) {
  const state = supabaseState(env);
  if (!state.configured) {
    throw new Error("Supabase storage is not configured.");
  }
  const url = new URL(`${state.url}/rest/v1/${table}`);
  const params = options.params || {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  }
  const headers = new Headers({
    Accept: "application/json",
    apikey: state.serviceRoleKey,
    Authorization: `Bearer ${state.serviceRoleKey}`,
  });
  if (options.body !== undefined) {
    headers.set("content-type", "application/json");
  }
  if (state.schema && state.schema !== DEFAULT_SUPABASE_SCHEMA) {
    headers.set("accept-profile", state.schema);
    headers.set("content-profile", state.schema);
  }
  if (options.prefer) {
    headers.set("prefer", options.prefer);
  }
  const response = await fetch(url, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Supabase ${method} ${table} failed with ${response.status}: ${text.slice(0, 400)}`);
  }
  if (!text.trim()) {
    return null;
  }
  return JSON.parse(text);
}

async function supabaseSelectRows(env, table, filters = {}, options = {}) {
  const params = { select: options.select || "*", ...filters };
  if (options.order) {
    params.order = options.order;
  }
  const payload = await supabaseRequest(env, "GET", table, { params });
  return Array.isArray(payload) ? payload : [];
}

async function supabaseSelectOne(env, table, filters = {}, options = {}) {
  const rows = await supabaseSelectRows(env, table, filters, options);
  return rows[0] || null;
}

async function supabaseDeleteRows(env, table, filters) {
  await supabaseRequest(env, "DELETE", table, { params: filters, prefer: "return=minimal" });
}

async function supabaseInsertRows(env, table, rows) {
  await supabaseRequest(env, "POST", table, { body: rows, prefer: "return=representation" });
}

async function supabaseUpsertRows(env, table, rows, onConflict) {
  await supabaseRequest(env, "POST", table, {
    params: { on_conflict: onConflict },
    body: rows,
    prefer: "resolution=merge-duplicates,return=representation",
  });
}

async function loadCloudBundle(env, sessionId) {
  const sessionRow = await supabaseSelectOne(env, "lab_sessions", { session_id: `eq.${sessionId}` });
  if (!sessionRow) {
    return null;
  }
  const [turns, claims, failures, memoryEdges, reportRow] = await Promise.all([
    supabaseSelectRows(env, "lab_turns", { session_id: `eq.${sessionId}` }, { order: "created_at.asc" }),
    supabaseSelectRows(env, "claims", { session_id: `eq.${sessionId}` }, { order: "created_at.asc" }),
    supabaseSelectRows(env, "failures", { session_id: `eq.${sessionId}` }, { order: "created_at.asc" }),
    supabaseSelectRows(env, "memory_edges", { session_id: `eq.${sessionId}` }, { order: "created_at.asc" }),
    supabaseSelectOne(env, "reports", { session_id: `eq.${sessionId}` }),
  ]);
  return parseCloudBundle(sessionRow, turns, claims, failures, memoryEdges, reportRow);
}

async function saveCloudBundle(env, bundle) {
  const schema = supabaseState(env).schema;
  bundle.session.artifact_paths = cloudArtifactPaths(schema, bundle.session.session_id);
  const sessionRow = {
    ...bundle.session,
    notebook_markdown: bundle.notebook_markdown || "",
    experiments_json: Array.isArray(bundle.experiments) ? bundle.experiments : [],
  };
  await supabaseUpsertRows(env, "lab_sessions", [sessionRow], "session_id");
  await Promise.all([
    supabaseDeleteRows(env, "lab_turns", { session_id: `eq.${bundle.session.session_id}` }),
    supabaseDeleteRows(env, "claims", { session_id: `eq.${bundle.session.session_id}` }),
    supabaseDeleteRows(env, "failures", { session_id: `eq.${bundle.session.session_id}` }),
    supabaseDeleteRows(env, "memory_edges", { session_id: `eq.${bundle.session.session_id}` }),
  ]);
  if (Array.isArray(bundle.turns) && bundle.turns.length) {
    await supabaseInsertRows(env, "lab_turns", bundle.turns);
  }
  if (Array.isArray(bundle.claims) && bundle.claims.length) {
    await supabaseInsertRows(env, "claims", bundle.claims);
  }
  if (Array.isArray(bundle.failures) && bundle.failures.length) {
    await supabaseInsertRows(env, "failures", bundle.failures);
  }
  if (Array.isArray(bundle.memory_edges) && bundle.memory_edges.length) {
    await supabaseInsertRows(env, "memory_edges", bundle.memory_edges);
  }
  if (bundle.report_markdown) {
    const report = renderCloudReport(bundle);
    report.markdown = bundle.report_markdown;
    await supabaseUpsertRows(env, "reports", [report], "session_id");
  } else {
    await supabaseDeleteRows(env, "reports", { session_id: `eq.${bundle.session.session_id}` });
  }
  return bundle.session.artifact_paths;
}

function cloudSessionPayload(bundle) {
  return {
    session: bundle.session,
    session_id: bundle.session.session_id,
    latest_turns: bundle.turns.slice(-10),
    turns: bundle.turns,
    claims: bundle.claims,
    experiments: bundle.experiments,
    failures: bundle.failures,
    memory_edges: bundle.memory_edges,
    next_actions: [...bundle.session.next_actions],
    notebook_path: bundle.session.artifact_paths.notebook || "",
    report_path: bundle.session.artifact_paths.report || "",
    notebook_markdown: bundle.notebook_markdown,
    report_markdown: bundle.report_markdown,
  };
}

async function callCloudTool(name, args, env, state) {
  const supabase = supabaseState(env);
  if (name === "mystic_status") {
    return phase1MysticStatus(state, supabase);
  }
  if (name === "health_check") {
    return phase1HealthCheck(state, supabase);
  }
  if (!supabase.configured) {
    throw new Error("Supabase storage is not configured for cloud-native phase-1 mode.");
  }
  if (name === "lab_session_create") {
    const sessionId = makeCloudSessionId();
    const bundle = buildCloudSessionBundle({
      sessionId,
      problem: args.problem.trim(),
      domain: args.domain.trim(),
      goal: args.goal.trim(),
      mode: args.mode.trim(),
      participants: args.participants.map((item) => String(item)),
      schema: supabase.schema,
    });
    const paths = await saveCloudBundle(env, bundle);
    return {
      session_id: sessionId,
      status: bundle.session.status,
      current_phase: bundle.session.current_phase,
      paths,
    };
  }
  if (name === "lab_session_get") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    return cloudSessionPayload(bundle);
  }
  if (name === "lab_report_generate") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const report = renderCloudReport(bundle);
    bundle.report_markdown = report.markdown;
    bundle.session.current_phase = "completed";
    bundle.session.status = "completed";
    bundle.session.next_actions = [];
    bundle.session.updated_at = new Date().toISOString();
    const paths = await saveCloudBundle(env, bundle);
    if (!args.include_failures) {
      report.failed_claims = [];
    }
    if (!args.include_next_actions) {
      report.next_actions = [];
    }
    return {
      report_path: paths.report,
      markdown: report.markdown,
      summary: {
        surviving_claims: report.surviving_claims.length,
        failed_claims: report.failed_claims.length,
        next_actions: report.next_actions.length,
      },
    };
  }
  throw new Error(`Unsupported cloud-native tool: ${name}`);
}

async function handleCloudPhase1Mcp(request, env, state) {
  if (request.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405, headers: { allow: "POST" } });
  }
  let payload;
  try {
    payload = await request.json();
  } catch (error) {
    return jsonRpcError(null, -32700, `Invalid JSON: ${error.message}`);
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return jsonRpcError(null, -32600, "MCP requests must be a single JSON-RPC object.");
  }
  const requestId = payload.id ?? null;
  const method = String(payload.method || "");
  if (method === "initialize") {
    return jsonRpcResponse(requestId, {
      protocolVersion: "2025-06-18",
      capabilities: { tools: {} },
      serverInfo: { name: "mystic-cloud-worker", version: "0.1.0" },
    });
  }
  if (method === "ping") {
    return jsonRpcResponse(requestId, {});
  }
  if (method === "tools/list") {
    return jsonRpcResponse(requestId, { tools: CLOUD_PHASE1_TOOL_DEFINITIONS });
  }
  if (method !== "tools/call") {
    return jsonRpcError(requestId, -32601, `Unknown method: ${method}`);
  }
  const params = payload.params || {};
  const name = String(params.name || "");
  const args = params.arguments || {};
  if (!CLOUD_PHASE1_TOOL_NAMES.has(name)) {
    return jsonRpcError(requestId, -32601, `Unknown tool: ${name}`);
  }
  const argumentErrors = validateCloudToolArguments(name, args);
  if (argumentErrors.length) {
    return jsonRpcError(requestId, -32000, `Invalid params: ${argumentErrors.join("; ")}`);
  }
  try {
    const result = await callCloudTool(name, args, env, state);
    return jsonRpcResponse(requestId, {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      structuredContent: result,
      isError: false,
    });
  } catch (error) {
    return jsonRpcError(requestId, -32000, error.message);
  }
}

function b64urlEncodeBytes(bytes) {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function b64urlEncodeText(value) {
  return b64urlEncodeBytes(textEncoder.encode(value));
}

function b64urlDecodeBytes(value) {
  const normalized = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  const binary = atob(`${normalized}${padding}`);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function constantTimeEqual(a, b) {
  const left = textEncoder.encode(String(a || ""));
  const right = textEncoder.encode(String(b || ""));
  if (left.length !== right.length) {
    return false;
  }
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= left[index] ^ right[index];
  }
  return diff === 0;
}

async function importHmacKey(secret) {
  return crypto.subtle.importKey(
    "raw",
    textEncoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

async function sha256Base64Url(value) {
  const digest = await crypto.subtle.digest("SHA-256", textEncoder.encode(value));
  return b64urlEncodeBytes(new Uint8Array(digest));
}

async function signEnvelope(payload, secret) {
  const header = b64urlEncodeText(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64urlEncodeText(JSON.stringify(payload));
  const signingInput = `${header}.${body}`;
  const key = await importHmacKey(secret);
  const signatureBuffer = await crypto.subtle.sign("HMAC", key, textEncoder.encode(signingInput));
  const signature = b64urlEncodeBytes(new Uint8Array(signatureBuffer));
  return `${signingInput}.${signature}`;
}

async function verifyEnvelope(token, secret) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) {
    return null;
  }
  const [header, body, signature] = parts;
  const signingInput = `${header}.${body}`;
  const key = await importHmacKey(secret);
  const expected = await crypto.subtle.sign("HMAC", key, textEncoder.encode(signingInput));
  if (!constantTimeEqual(signature, b64urlEncodeBytes(new Uint8Array(expected)))) {
    return null;
  }
  try {
    return JSON.parse(textDecoder.decode(b64urlDecodeBytes(body)));
  } catch {
    return null;
  }
}

function scopesFromValue(scope) {
  return String(scope || DEFAULT_SCOPES)
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function isRedirectUriAllowed(redirectUri, state) {
  let parsed;
  try {
    parsed = new URL(redirectUri);
  } catch {
    return false;
  }
  if (state.allowedRedirectUris.length > 0) {
    return state.allowedRedirectUris.includes(redirectUri);
  }
  return parsed.protocol === "https:" || parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
}

function buildProtectedResourceMetadata(state) {
  return {
    resource: state.resource,
    authorization_servers: [state.issuer],
    scopes_supported: scopesFromValue(DEFAULT_SCOPES),
    bearer_methods_supported: ["header"],
    resource_documentation: `${state.issuer}/mcp`,
  };
}

function buildAuthorizationServerMetadata(state) {
  const payload = {
    issuer: state.issuer,
    authorization_endpoint: state.authorizationEndpoint,
    token_endpoint: state.tokenEndpoint,
    response_types_supported: ["code"],
    response_modes_supported: ["query"],
    grant_types_supported: ["authorization_code"],
    token_endpoint_auth_methods_supported: ["none"],
    code_challenge_methods_supported: ["S256"],
    scopes_supported: scopesFromValue(DEFAULT_SCOPES),
  };
  if (state.dynamicClientRegistrationEnabled && state.registrationEndpoint) {
    payload.registration_endpoint = state.registrationEndpoint;
  }
  if (state.jwksUri) {
    payload.jwks_uri = state.jwksUri;
  }
  return payload;
}

function buildAuthChallenge(state, options = {}) {
  const challenge = new URLSearchParams();
  challenge.set("realm", "Mystic MCP");
  challenge.set("resource_metadata", state.resourceMetadataUrl);
  challenge.set("scope", DEFAULT_SCOPES);
  if (options.error) {
    challenge.set("error", options.error);
  }
  if (options.errorDescription) {
    challenge.set("error_description", options.errorDescription);
  }
  return `Bearer ${Array.from(challenge.entries())
    .map(([key, value]) => `${key}=\"${value}\"`)
    .join(", ")}`;
}

function unauthorizedMcpResponse(state, options = {}) {
  return jsonResponse(
    {
      error: "unauthorized",
      error_description: options.errorDescription || "Bearer token required.",
    },
    401,
    {
      "cache-control": "no-store",
      "www-authenticate": buildAuthChallenge(state, options),
    },
  );
}

async function generateAuthorizationCode({ clientId, redirectUri, scope, codeChallenge, state }) {
  const payload = {
    iss: state.issuer,
    aud: state.resource,
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: scope || DEFAULT_SCOPES,
    code_challenge: codeChallenge,
    exp: Math.floor(Date.now() / 1000) + 600,
    iat: Math.floor(Date.now() / 1000),
    type: "authorization_code",
  };
  return signEnvelope(payload, state.signingSecret);
}

async function generateAccessToken({ clientId, scope, state }) {
  const payload = {
    iss: state.issuer,
    aud: state.resource,
    client_id: clientId,
    scope: scope || DEFAULT_SCOPES,
    exp: Math.floor(Date.now() / 1000) + state.tokenTtlSeconds,
    iat: Math.floor(Date.now() / 1000),
    sub: "mystic-dev-user",
    type: "access_token",
  };
  return signEnvelope(payload, state.signingSecret);
}

async function exchangeAuthorizationCode({ code, clientId, redirectUri, codeVerifier, state }) {
  const payload = await verifyEnvelope(code, state.signingSecret);
  if (!payload || payload.type !== "authorization_code") {
    return { ok: false, error: "invalid_grant", error_description: "Authorization code is invalid." };
  }
  if (payload.exp <= Math.floor(Date.now() / 1000)) {
    return { ok: false, error: "invalid_grant", error_description: "Authorization code expired." };
  }
  if (payload.client_id !== clientId || payload.redirect_uri !== redirectUri) {
    return { ok: false, error: "invalid_grant", error_description: "Authorization code client binding mismatch." };
  }
  if ((await sha256Base64Url(codeVerifier)) !== payload.code_challenge) {
    return { ok: false, error: "invalid_grant", error_description: "PKCE verification failed." };
  }
  const accessToken = await generateAccessToken({
    clientId,
    scope: payload.scope,
    state,
  });
  return {
    ok: true,
    access_token: accessToken,
    token_type: "Bearer",
    expires_in: state.tokenTtlSeconds,
    scope: payload.scope,
  };
}

async function validateAccessToken(token, state) {
  if (state.devStaticTokenConfigured && constantTimeEqual(token, state.devStaticToken)) {
    return {
      valid: true,
      payload: {
        iss: state.issuer,
        aud: state.resource,
        scope: DEFAULT_SCOPES,
        type: "access_token",
        sub: "mystic-dev-static-token",
      },
    };
  }
  const payload = await verifyEnvelope(token, state.signingSecret);
  if (!payload || payload.type !== "access_token") {
    return { valid: false, reason: "invalid_token" };
  }
  if (payload.exp <= Math.floor(Date.now() / 1000)) {
    return { valid: false, reason: "token_expired" };
  }
  if (payload.iss !== state.issuer || payload.aud !== state.resource) {
    return { valid: false, reason: "audience_mismatch" };
  }
  return { valid: true, payload };
}

function extractBearerToken(request) {
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : "";
}

async function authorizeMcpRequest(request, state) {
  if (!state.enabled) {
    return { ok: true, auth: null };
  }
  if (!state.configured) {
    return {
      ok: false,
      response: unauthorizedMcpResponse(state, {
        error: "invalid_token",
        errorDescription: "OAuth is enabled but the Worker is not fully configured.",
      }),
    };
  }
  const token = extractBearerToken(request);
  if (!token) {
    return { ok: false, response: unauthorizedMcpResponse(state) };
  }
  const validated = await validateAccessToken(token, state);
  if (!validated.valid) {
    return {
      ok: false,
      response: unauthorizedMcpResponse(state, {
        error: "invalid_token",
        errorDescription: "Bearer token validation failed.",
      }),
    };
  }
  return { ok: true, auth: validated.payload };
}

function parseAuthorizeRequest(url) {
  return {
    responseType: url.searchParams.get("response_type") || "",
    clientId: url.searchParams.get("client_id") || "",
    redirectUri: url.searchParams.get("redirect_uri") || "",
    state: url.searchParams.get("state") || "",
    scope: url.searchParams.get("scope") || DEFAULT_SCOPES,
    codeChallenge: url.searchParams.get("code_challenge") || "",
    codeChallengeMethod: url.searchParams.get("code_challenge_method") || "",
  };
}

function validateAuthorizeParams(params, state) {
  if (!state.configured) {
    return "OAuth is enabled but the Worker is missing its signing secret.";
  }
  if (params.responseType !== "code") {
    return "Only response_type=code is supported.";
  }
  if (!params.clientId || !params.redirectUri || !params.state || !params.codeChallenge) {
    return "Missing required OAuth authorization parameters.";
  }
  if (params.codeChallengeMethod !== "S256") {
    return "Only PKCE S256 is supported.";
  }
  if (!isRedirectUriAllowed(params.redirectUri, state)) {
    return "Redirect URI is not allowed.";
  }
  return "";
}

function authorizeConsentPage(params) {
  const hiddenField = (name, value) =>
    `<input type="hidden" name="${name}" value="${String(value).replace(/"/g, "&quot;")}">`;
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Mystic MCP OAuth</title>
    <style>
      body { background:#0b1020; color:#e7ecf3; font-family:ui-sans-serif,system-ui,sans-serif; padding:40px; }
      main { max-width:720px; margin:0 auto; background:#111827; border:1px solid #243041; border-radius:16px; padding:24px; }
      code { font-family:ui-monospace,SFMono-Regular,monospace; }
      button { background:#2563eb; color:white; border:none; border-radius:10px; padding:12px 18px; font-weight:600; cursor:pointer; }
      button.secondary { background:#374151; margin-left:12px; }
    </style>
  </head>
  <body>
    <main>
      <h1>Mystic MCP OAuth approval</h1>
      <p>This development OAuth flow grants an MCP client access to Mystic tools.</p>
      <p><strong>Client ID:</strong> <code>${params.clientId}</code></p>
      <p><strong>Redirect URI:</strong> <code>${params.redirectUri}</code></p>
      <p><strong>Scopes:</strong> <code>${params.scope}</code></p>
      <form method="post">
        ${hiddenField("response_type", params.responseType)}
        ${hiddenField("client_id", params.clientId)}
        ${hiddenField("redirect_uri", params.redirectUri)}
        ${hiddenField("state", params.state)}
        ${hiddenField("scope", params.scope)}
        ${hiddenField("code_challenge", params.codeChallenge)}
        ${hiddenField("code_challenge_method", params.codeChallengeMethod)}
        <input type="hidden" name="decision" value="approve">
        <button type="submit">Approve access</button>
      </form>
    </main>
  </body>
</html>`;
}

function redirectWithError(redirectUri, stateValue, error, description) {
  const redirectUrl = new URL(redirectUri);
  redirectUrl.searchParams.set("error", error);
  redirectUrl.searchParams.set("error_description", description);
  if (stateValue) {
    redirectUrl.searchParams.set("state", stateValue);
  }
  return Response.redirect(redirectUrl.toString(), 302);
}

async function handleAuthorize(request, state) {
  if (!state.enabled) {
    return errorResponse("OAuth is disabled.", 404);
  }
  if (request.method === "GET") {
    const params = parseAuthorizeRequest(new URL(request.url));
    const validationError = validateAuthorizeParams(params, state);
    if (validationError) {
      return errorResponse(validationError, 400);
    }
    return htmlResponse(authorizeConsentPage(params));
  }
  if (request.method === "POST") {
    const form = await request.formData();
    const params = {
      responseType: String(form.get("response_type") || ""),
      clientId: String(form.get("client_id") || ""),
      redirectUri: String(form.get("redirect_uri") || ""),
      state: String(form.get("state") || ""),
      scope: String(form.get("scope") || DEFAULT_SCOPES),
      codeChallenge: String(form.get("code_challenge") || ""),
      codeChallengeMethod: String(form.get("code_challenge_method") || ""),
    };
    const validationError = validateAuthorizeParams(params, state);
    if (validationError) {
      return errorResponse(validationError, 400);
    }
    const decision = String(form.get("decision") || "approve");
    if (decision !== "approve") {
      return redirectWithError(params.redirectUri, params.state, "access_denied", "User denied access.");
    }
    const code = await generateAuthorizationCode({
      clientId: params.clientId,
      redirectUri: params.redirectUri,
      scope: params.scope,
      codeChallenge: params.codeChallenge,
      state,
    });
    const redirectUrl = new URL(params.redirectUri);
    redirectUrl.searchParams.set("code", code);
    redirectUrl.searchParams.set("state", params.state);
    return Response.redirect(redirectUrl.toString(), 302);
  }
  return new Response("Method Not Allowed", { status: 405 });
}

async function handleToken(request, state) {
  if (!state.enabled) {
    return errorResponse("OAuth is disabled.", 404);
  }
  if (request.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }
  const bodyText = await request.text();
  const form = new URLSearchParams(bodyText);
  const grantType = form.get("grant_type") || "";
  const clientId = form.get("client_id") || "";
  const redirectUri = form.get("redirect_uri") || "";
  const code = form.get("code") || "";
  const codeVerifier = form.get("code_verifier") || "";
  if (grantType !== "authorization_code") {
    return jsonResponse({ error: "unsupported_grant_type" }, 400, { "cache-control": "no-store" });
  }
  if (!clientId || !redirectUri || !code || !codeVerifier) {
    return jsonResponse({ error: "invalid_request" }, 400, { "cache-control": "no-store" });
  }
  const exchanged = await exchangeAuthorizationCode({
    code,
    clientId,
    redirectUri,
    codeVerifier,
    state,
  });
  if (!exchanged.ok) {
    return jsonResponse(
      {
        error: exchanged.error,
        error_description: exchanged.error_description,
      },
      400,
      { "cache-control": "no-store" },
    );
  }
  return jsonResponse(exchanged, 200, { "cache-control": "no-store" });
}

async function proxyRequest(request, env, sourceUrl, state) {
  let origin;
  try {
    origin = await loadOrigin(env);
  } catch (error) {
    return new Response(`Mystic origin unavailable: ${error.message}`, { status: 503 });
  }

  const targetUrl = new URL(origin);
  targetUrl.pathname = sourceUrl.pathname;
  targetUrl.search = sourceUrl.search;

  const headers = new Headers(request.headers);
  headers.set("host", targetUrl.host);
  headers.set("x-forwarded-host", sourceUrl.host);
  headers.set("x-mystic-public-gateway", "cloudflare-worker");
  headers.delete("authorization");

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set("x-mystic-public-origin", origin);
  responseHeaders.set("x-mystic-public-url", sourceUrl.origin);
  if (state.enabled) {
    responseHeaders.set("cache-control", "no-store");
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

async function routeRequest(request, env) {
  const sourceUrl = new URL(request.url);
  const state = oauthState(env, request.url);
  const pathname = sourceUrl.pathname;
  const phase1CloudMode = cloudPhase1Enabled(env);

  if (pathname === "/.well-known/oauth-protected-resource" || pathname === "/.well-known/oauth-protected-resource/mcp") {
    if (!state.metadataAvailable) {
      return errorResponse("OAuth metadata not configured.", 404);
    }
    return jsonResponse(buildProtectedResourceMetadata(state), 200, { "cache-control": "no-store" });
  }

  if (pathname === "/.well-known/oauth-authorization-server" || pathname === "/.well-known/openid-configuration") {
    if (!state.metadataAvailable) {
      return errorResponse("OAuth metadata not configured.", 404);
    }
    return jsonResponse(buildAuthorizationServerMetadata(state), 200, { "cache-control": "no-store" });
  }

  if (pathname === "/oauth/authorize") {
    return handleAuthorize(request, state);
  }

  if (pathname === "/oauth/token") {
    return handleToken(request, state);
  }

  if (pathname === "/oauth/register") {
    if (!state.dynamicClientRegistrationEnabled) {
      return errorResponse("Dynamic client registration is not enabled.", 404);
    }
    return errorResponse("Dynamic client registration is not implemented.", 501);
  }

  if (pathname === "/health" && phase1CloudMode) {
    const supabase = supabaseState(env);
    const status = supabase.configured ? 200 : 503;
    return jsonResponse(
      supabase.configured
        ? { status: "ok" }
        : {
            status: "error",
            storage_backend: "supabase",
            configured: false,
            missing_env: [
              ...(!supabase.url ? ["MYSTIC_SUPABASE_URL"] : []),
              ...(!supabase.serviceRoleKey ? ["MYSTIC_SUPABASE_SERVICE_ROLE_KEY"] : []),
            ],
          },
      status,
      {
        "cache-control": "no-store",
        "x-mystic-public-origin": "worker://supabase",
      },
    );
  }

  if (pathname === "/mcp") {
    const authorization = await authorizeMcpRequest(request, state);
    if (!authorization.ok) {
      return authorization.response;
    }
    if (phase1CloudMode) {
      return handleCloudPhase1Mcp(request, env, state);
    }
  }

  return proxyRequest(request, env, sourceUrl, state);
}

async function simulateWorkerRequest(input) {
  const originalFetch = globalThis.fetch;
  const fetchCalls = [];
  if (Array.isArray(input.fetchResponses)) {
    globalThis.fetch = async (url, init = {}) => {
      const target = typeof url === "string" ? url : url.url;
      const method = String(init.method || "GET").toUpperCase();
      fetchCalls.push({
        url: target,
        method,
        body: typeof init.body === "string" ? init.body : "",
        headers: Object.fromEntries(new Headers(init.headers || {}).entries()),
      });
      const key = `${method} ${target}`;
      const entry = input.fetchResponses.find(
        (item) =>
          item.key === key ||
          item.key === target ||
          (item.prefix && target.startsWith(item.prefix)) ||
          (item.methodPrefix && key.startsWith(item.methodPrefix)),
      );
      if (!entry) {
        throw new Error(`Unexpected fetch: ${key}`);
      }
      return new Response(entry.body === undefined ? "" : JSON.stringify(entry.body), {
        status: entry.status || 200,
        headers: entry.headers || { "content-type": "application/json; charset=utf-8" },
      });
    };
  }
  try {
    const request = new Request(input.requestUrl, {
      method: input.method || "POST",
      headers: input.headers || {},
      body: input.body === undefined ? undefined : JSON.stringify(input.body),
    });
    const response = await routeRequest(request, input.env || {});
    const contentType = response.headers.get("content-type") || "";
    const text = await response.text();
    let body = text;
    if (contentType.includes("json")) {
      try {
        body = text ? JSON.parse(text) : null;
      } catch {
        body = text;
      }
    }
    return {
      status: response.status,
      headers: Object.fromEntries(response.headers.entries()),
      body,
      fetchCalls,
    };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

export const __test = {
  describeOAuth(input) {
    const state = oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp");
    return {
      enabled: state.enabled,
      configured: state.configured,
      metadataAvailable: state.metadataAvailable,
      dynamicClientRegistrationEnabled: state.dynamicClientRegistrationEnabled,
      resource: state.resource,
      issuer: state.issuer,
      resourceMetadataUrl: state.resourceMetadataUrl,
      authorizationEndpoint: state.authorizationEndpoint,
      tokenEndpoint: state.tokenEndpoint,
      registrationEndpoint: state.registrationEndpoint,
      tokenTtlSeconds: state.tokenTtlSeconds,
      devStaticTokenConfigured: state.devStaticTokenConfigured,
      signingSecret: secretPreview(state.signingSecret),
    };
  },
  buildProtectedResourceMetadata(input) {
    return buildProtectedResourceMetadata(oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp"));
  },
  buildAuthorizationServerMetadata(input) {
    return buildAuthorizationServerMetadata(oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp"));
  },
  async simulateMcpAuth(input) {
    const requestUrl = input.requestUrl || "https://mystic.dexproject.workers.dev/mcp";
    const state = oauthState(input.env || {}, requestUrl);
    const headers = new Headers(input.headers || {});
    const request = new Request(requestUrl, { method: "POST", headers, body: "{}" });
    const decision = await authorizeMcpRequest(request, state);
    if (decision.ok) {
      return { ok: true, auth: decision.auth || null };
    }
    return {
      ok: false,
      status: decision.response.status,
      headers: Object.fromEntries(decision.response.headers.entries()),
      body: await decision.response.json(),
    };
  },
  async issueAuthorizationCode(input) {
    const state = oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp");
    return generateAuthorizationCode({
      clientId: input.clientId,
      redirectUri: input.redirectUri,
      scope: input.scope || DEFAULT_SCOPES,
      codeChallenge: input.codeChallenge,
      state,
    });
  },
  async exchangeAuthorizationCode(input) {
    const state = oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp");
    return exchangeAuthorizationCode({
      code: input.code,
      clientId: input.clientId,
      redirectUri: input.redirectUri,
      codeVerifier: input.codeVerifier,
      state,
    });
  },
  async validateAccessToken(input) {
    const state = oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp");
    return validateAccessToken(input.token, state);
  },
  async pkceChallenge(input) {
    return sha256Base64Url(input.codeVerifier);
  },
  async simulateRequest(input) {
    return simulateWorkerRequest(input);
  },
};

export default {
  async fetch(request, env) {
    return routeRequest(request, env);
  },
};
