const CONFIG_URL = "https://gist.githubusercontent.com/Dezire0/778759ccca8f7d9a54c1f98662b6a9ec/raw/mystic-origin.json";
const DEFAULT_SCOPES = "tools:read tools:execute";
const DEFAULT_TOKEN_TTL_SECONDS = 3600;
const MANUAL_IMPORT_VERIFICATION_PATH = "/mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_import_verified.json";
const MANUAL_IMPORT_VERIFICATION_ENV = "MYSTIC_CHATGPT_IMPORT_VERIFICATION_JSON";
const DEFAULT_SUPABASE_SCHEMA = "public";
const PUBLIC_PROVIDER_IDS = ["openai_compatible", "gemini", "google_vertex_ai", "anthropic", "future_custom"];
const CLOUD_REQUIRED_TOOL_NAMES = [
  "mystic_status",
  "health_check",
  "lab_session_create",
  "lab_session_get",
  "lab_report_generate",
];
const IMPORT_VERIFICATION_REQUIRED_TOOLS = [
  "health_check",
  "lab_session_create",
  "lab_session_get",
  "lab_report_generate",
];
const IMPORT_VERIFICATION_FORBIDDEN_FIELD_NAMES = new Set([
  "token",
  "bearer_token",
  "access_token",
  "refresh_token",
  "client_secret",
  "signing_secret",
  "password",
  "secret",
]);
const LAB_PHASES = [
  "problem_intake",
  "background_scan",
  "hypothesis_generation",
  "experiment_design",
  "simulation_or_execution",
  "referee_review",
  "failure_archive",
  "knowledge_update",
  "next_experiment_planning",
  "report_generation",
  "completed",
];
const LAB_PHASE_TO_ROOM = {
  problem_intake: "Main Lab Room",
  background_scan: "Theory Room",
  hypothesis_generation: "Hypothesis Chamber",
  experiment_design: "Experiment Room",
  simulation_or_execution: "Simulation Tank",
  referee_review: "Referee Court",
  failure_archive: "Failure Museum",
  knowledge_update: "Research Memory Graph",
  next_experiment_planning: "Control Panel",
  report_generation: "Paper Room",
  completed: "Main Lab Room",
};
const LAB_PHASE_TO_AGENT_ROLE = {
  problem_intake: "Director",
  background_scan: "Theorist",
  hypothesis_generation: "HypothesisGenerator",
  experiment_design: "ExperimentDesigner",
  simulation_or_execution: "Simulator",
  referee_review: "Referee",
  failure_archive: "Archivist",
  knowledge_update: "Synthesizer",
  next_experiment_planning: "Director",
  report_generation: "PaperWriter",
};
const SCENE_OBJECT_SCHEMA = {
  type: "object",
  properties: {
    id: { type: "string", minLength: 1 },
    type: { type: "string", minLength: 1 },
    label: { type: "string", minLength: 1 },
    position: { type: "object" },
    rotation: { type: "object" },
    scale: { type: "object" },
    geometry: { type: "object" },
    material: { type: "object" },
    data: { type: "object" },
    metadata: { type: "object" },
  },
  required: ["id", "type", "label", "position", "rotation", "scale", "geometry", "material", "data", "metadata"],
  additionalProperties: false,
};
const CLOUD_TOOL_DEFINITIONS = [
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
    description: "Create a cloud-native Mystic Lab session in Supabase-backed storage.",
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
    name: "lab_session_advance",
    title: "Advance Lab Session",
    description: "Advance a cloud-native lab session through the next structured research steps.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        max_steps: { type: "integer", minimum: 1, maximum: 10 },
        target_phase: { type: "string", enum: LAB_PHASES.filter((item) => item !== "completed") },
        use_model_arena: { type: "boolean" },
        use_verifier: { type: "boolean" },
      },
      required: ["session_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_agent_run",
    title: "Run Lab Agent",
    description: "Run a single cloud-native lab agent turn through an explicitly configured external provider.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        agent_role: {
          type: "string",
          enum: [
            "Director",
            "Theorist",
            "HypothesisGenerator",
            "ExperimentDesigner",
            "Simulator",
            "ProofForger",
            "Referee",
            "Archivist",
            "Synthesizer",
            "PaperWriter",
            "ModelArena",
            "CodeRunner",
          ],
        },
        provider: { type: "string", minLength: 1 },
        task: { type: "string", minLength: 1 },
        context_ids: { type: "array", items: { type: "string" }, maxItems: 16 },
      },
      required: ["session_id", "agent_role", "provider", "task", "context_ids"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_referee_review",
    title: "Referee Review",
    description: "Run a structured cloud-native referee review and return a deterministic, provider-backed, or deferred verdict.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        claim_id: { type: "string" },
        text: { type: "string" },
        strictness: { type: "string", enum: ["normal", "hostile"] },
        provider: { type: "string" },
      },
      required: ["session_id", "text", "strictness"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_experiment_create",
    title: "Create Experiment",
    description: "Create a cloud-native experiment linked to an existing claim.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        claim_id: { type: "string", minLength: 1 },
        question: { type: "string", minLength: 1 },
        method: {
          type: "string",
          enum: ["python_bruteforce", "symbolic", "simulation", "unit_test", "model_debate", "manual_review"],
        },
        inputs: { type: "object" },
      },
      required: ["session_id", "claim_id", "question", "method", "inputs"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_experiment_run",
    title: "Run Experiment",
    description: "Run a cloud-native experiment or return a structured deferred/provider-required response.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        experiment_id: { type: "string", minLength: 1 },
        dry_run: { type: "boolean" },
      },
      required: ["session_id", "experiment_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_memory_search",
    title: "Search Lab Memory",
    description: "Search stored cloud-native lab sessions, claims, failures, experiments, and edges.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", minLength: 1 },
        domain: { type: "string" },
        status_filter: { type: "string" },
        limit: { type: "integer", minimum: 1, maximum: 50 },
      },
      required: ["query"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "lab_memory_write",
    title: "Write Lab Memory",
    description: "Write structured claims, failures, experiments, notes, or edges into a cloud-native lab session.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        kind: { type: "string", enum: ["claim", "failure", "experiment", "note", "edge"] },
        payload: { type: "object" },
      },
      required: ["session_id", "kind", "payload"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_models_debate",
    title: "Run Model Arena Debate",
    description: "Run a cloud-native Model Arena debate through explicitly configured external providers.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        question: { type: "string", minLength: 1 },
        participants: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 4 },
        rounds: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 8 },
        use_existing_research_table: { type: "boolean" },
      },
      required: ["session_id", "question", "participants", "rounds", "use_existing_research_table"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
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
  {
    name: "create_lab_scene",
    title: "Create Lab Scene",
    description: "Create a persisted Phase 1 scene linked to an existing cloud-native lab session.",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string", minLength: 1 },
        title: { type: "string", minLength: 1 },
        description: { type: "string" },
        units: { type: "object" },
        parameters: { type: "object" },
        metadata: { type: "object" },
      },
      required: ["session_id", "title"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "get_lab_scene",
    title: "Get Lab Scene",
    description: "Load a persisted Phase 1 scene, including its objects, simulations, report, and exports.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
      },
      required: ["scene_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "add_lab_object",
    title: "Add Lab Object",
    description: "Add a structured object to a persisted Phase 1 scene.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        object: SCENE_OBJECT_SCHEMA,
      },
      required: ["scene_id", "expected_revision", "object"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "update_lab_object",
    title: "Update Lab Object",
    description: "Update a structured object inside a persisted Phase 1 scene.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        object_id: { type: "string", minLength: 1 },
        patch: { type: "object" },
      },
      required: ["scene_id", "expected_revision", "object_id", "patch"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "remove_lab_object",
    title: "Remove Lab Object",
    description: "Remove a structured object from a persisted Phase 1 scene.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        object_id: { type: "string", minLength: 1 },
      },
      required: ["scene_id", "expected_revision", "object_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "set_lab_parameters",
    title: "Set Lab Parameters",
    description: "Set or update Phase 1 scene parameters, units, and metadata.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        parameters: { type: "object" },
        units: { type: "object" },
        metadata: { type: "object" },
      },
      required: ["scene_id", "expected_revision", "parameters"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "run_lab_simulation",
    title: "Run Lab Simulation",
    description: "Run a deterministic Phase 1 scene adapter or return a structured engine-required result.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        adapter_id: { type: "string", enum: ["math.sympy", "physics.simple_projectile", "physics.simple_collision"] },
        inputs: { type: "object" },
      },
      required: ["scene_id", "expected_revision", "adapter_id", "inputs"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "attach_simulation_to_scene",
    title: "Attach Simulation To Scene",
    description: "Attach a stored simulation result to a scene and optionally apply its object updates.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        simulation_id: { type: "string", minLength: 1 },
        object_ids: { type: "array", items: { type: "string" }, maxItems: 32 },
        evidence_refs: { type: "array", items: { type: "string" }, maxItems: 32 },
        report_refs: { type: "array", items: { type: "string" }, maxItems: 32 },
        apply_object_updates: { type: "boolean" },
      },
      required: ["scene_id", "expected_revision", "simulation_id", "apply_object_updates"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "export_lab_snapshot",
    title: "Export Lab Snapshot",
    description: "Export a persisted scene through the scene.three_json Phase 1 adapter.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        adapter_id: { type: "string", enum: ["scene.three_json"] },
        include_simulations: { type: "boolean" },
      },
      required: ["scene_id", "expected_revision", "adapter_id", "include_simulations"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "generate_lab_report",
    title: "Generate Scene Report",
    description: "Generate a markdown scene report that links objects, simulations, and archive references.",
    inputSchema: {
      type: "object",
      properties: {
        scene_id: { type: "string", minLength: 1 },
        expected_revision: { type: "integer", minimum: 1 },
        format: { type: "string", enum: ["markdown"] },
        include_objects: { type: "boolean" },
        include_simulations: { type: "boolean" },
      },
      required: ["scene_id", "expected_revision", "format", "include_objects", "include_simulations"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "provider_list",
    title: "List Providers",
    description: "List known external model providers and their current Provider Connect status without exposing secrets.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_status",
    title: "Provider Status",
    description: "Inspect one Provider Connect record and its current safe configuration status.",
    inputSchema: {
      type: "object",
      properties: { provider_id: { type: "string", minLength: 1 } },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_connect_start",
    title: "Start Provider Connect",
    description: "Return a real provider authorization URL when OAuth is configured, or a secure Mystic LAB setup URL when API-key auth is required.",
    inputSchema: {
      type: "object",
      properties: {
        provider_id: { type: "string", minLength: 1 },
        auth_method: { type: "string", enum: ["api_key", "oauth", "bearer_token", "none/mock"] },
      },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "provider_connect_callback_status",
    title: "Provider Callback Status",
    description: "Check the safe stored status of a provider OAuth flow without exposing raw codes, tokens, or secrets.",
    inputSchema: {
      type: "object",
      properties: {
        provider_id: { type: "string", minLength: 1 },
        flow_id: { type: "string", minLength: 1 },
      },
      required: ["provider_id", "flow_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_configure_secret_instructions",
    title: "Provider Secret Instructions",
    description: "Return exact safe Cloudflare secret setup instructions for a provider without printing secret values.",
    inputSchema: {
      type: "object",
      properties: { provider_id: { type: "string", minLength: 1 } },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_verify",
    title: "Verify Provider",
    description: "Verify whether a provider appears configured while keeping secrets server-side.",
    inputSchema: {
      type: "object",
      properties: { provider_id: { type: "string", minLength: 1 } },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_disconnect",
    title: "Disconnect Provider",
    description: "Mark a provider disconnected without deleting any existing Cloudflare secrets.",
    inputSchema: {
      type: "object",
      properties: { provider_id: { type: "string", minLength: 1 } },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "provider_model_list",
    title: "Provider Model List",
    description: "Return a provider model list when configuration is present, or a structured required-status response otherwise.",
    inputSchema: {
      type: "object",
      properties: { provider_id: { type: "string", minLength: 1 } },
      required: ["provider_id"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "provider_call_test",
    title: "Provider Call Test",
    description: "Run a Provider Connect foundation test. Real provider calls stay disabled here unless a mock provider is explicitly used in tests.",
    inputSchema: {
      type: "object",
      properties: {
        provider_id: { type: "string", minLength: 1 },
        prompt: { type: "string", minLength: 1 },
      },
      required: ["provider_id", "prompt"],
      additionalProperties: false,
    },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
  },
  {
    name: "lab_session_list",
    title: "List Lab Sessions",
    description: "List persisted Mystic LAB sessions with safe summaries.",
    inputSchema: { type: "object", properties: { limit: { type: "integer", minimum: 1, maximum: 100 }, status_filter: { type: "string" }, domain_filter: { type: "string" }, updated_after: { type: "string" } }, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "lab_scene_list",
    title: "List Lab Scenes",
    description: "List persisted Mystic LAB scenes with authoritative counts and revisions.",
    inputSchema: { type: "object", properties: { limit: { type: "integer", minimum: 1, maximum: 100 }, session_id: { type: "string" }, updated_after: { type: "string" } }, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
  {
    name: "lab_activity_list",
    title: "List Lab Activity",
    description: "List safe persisted Mystic LAB audit events.",
    inputSchema: { type: "object", properties: { limit: { type: "integer", minimum: 1, maximum: 100 }, session_id: { type: "string" }, updated_after: { type: "string" } }, additionalProperties: false },
    securitySchemes: [{ type: "oauth2", scopes: ["tools:read", "tools:execute"] }],
    annotations: { readOnlyHint: true },
  },
];
const CLOUD_TOOL_NAMES = new Set(CLOUD_TOOL_DEFINITIONS.map((tool) => tool.name));
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
const authorizationCodeMemoryStore = new Map();

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

function cloudSceneArtifactPaths(schema, sceneId) {
  return {
    scene: `supabase://${schema}/lab_scenes/${sceneId}`,
    objects: `supabase://${schema}/lab_scene_objects?scene_id=${sceneId}`,
    simulations: `supabase://${schema}/lab_simulations?scene_id=${sceneId}`,
    report: `supabase://${schema}/lab_scenes/${sceneId}#report`,
    snapshot: `supabase://${schema}/lab_scenes/${sceneId}#exports`,
  };
}

function objectMapping(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? { ...value } : {};
}

function numericValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeVector(value, defaults = { x: 0, y: 0, z: 0 }) {
  const payload = objectMapping(value);
  return {
    x: numericValue(payload.x, defaults.x),
    y: numericValue(payload.y, defaults.y),
    z: numericValue(payload.z, defaults.z),
  };
}

function normalizeSceneObjectPayload(sceneId, payload, existing = {}) {
  const merged = { ...objectMapping(existing), ...objectMapping(payload) };
  const objectId = trimmed(merged.id, `obj-${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`);
  const objectType = trimmed(merged.type);
  const label = trimmed(merged.label, objectType || objectId);
  if (!objectType) {
    throw new Error("scene object type is required");
  }
  return {
    scene_id: sceneId,
    id: objectId,
    type: objectType,
    label,
    position: normalizeVector(merged.position, { x: 0, y: 0, z: 0 }),
    rotation: normalizeVector(merged.rotation, { x: 0, y: 0, z: 0 }),
    scale: normalizeVector(merged.scale, { x: 1, y: 1, z: 1 }),
    geometry: objectMapping(merged.geometry),
    material: objectMapping(merged.material),
    data: objectMapping(merged.data),
    metadata: objectMapping(merged.metadata),
    created_at: trimmed(merged.created_at, nowIso()),
    updated_at: nowIso(),
  };
}

function parseCloudSceneBundle(sceneRow, objectRows, simulationRows) {
  return {
    scene: {
      scene_id: sceneRow.scene_id,
      session_id: sceneRow.session_id,
      domain: sceneRow.domain,
      title: sceneRow.title,
      description: trimmed(sceneRow.description),
      units: objectMapping(sceneRow.units),
      parameters: objectMapping(sceneRow.parameters),
      attached_simulations: asStringArray(sceneRow.attached_simulations),
      evidence_refs: asStringArray(sceneRow.evidence_refs),
      report_refs: asStringArray(sceneRow.report_refs),
      metadata: objectMapping(sceneRow.metadata),
      artifact_paths: objectMapping(sceneRow.artifact_paths),
      exports_json: objectMapping(sceneRow.exports_json),
      report_markdown: trimmed(sceneRow.report_markdown),
      revision: Number(sceneRow.revision || 1),
      created_at: trimmed(sceneRow.created_at),
      updated_at: trimmed(sceneRow.updated_at),
    },
    objects: Array.isArray(objectRows) ? objectRows.map((row) => normalizeSceneObjectPayload(sceneRow.scene_id, row, row)) : [],
    simulations: Array.isArray(simulationRows)
      ? simulationRows.map((row) => ({
          simulation_id: row.simulation_id,
          scene_id: row.scene_id,
          session_id: row.session_id,
          adapter_id: row.adapter_id,
          status: row.status,
          inputs: objectMapping(row.inputs),
          outputs: objectMapping(row.outputs),
          evidence: objectMapping(row.evidence),
          warnings: asStringArray(row.warnings),
          errors: asStringArray(row.errors),
          attached_object_ids: asStringArray(row.attached_object_ids),
          metadata: objectMapping(row.metadata),
          created_at: trimmed(row.created_at),
          updated_at: trimmed(row.updated_at),
        }))
      : [],
  };
}

async function loadCloudSceneBundle(env, sceneId) {
  const sceneRow = await supabaseSelectOne(env, "lab_scenes", { scene_id: `eq.${sceneId}` });
  if (!sceneRow) {
    return null;
  }
  const [objectRows, simulationRows] = await Promise.all([
    supabaseSelectRows(env, "lab_scene_objects", { scene_id: `eq.${sceneId}` }, { order: "created_at.asc" }),
    supabaseSelectRows(env, "lab_simulations", { scene_id: `eq.${sceneId}` }, { order: "created_at.asc" }),
  ]);
  return parseCloudSceneBundle(sceneRow, objectRows, simulationRows);
}

async function saveCloudSceneBundle(env, bundle, expectedRevision, activity) {
  const schema = supabaseState(env).schema;
  bundle.scene.artifact_paths = cloudSceneArtifactPaths(schema, bundle.scene.scene_id);
  const guardedRevision = Number.isInteger(Number(expectedRevision)) ? Number(expectedRevision) : Number(bundle.scene.revision || 0);
  if (guardedRevision > 0) {
    const result = await supabaseRpc(env, "mystic_mutate_lab_scene", {
      p_scene_id: bundle.scene.scene_id,
      p_expected_revision: guardedRevision,
      p_scene: bundle.scene,
      p_objects: bundle.objects,
      p_simulations: bundle.simulations,
      p_activity: activity || null,
    });
    if (result && result.error) {
      const error = new Error(result.safe_message || result.error);
      error.code = result.error;
      error.expected_revision = result.expected_revision;
      error.current_revision = result.current_revision;
      throw error;
    }
    bundle.scene.revision = Number(result?.revision || guardedRevision + 1);
    bundle.scene.updated_at = String(result?.updated_at || nowIso());
    return bundle.scene.artifact_paths;
  }
  bundle.scene.updated_at = nowIso();
  await supabaseUpsertRows(env, "lab_scenes", [bundle.scene], "scene_id");
  await Promise.all([
    supabaseDeleteRows(env, "lab_scene_objects", { scene_id: `eq.${bundle.scene.scene_id}` }),
    supabaseDeleteRows(env, "lab_simulations", { scene_id: `eq.${bundle.scene.scene_id}` }),
  ]);
  if (Array.isArray(bundle.objects) && bundle.objects.length) {
    await supabaseInsertRows(env, "lab_scene_objects", bundle.objects);
  }
  if (Array.isArray(bundle.simulations) && bundle.simulations.length) {
    await supabaseInsertRows(env, "lab_simulations", bundle.simulations);
  }
  if (activity) {
    await supabaseInsertRows(env, "lab_activity_events", [{
      event_id: activity.event_id || cloudId("event"),
      event_type: activity.event_type || "scene_mutation",
      session_id: activity.session_id || bundle.scene.session_id,
      scene_id: bundle.scene.scene_id,
      tool_name: activity.tool_name || "scene_mutation",
      status: activity.status || "completed",
      safe_summary: activity.safe_summary || "Scene changed.",
      metadata_safe: objectMapping(activity.metadata_safe),
    }]);
  }
  return bundle.scene.artifact_paths;
}

function cloudSceneMutationActivity(toolName, sceneBundle) {
  return {
    event_id: cloudId("event"),
    event_type: "scene_mutation",
    session_id: sceneBundle.scene.session_id,
    tool_name: toolName,
    status: "completed",
    safe_summary: `Scene changed by ${toolName}.`,
  };
}

function cloudScenePayload(bundle) {
  return {
    scene: bundle.scene,
    scene_id: bundle.scene.scene_id,
    session_id: bundle.scene.session_id,
    objects: bundle.objects,
    simulations: bundle.simulations,
    attached_simulations: [...bundle.scene.attached_simulations],
    report_path: bundle.scene.artifact_paths.report || "",
    snapshot_path: bundle.scene.artifact_paths.snapshot || "",
    report_markdown: bundle.scene.report_markdown,
    exports: bundle.scene.exports_json,
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
  if (["lab_session_list", "lab_scene_list", "lab_activity_list"].includes(name) && args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 100)) {
    errors.push("limit must be an integer between 1 and 100");
  }
  if (["add_lab_object", "update_lab_object", "remove_lab_object", "set_lab_parameters", "run_lab_simulation", "attach_simulation_to_scene", "export_lab_snapshot", "generate_lab_report"].includes(name) && (!Number.isInteger(args.expected_revision) || args.expected_revision < 1)) {
    errors.push("expected_revision must be a positive integer");
  }
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
  if (
    name === "lab_session_get" ||
    name === "lab_report_generate" ||
    name === "lab_session_advance" ||
    name === "lab_agent_run" ||
    name === "lab_referee_review" ||
    name === "lab_experiment_create" ||
    name === "lab_experiment_run" ||
    name === "lab_memory_write" ||
    name === "lab_models_debate" ||
    name === "create_lab_scene"
  ) {
    if (typeof args.session_id !== "string" || !args.session_id.trim()) {
      errors.push("session_id is required");
    }
  }
  if (
    name === "get_lab_scene" ||
    name === "add_lab_object" ||
    name === "update_lab_object" ||
    name === "remove_lab_object" ||
    name === "set_lab_parameters" ||
    name === "run_lab_simulation" ||
    name === "attach_simulation_to_scene" ||
    name === "export_lab_snapshot" ||
    name === "generate_lab_report"
  ) {
    if (typeof args.scene_id !== "string" || !args.scene_id.trim()) {
      errors.push("scene_id is required");
    }
  }
  if (name === "lab_session_advance") {
    if (args.max_steps !== undefined && (!Number.isInteger(args.max_steps) || args.max_steps < 1 || args.max_steps > 10)) {
      errors.push("max_steps must be an integer between 1 and 10");
    }
    if (args.target_phase !== undefined && typeof args.target_phase !== "string") {
      errors.push("target_phase must be a string");
    }
    if (args.use_model_arena !== undefined && typeof args.use_model_arena !== "boolean") {
      errors.push("use_model_arena must be boolean");
    }
    if (args.use_verifier !== undefined && typeof args.use_verifier !== "boolean") {
      errors.push("use_verifier must be boolean");
    }
  }
  if (name === "lab_agent_run") {
    if (typeof args.agent_role !== "string" || !args.agent_role.trim()) {
      errors.push("agent_role is required");
    }
    if (typeof args.provider !== "string" || !args.provider.trim()) {
      errors.push("provider is required");
    }
    if (typeof args.task !== "string" || !args.task.trim()) {
      errors.push("task is required");
    }
    if (!Array.isArray(args.context_ids)) {
      errors.push("context_ids must be an array");
    }
  }
  if (name === "lab_referee_review") {
    if (typeof args.text !== "string") {
      errors.push("text must be a string");
    }
    if (typeof args.strictness !== "string" || !["normal", "hostile"].includes(args.strictness)) {
      errors.push("strictness must be normal or hostile");
    }
    if (args.claim_id !== undefined && typeof args.claim_id !== "string") {
      errors.push("claim_id must be a string when provided");
    }
    if (args.provider !== undefined && typeof args.provider !== "string") {
      errors.push("provider must be a string when provided");
    }
  }
  if (name === "lab_experiment_create") {
    if (typeof args.claim_id !== "string" || !args.claim_id.trim()) {
      errors.push("claim_id is required");
    }
    if (typeof args.question !== "string" || !args.question.trim()) {
      errors.push("question is required");
    }
    if (typeof args.method !== "string" || !args.method.trim()) {
      errors.push("method is required");
    }
    if (!args.inputs || typeof args.inputs !== "object" || Array.isArray(args.inputs)) {
      errors.push("inputs must be an object");
    }
  }
  if (name === "lab_experiment_run") {
    if (typeof args.experiment_id !== "string" || !args.experiment_id.trim()) {
      errors.push("experiment_id is required");
    }
    if (args.dry_run !== undefined && typeof args.dry_run !== "boolean") {
      errors.push("dry_run must be boolean");
    }
  }
  if (name === "lab_memory_search") {
    if (typeof args.query !== "string" || !args.query.trim()) {
      errors.push("query is required");
    }
    if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 50)) {
      errors.push("limit must be an integer between 1 and 50");
    }
  }
  if (name === "lab_memory_write") {
    if (typeof args.kind !== "string" || !args.kind.trim()) {
      errors.push("kind is required");
    }
    if (!args.payload || typeof args.payload !== "object" || Array.isArray(args.payload)) {
      errors.push("payload must be an object");
    }
  }
  if (name === "lab_models_debate") {
    if (typeof args.question !== "string" || !args.question.trim()) {
      errors.push("question is required");
    }
    if (!Array.isArray(args.participants) || args.participants.length < 1) {
      errors.push("participants must contain at least one entry");
    }
    if (!Array.isArray(args.rounds) || args.rounds.length < 1) {
      errors.push("rounds must contain at least one entry");
    }
    if (typeof args.use_existing_research_table !== "boolean") {
      errors.push("use_existing_research_table must be boolean");
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
  if (name === "create_lab_scene") {
    if (typeof args.title !== "string" || !args.title.trim()) {
      errors.push("title is required");
    }
    for (const key of ["description", "units", "parameters", "metadata"]) {
      if (args[key] !== undefined && key === "description" && typeof args[key] !== "string") {
        errors.push("description must be a string");
      }
      if (args[key] !== undefined && key !== "description" && (!args[key] || typeof args[key] !== "object" || Array.isArray(args[key]))) {
        errors.push(`${key} must be an object`);
      }
    }
  }
  if (name === "add_lab_object") {
    if (!args.object || typeof args.object !== "object" || Array.isArray(args.object)) {
      errors.push("object must be an object");
    }
  }
  if (name === "update_lab_object") {
    if (typeof args.object_id !== "string" || !args.object_id.trim()) {
      errors.push("object_id is required");
    }
    if (!args.patch || typeof args.patch !== "object" || Array.isArray(args.patch)) {
      errors.push("patch must be an object");
    }
  }
  if (name === "remove_lab_object") {
    if (typeof args.object_id !== "string" || !args.object_id.trim()) {
      errors.push("object_id is required");
    }
  }
  if (name === "set_lab_parameters") {
    if (!args.parameters || typeof args.parameters !== "object" || Array.isArray(args.parameters)) {
      errors.push("parameters must be an object");
    }
    for (const key of ["units", "metadata"]) {
      if (args[key] !== undefined && (!args[key] || typeof args[key] !== "object" || Array.isArray(args[key]))) {
        errors.push(`${key} must be an object`);
      }
    }
  }
  if (name === "run_lab_simulation") {
    if (typeof args.adapter_id !== "string" || !args.adapter_id.trim()) {
      errors.push("adapter_id is required");
    }
    if (!args.inputs || typeof args.inputs !== "object" || Array.isArray(args.inputs)) {
      errors.push("inputs must be an object");
    }
  }
  if (name === "attach_simulation_to_scene") {
    if (typeof args.simulation_id !== "string" || !args.simulation_id.trim()) {
      errors.push("simulation_id is required");
    }
    if (typeof args.apply_object_updates !== "boolean") {
      errors.push("apply_object_updates must be boolean");
    }
    for (const key of ["object_ids", "evidence_refs", "report_refs"]) {
      if (args[key] !== undefined && !Array.isArray(args[key])) {
        errors.push(`${key} must be an array`);
      }
    }
  }
  if (name === "export_lab_snapshot") {
    if (args.adapter_id !== "scene.three_json") {
      errors.push("adapter_id must be scene.three_json");
    }
    if (typeof args.include_simulations !== "boolean") {
      errors.push("include_simulations must be boolean");
    }
  }
  if (name === "generate_lab_report") {
    if (args.format !== "markdown") {
      errors.push("format must be markdown");
    }
    if (typeof args.include_objects !== "boolean") {
      errors.push("include_objects must be boolean");
    }
    if (typeof args.include_simulations !== "boolean") {
      errors.push("include_simulations must be boolean");
    }
  }
  if (
    name === "provider_status" ||
    name === "provider_connect_start" ||
    name === "provider_configure_secret_instructions" ||
    name === "provider_verify" ||
    name === "provider_disconnect" ||
    name === "provider_model_list" ||
    name === "provider_call_test"
  ) {
    if (typeof args.provider_id !== "string" || !args.provider_id.trim()) {
      errors.push("provider_id is required");
    }
  }
  if (name === "provider_connect_start") {
    if (args.auth_method !== undefined && !["api_key", "oauth", "bearer_token", "none/mock"].includes(String(args.auth_method))) {
      errors.push("auth_method must be api_key, oauth, bearer_token, or none/mock");
    }
  }
  if (name === "provider_connect_callback_status") {
    if (typeof args.provider_id !== "string" || !args.provider_id.trim()) {
      errors.push("provider_id is required");
    }
    if (typeof args.flow_id !== "string" || !args.flow_id.trim()) {
      errors.push("flow_id is required");
    }
  }
  if (name === "provider_call_test") {
    if (typeof args.prompt !== "string" || !args.prompt.trim()) {
      errors.push("prompt is required");
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
  const params = { select: options.select || "*", ...filters, ...(options.params || {}) };
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

async function supabaseRpc(env, functionName, body) {
  return supabaseRequest(env, "POST", `rpc/${functionName}`, { body });
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

function cloudEngineRequired(adapterId, message, extra = {}) {
  return {
    status: "engine_required",
    adapter_id: adapterId,
    message,
    supported_in_cloud_mode: adapterId !== "math.sympy",
    ...extra,
  };
}

function cloudCompleted(adapterId, { inputs, outputs, evidence, warnings = [] }) {
  return {
    status: "completed",
    adapter_id: adapterId,
    inputs,
    outputs,
    evidence,
    warnings,
    errors: [],
  };
}

function cloudUnsupportedExpression(adapterId, message, extra = {}) {
  return {
    status: "unsupported_expression",
    adapter_id: adapterId,
    message,
    supported_in_cloud_mode: true,
    ...extra,
  };
}

function normalizeMathExpression(expression) {
  return String(expression || "");
}

function mathNumberNode(value) {
  let normalized = Number(value);
  if (Math.abs(normalized) <= 1e-12) {
    normalized = 0;
  }
  if (Math.abs(normalized - Math.round(normalized)) <= 1e-12) {
    normalized = Math.round(normalized);
  }
  return { type: "number", value: normalized };
}

function isMathNumberNode(node) {
  return node?.type === "number" && Number.isFinite(node.value);
}

function mathIsZeroNode(node) {
  return isMathNumberNode(node) && Math.abs(node.value) <= 1e-12;
}

function mathIsOneNode(node) {
  return isMathNumberNode(node) && Math.abs(node.value - 1) <= 1e-12;
}

function tokenizeMathExpression(expression) {
  const text = normalizeMathExpression(expression);
  const tokens = [];
  let index = 0;
  while (index < text.length) {
    const char = text[index];
    if (/\s/.test(char)) {
      index += 1;
      continue;
    }
    if ("+-*/^()".includes(char)) {
      tokens.push({ type: char });
      index += 1;
      continue;
    }
    if (char === "=") {
      tokens.push({ type: "=" });
      index += 1;
      continue;
    }
    if (/[0-9.]/.test(char)) {
      const start = index;
      let seenDot = false;
      let seenDigit = false;
      while (index < text.length) {
        const current = text[index];
        if (/[0-9]/.test(current)) {
          seenDigit = true;
          index += 1;
          continue;
        }
        if (current === "." && !seenDot) {
          seenDot = true;
          index += 1;
          continue;
        }
        break;
      }
      const raw = text.slice(start, index);
      if (!seenDigit) {
        throw new Error("Invalid numeric literal");
      }
      const value = Number(raw);
      if (!Number.isFinite(value)) {
        throw new Error("Invalid numeric literal");
      }
      tokens.push({ type: "number", value });
      continue;
    }
    if (/[A-Za-z_]/.test(char)) {
      const start = index;
      index += 1;
      while (index < text.length && /[A-Za-z0-9_]/.test(text[index])) {
        index += 1;
      }
      tokens.push({ type: "identifier", value: text.slice(start, index) });
      continue;
    }
    throw new Error(`Unsupported token: ${char}`);
  }
  tokens.push({ type: "eof" });
  return tokens;
}

function parseMathExpression(expression) {
  const tokens = tokenizeMathExpression(expression);
  let index = 0;
  const peek = () => tokens[index];
  const consume = (type) => {
    const token = tokens[index];
    if (!token || token.type !== type) {
      throw new Error(`Expected '${type}'`);
    }
    index += 1;
    return token;
  };

  function parseExpression() {
    return parseAdditive();
  }

  function parseAdditive() {
    let node = parseMultiplicative();
    while (peek().type === "+" || peek().type === "-") {
      const operator = consume(peek().type).type;
      node = { type: "binary", operator, left: node, right: parseMultiplicative() };
    }
    return node;
  }

  function parseMultiplicative() {
    let node = parsePower();
    while (peek().type === "*" || peek().type === "/") {
      const operator = consume(peek().type).type;
      node = { type: "binary", operator, left: node, right: parsePower() };
    }
    return node;
  }

  function parsePower() {
    let node = parseUnary();
    if (peek().type === "^") {
      consume("^");
      node = { type: "binary", operator: "^", left: node, right: parsePower() };
    }
    return node;
  }

  function parseUnary() {
    if (peek().type === "+" || peek().type === "-") {
      const operator = consume(peek().type).type;
      return { type: "unary", operator, operand: parseUnary() };
    }
    return parsePrimary();
  }

  function parsePrimary() {
    if (peek().type === "number") {
      return mathNumberNode(consume("number").value);
    }
    if (peek().type === "identifier") {
      const token = consume("identifier");
      if (peek().type === "(") {
        throw new Error(`Unsupported function call: ${token.value}`);
      }
      return { type: "variable", name: token.value };
    }
    if (peek().type === "(") {
      consume("(");
      const node = parseExpression();
      consume(")");
      return node;
    }
    throw new Error(`Unexpected token: ${peek().type}`);
  }

  const parsed = parseExpression();
  if (peek().type !== "eof") {
    throw new Error(`Unexpected token: ${peek().type}`);
  }
  return parsed;
}

function cloudMathVariables(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  const payload = {};
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "boolean") {
      continue;
    }
    const numeric = Number(item);
    if (Number.isFinite(numeric)) {
      payload[String(key)] = numeric;
    }
  }
  return payload;
}

function evaluateNumericMathAst(node) {
  if (isMathNumberNode(node)) {
    return node.value;
  }
  if (node?.type === "unary") {
    const operand = evaluateNumericMathAst(node.operand);
    if (node.operator === "+") {
      return operand;
    }
    if (node.operator === "-") {
      return -operand;
    }
  }
  if (node?.type === "binary") {
    const left = evaluateNumericMathAst(node.left);
    const right = evaluateNumericMathAst(node.right);
    if (node.operator === "+") {
      return left + right;
    }
    if (node.operator === "-") {
      return left - right;
    }
    if (node.operator === "*") {
      return left * right;
    }
    if (node.operator === "/") {
      return left / right;
    }
    if (node.operator === "^") {
      return left ** right;
    }
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function substituteMathAst(node, variables) {
  if (isMathNumberNode(node)) {
    return mathNumberNode(node.value);
  }
  if (node?.type === "variable") {
    if (Object.prototype.hasOwnProperty.call(variables, node.name)) {
      return mathNumberNode(variables[node.name]);
    }
    return { type: "variable", name: node.name };
  }
  if (node?.type === "unary") {
    return { type: "unary", operator: node.operator, operand: substituteMathAst(node.operand, variables) };
  }
  if (node?.type === "binary") {
    return {
      type: "binary",
      operator: node.operator,
      left: substituteMathAst(node.left, variables),
      right: substituteMathAst(node.right, variables),
    };
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function simplifyMathAst(node) {
  if (isMathNumberNode(node)) {
    return mathNumberNode(node.value);
  }
  if (node?.type === "variable") {
    return { type: "variable", name: node.name };
  }
  if (node?.type === "unary") {
    const operand = simplifyMathAst(node.operand);
    if (node.operator === "+") {
      return operand;
    }
    if (node.operator === "-") {
      if (isMathNumberNode(operand)) {
        return mathNumberNode(-operand.value);
      }
      return { type: "unary", operator: "-", operand };
    }
  }
  if (node?.type === "binary") {
    const left = simplifyMathAst(node.left);
    const right = simplifyMathAst(node.right);
    if (isMathNumberNode(left) && isMathNumberNode(right)) {
      return mathNumberNode(evaluateNumericMathAst({ type: "binary", operator: node.operator, left, right }));
    }
    if (node.operator === "+") {
      if (mathIsZeroNode(left)) {
        return right;
      }
      if (mathIsZeroNode(right)) {
        return left;
      }
    }
    if (node.operator === "-") {
      if (mathIsZeroNode(right)) {
        return left;
      }
    }
    if (node.operator === "*") {
      if (mathIsZeroNode(left) || mathIsZeroNode(right)) {
        return mathNumberNode(0);
      }
      if (mathIsOneNode(left)) {
        return right;
      }
      if (mathIsOneNode(right)) {
        return left;
      }
    }
    if (node.operator === "/") {
      if (mathIsZeroNode(left) && isMathNumberNode(right) && Math.abs(right.value) > 1e-12) {
        return mathNumberNode(0);
      }
      if (mathIsOneNode(right)) {
        return left;
      }
    }
    if (node.operator === "^") {
      if (mathIsZeroNode(right)) {
        return mathNumberNode(1);
      }
      if (mathIsOneNode(right)) {
        return left;
      }
      if (mathIsOneNode(left)) {
        return mathNumberNode(1);
      }
      if (mathIsZeroNode(left) && isMathNumberNode(right) && right.value > 0) {
        return mathNumberNode(0);
      }
    }
    return { type: "binary", operator: node.operator, left, right };
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function collectMathSymbols(node, symbols = new Set()) {
  if (isMathNumberNode(node)) {
    return symbols;
  }
  if (node?.type === "variable") {
    symbols.add(node.name);
    return symbols;
  }
  if (node?.type === "unary") {
    return collectMathSymbols(node.operand, symbols);
  }
  if (node?.type === "binary") {
    collectMathSymbols(node.left, symbols);
    collectMathSymbols(node.right, symbols);
    return symbols;
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function formatMathNumber(value) {
  if (Math.abs(value - Math.round(value)) <= 1e-12) {
    return String(Math.round(value));
  }
  return Number(value.toFixed(12)).toString();
}

function mathPrecedence(node) {
  if (isMathNumberNode(node) || node?.type === "variable") {
    return 4;
  }
  if (node?.type === "unary") {
    return 3;
  }
  if (node?.type === "binary") {
    if (node.operator === "^") {
      return 3;
    }
    if (node.operator === "*" || node.operator === "/") {
      return 2;
    }
    if (node.operator === "+" || node.operator === "-") {
      return 1;
    }
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function formatMathAst(node, parentPrecedence = -1, isRightChild = false) {
  if (isMathNumberNode(node)) {
    return formatMathNumber(node.value);
  }
  if (node?.type === "variable") {
    return node.name;
  }
  if (node?.type === "unary") {
    const precedence = 3;
    const text = `${node.operator}${formatMathAst(node.operand, precedence)}`;
    return precedence < parentPrecedence ? `(${text})` : text;
  }
  if (node?.type === "binary") {
    const precedence = mathPrecedence(node);
    const leftText = formatMathAst(node.left, precedence);
    const rightText = formatMathAst(
      node.right,
      node.operator === "^" ? precedence : precedence + 1,
      true,
    );
    const text = `${leftText} ${node.operator} ${rightText}`;
    if (node.operator === "^" && isRightChild && precedence < parentPrecedence) {
      return `(${text})`;
    }
    return precedence < parentPrecedence ? `(${text})` : text;
  }
  throw new Error("Unsupported expression for math.sympy cloud subset");
}

function linearMathForm(node, variable, variables) {
  if (isMathNumberNode(node)) {
    return { coefficient: 0, constant: node.value };
  }
  if (node?.type === "variable") {
    if (node.name === variable) {
      return { coefficient: 1, constant: 0 };
    }
    if (Object.prototype.hasOwnProperty.call(variables, node.name)) {
      return { coefficient: 0, constant: variables[node.name] };
    }
    throw new Error(`Unknown variable: ${node.name}`);
  }
  if (node?.type === "unary") {
    const value = linearMathForm(node.operand, variable, variables);
    if (node.operator === "+") {
      return value;
    }
    if (node.operator === "-") {
      return { coefficient: -value.coefficient, constant: -value.constant };
    }
  }
  if (node?.type === "binary") {
    const left = linearMathForm(node.left, variable, variables);
    const right = linearMathForm(node.right, variable, variables);
    if (node.operator === "+") {
      return { coefficient: left.coefficient + right.coefficient, constant: left.constant + right.constant };
    }
    if (node.operator === "-") {
      return { coefficient: left.coefficient - right.coefficient, constant: left.constant - right.constant };
    }
    if (node.operator === "*") {
      if (Math.abs(left.coefficient) > 1e-12 && Math.abs(right.coefficient) > 1e-12) {
        throw new Error("Non-linear multiplication is unsupported");
      }
      if (Math.abs(left.coefficient) > 1e-12) {
        return { coefficient: left.coefficient * right.constant, constant: left.constant * right.constant };
      }
      if (Math.abs(right.coefficient) > 1e-12) {
        return { coefficient: right.coefficient * left.constant, constant: right.constant * left.constant };
      }
      return { coefficient: 0, constant: left.constant * right.constant };
    }
    if (node.operator === "/") {
      if (Math.abs(right.coefficient) > 1e-12) {
        throw new Error("Division by a symbolic term is unsupported");
      }
      return { coefficient: left.coefficient / right.constant, constant: left.constant / right.constant };
    }
    if (node.operator === "^") {
      if (Math.abs(left.coefficient) > 1e-12 || Math.abs(right.coefficient) > 1e-12) {
        throw new Error("Symbolic powers are unsupported");
      }
      return { coefficient: 0, constant: left.constant ** right.constant };
    }
  }
  throw new Error("Unsupported expression for solve_linear cloud subset");
}

function runCloudMathSympy(inputs) {
  const operation = trimmed(inputs.operation, "evaluate") || "evaluate";
  const warnings = ["cloud_native_math_subset"];
  const variables = cloudMathVariables(inputs.variables);
  try {
    if (operation === "evaluate") {
      const expression = trimmed(inputs.expression);
      if (!expression) {
        return cloudEngineRequired("math.sympy", "expression is required for math.sympy evaluate");
      }
      const simplified = simplifyMathAst(substituteMathAst(parseMathExpression(expression), variables));
      const remaining = Array.from(collectMathSymbols(simplified)).sort();
      if (remaining.length) {
        throw new Error(`evaluate requires numeric values for all variables; unresolved: ${remaining.join(", ")}`);
      }
      return cloudCompleted("math.sympy", {
        inputs,
        outputs: { operation, result: evaluateNumericMathAst(simplified) },
        evidence: { implementation: "cloud_native_subset", grammar: "arithmetic_v1" },
        warnings,
      });
    }
    if (operation === "substitute") {
      const expression = trimmed(inputs.expression);
      if (!expression) {
        return cloudEngineRequired("math.sympy", "expression is required for math.sympy substitute");
      }
      const simplified = simplifyMathAst(substituteMathAst(parseMathExpression(expression), variables));
      const remaining = Array.from(collectMathSymbols(simplified)).sort();
      const outputs = {
        operation,
        expression: formatMathAst(simplified),
        remaining_variables: remaining,
      };
      if (!remaining.length) {
        outputs.result = evaluateNumericMathAst(simplified);
      }
      return cloudCompleted("math.sympy", {
        inputs,
        outputs,
        evidence: { implementation: "cloud_native_subset", grammar: "arithmetic_v1" },
        warnings,
      });
    }
    if (operation === "simplify") {
      const expression = trimmed(inputs.expression);
      if (!expression) {
        return cloudEngineRequired("math.sympy", "expression is required for math.sympy simplify");
      }
      const simplified = simplifyMathAst(parseMathExpression(expression));
      return cloudCompleted("math.sympy", {
        inputs,
        outputs: { operation, result: formatMathAst(simplified) },
        evidence: { implementation: "cloud_native_subset", grammar: "arithmetic_v1" },
        warnings,
      });
    }
    if (operation === "solve_linear") {
      const equation = trimmed(inputs.equation);
      const variable = trimmed(inputs.variable, "x") || "x";
      if (!equation || !equation.includes("=")) {
        return cloudEngineRequired("math.sympy", "solve_linear requires an equation string containing '='");
      }
      const [lhsText, rhsText] = equation.split("=", 2).map((item) => item.trim());
      const lhs = linearMathForm(parseMathExpression(lhsText), variable, variables);
      const rhs = linearMathForm(parseMathExpression(rhsText), variable, variables);
      const coefficient = lhs.coefficient - rhs.coefficient;
      const constant = rhs.constant - lhs.constant;
      if (Math.abs(coefficient) <= 1e-12) {
        throw new Error("Equation is not solvable as a single-variable linear form");
      }
      return cloudCompleted("math.sympy", {
        inputs,
        outputs: { operation, variable, solution: constant / coefficient },
        evidence: { implementation: "cloud_native_subset", grammar: "arithmetic_v1" },
        warnings,
      });
    }
    return cloudEngineRequired(
      "math.sympy",
      `operation=${operation} requires a fuller symbolic engine than the cloud-native subset provides.`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unsupported expression";
    return cloudUnsupportedExpression("math.sympy", message, { operation });
  }
}

function gravityVector(primary, fallback) {
  const selected = primary !== undefined ? primary : fallback;
  if (typeof selected === "number" && Number.isFinite(selected)) {
    return { x: 0, y: -selected, z: 0 };
  }
  const vector = normalizeVector(selected, { x: 0, y: -9.81, z: 0 });
  if (vector.x === 0 && vector.y === 0 && vector.z === 0) {
    return { x: 0, y: -9.81, z: 0 };
  }
  return vector;
}

function findSceneObject(bundle, objectId) {
  if (!objectId) {
    return bundle.objects[0] || null;
  }
  return bundle.objects.find((item) => item.id === objectId) || null;
}

function axisVector(value) {
  const vector = normalizeVector(value, { x: 1, y: 0, z: 0 });
  const length = Math.sqrt((vector.x ** 2) + (vector.y ** 2) + (vector.z ** 2));
  if (length <= 1e-12) {
    return { x: 1, y: 0, z: 0 };
  }
  return {
    x: vector.x / length,
    y: vector.y / length,
    z: vector.z / length,
  };
}

function dot(a, b) {
  return (a.x * b.x) + (a.y * b.y) + (a.z * b.z);
}

function replaceAxisComponent(velocity, axis, scalar) {
  const currentScalar = dot(velocity, axis);
  const delta = scalar - currentScalar;
  return {
    x: velocity.x + (axis.x * delta),
    y: velocity.y + (axis.y * delta),
    z: velocity.z + (axis.z * delta),
  };
}

function runCloudProjectile(bundle, inputs) {
  const objectId = trimmed(inputs.object_id);
  const obj = findSceneObject(bundle, objectId);
  const initialPosition = normalizeVector(
    inputs.initial_position && typeof inputs.initial_position === "object" ? inputs.initial_position : obj?.position,
    { x: 0, y: 0, z: 0 },
  );
  const initialVelocity = normalizeVector(
    inputs.initial_velocity && typeof inputs.initial_velocity === "object" ? inputs.initial_velocity : obj?.data?.velocity,
    { x: 0, y: 0, z: 0 },
  );
  const gravity = gravityVector(inputs.gravity, bundle.scene.parameters.gravity);
  const duration = Math.max(numericValue(inputs.duration, 2), 0);
  const timeStep = Math.max(numericValue(inputs.time_step, 0.1), 0.01);
  const groundY = numericValue(inputs.ground_y, 0);
  const stopOnGround = inputs.stop_on_ground !== false;
  const trajectory = [];
  let maxHeight = initialPosition.y;
  for (let elapsed = 0; elapsed <= duration + 1e-9; elapsed += timeStep) {
    const position = {
      x: initialPosition.x + (initialVelocity.x * elapsed) + (0.5 * gravity.x * elapsed * elapsed),
      y: initialPosition.y + (initialVelocity.y * elapsed) + (0.5 * gravity.y * elapsed * elapsed),
      z: initialPosition.z + (initialVelocity.z * elapsed) + (0.5 * gravity.z * elapsed * elapsed),
    };
    const velocity = {
      x: initialVelocity.x + (gravity.x * elapsed),
      y: initialVelocity.y + (gravity.y * elapsed),
      z: initialVelocity.z + (gravity.z * elapsed),
    };
    trajectory.push({ time: Number(elapsed.toFixed(6)), position, velocity });
    maxHeight = Math.max(maxHeight, position.y);
    if (stopOnGround && elapsed > 0 && position.y <= groundY) {
      break;
    }
  }
  const finalSample = trajectory[trajectory.length - 1];
  return cloudCompleted("physics.simple_projectile", {
    inputs,
    outputs: {
      object_id: objectId,
      trajectory,
      final_position: finalSample.position,
      final_velocity: finalSample.velocity,
      max_height: maxHeight,
      duration_used: finalSample.time,
    },
    evidence: { equations: ["p = p0 + vt + 0.5at^2", "v = v0 + at"] },
  });
}

function runCloudCollision(bundle, inputs) {
  const objectIds = asStringArray(inputs.object_ids).slice(0, 2);
  if (objectIds.length !== 2) {
    return cloudEngineRequired("physics.simple_collision", "object_ids must contain exactly two scene object ids");
  }
  const objectA = findSceneObject(bundle, objectIds[0]);
  const objectB = findSceneObject(bundle, objectIds[1]);
  if (!objectA || !objectB) {
    return cloudEngineRequired("physics.simple_collision", "Both collision objects must exist in the scene before simulation.");
  }
  const axis = axisVector(inputs.axis);
  const massA = numericValue(inputs.mass_a, numericValue(objectA.data.mass, 1));
  const massB = numericValue(inputs.mass_b, numericValue(objectB.data.mass, 1));
  const restitution = Math.min(Math.max(numericValue(inputs.coefficient_of_restitution, 1), 0), 1);
  const velocityA = normalizeVector(inputs.velocity_a || objectA.data.velocity, { x: 0, y: 0, z: 0 });
  const velocityB = normalizeVector(inputs.velocity_b || objectB.data.velocity, { x: 0, y: 0, z: 0 });
  const scalarA = dot(velocityA, axis);
  const scalarB = dot(velocityB, axis);
  const postA = ((massA * scalarA) + (massB * scalarB) - (massB * restitution * (scalarA - scalarB))) / (massA + massB);
  const postB = ((massA * scalarA) + (massB * scalarB) + (massA * restitution * (scalarA - scalarB))) / (massA + massB);
  return cloudCompleted("physics.simple_collision", {
    inputs,
    outputs: {
      axis,
      pre_collision: {
        [objectA.id]: velocityA,
        [objectB.id]: velocityB,
      },
      post_collision: {
        [objectA.id]: replaceAxisComponent(velocityA, axis, postA),
        [objectB.id]: replaceAxisComponent(velocityB, axis, postB),
      },
      momentum: {
        before: (massA * scalarA) + (massB * scalarB),
        after: (massA * postA) + (massB * postB),
      },
    },
    evidence: { equations: ["conservation_of_momentum", "coefficient_of_restitution"] },
  });
}

function runCloudSceneAdapter(adapterId, bundle, inputs) {
  if (adapterId === "math.sympy") {
    return runCloudMathSympy(inputs);
  }
  if (adapterId === "physics.simple_projectile") {
    return runCloudProjectile(bundle, inputs);
  }
  if (adapterId === "physics.simple_collision") {
    return runCloudCollision(bundle, inputs);
  }
  return cloudEngineRequired(adapterId, "The requested Phase 1 adapter is not registered in cloud-native mode.");
}

function exportCloudScene(bundle, adapterId, includeSimulations) {
  if (adapterId !== "scene.three_json") {
    return cloudEngineRequired(adapterId, "This scene export adapter is unavailable in cloud-native mode.");
  }
  const snapshot = {
    metadata: {
      adapter_id: adapterId,
      type: "MysticLABScene",
      version: 1,
    },
    scene: {
      uuid: bundle.scene.scene_id,
      name: bundle.scene.title,
      type: "Scene",
      userData: {
        session_id: bundle.scene.session_id,
        domain: bundle.scene.domain,
        description: bundle.scene.description,
        parameters: bundle.scene.parameters,
        units: bundle.scene.units,
        attached_simulations: bundle.scene.attached_simulations,
        metadata: bundle.scene.metadata,
      },
    },
    objects: bundle.objects.map((item) => ({
      uuid: item.id,
      name: item.label,
      type: item.type,
      position: [item.position.x, item.position.y, item.position.z],
      rotation: [item.rotation.x, item.rotation.y, item.rotation.z],
      scale: [item.scale.x, item.scale.y, item.scale.z],
      geometry: item.geometry,
      material: item.material,
      userData: {
        data: item.data,
        metadata: item.metadata,
      },
    })),
  };
  if (includeSimulations) {
    snapshot.simulations = bundle.simulations.map((item) => ({
      simulation_id: item.simulation_id,
      adapter_id: item.adapter_id,
      status: item.status,
      attached_object_ids: item.attached_object_ids,
      outputs: item.outputs,
    }));
  }
  return cloudCompleted(adapterId, {
    inputs: { include_simulations: includeSimulations },
    outputs: { snapshot },
    evidence: { scene_id: bundle.scene.scene_id, object_count: bundle.objects.length },
  });
}

function renderCloudSceneReport(bundle) {
  const parameterLines = Object.entries(bundle.scene.parameters || {}).map(([key, value]) => `- ${key}: ${value}`);
  const objectLines = bundle.objects.map(
    (item) => `- ${item.label} (${item.type}) @ (${item.position.x.toFixed(3)}, ${item.position.y.toFixed(3)}, ${item.position.z.toFixed(3)})`,
  );
  const simulationLines = bundle.simulations.map((item) => `- ${item.simulation_id} [${item.adapter_id}] => ${item.status}`);
  const evidenceLines = bundle.scene.evidence_refs.length ? bundle.scene.evidence_refs.map((item) => `- ${item}`) : ["- None"];
  return [
    `# Mystic LAB Scene Report: ${bundle.scene.title}`,
    "",
    `Scene ID: ${bundle.scene.scene_id}`,
    `Session ID: ${bundle.scene.session_id}`,
    `Domain: ${bundle.scene.domain}`,
    "",
    "## Description",
    bundle.scene.description || "No description.",
    "",
    "## Parameters",
    ...(parameterLines.length ? parameterLines : ["- None"]),
    "",
    "## Objects",
    ...(objectLines.length ? objectLines : ["- None"]),
    "",
    "## Simulations",
    ...(simulationLines.length ? simulationLines : ["- None"]),
    "",
    "## Evidence Refs",
    ...evidenceLines,
    "",
  ].join("\n");
}

function applyCloudSimulationToScene(bundle, simulation, objectIds) {
  const selectedIds = objectIds && objectIds.length ? objectIds : simulation.attached_object_ids;
  if (simulation.adapter_id === "physics.simple_projectile") {
    const targetId = trimmed(simulation.outputs.object_id);
    const target = bundle.objects.find((item) => item.id === targetId && selectedIds.includes(item.id));
    if (!target) {
      return;
    }
    target.position = normalizeVector(simulation.outputs.final_position, { x: 0, y: 0, z: 0 });
    target.data = { ...target.data, velocity: normalizeVector(simulation.outputs.final_velocity, { x: 0, y: 0, z: 0 }), trajectory: simulation.outputs.trajectory || [] };
    target.metadata = { ...target.metadata, last_simulation_id: simulation.simulation_id };
    target.updated_at = nowIso();
    return;
  }
  if (simulation.adapter_id === "physics.simple_collision") {
    const postCollision = objectMapping(simulation.outputs.post_collision);
    bundle.objects = bundle.objects.map((item) => {
      if (!selectedIds.includes(item.id) || !postCollision[item.id] || typeof postCollision[item.id] !== "object") {
        return item;
      }
      return {
        ...item,
        data: { ...item.data, velocity: normalizeVector(postCollision[item.id], { x: 0, y: 0, z: 0 }) },
        metadata: { ...item.metadata, last_simulation_id: simulation.simulation_id },
        updated_at: nowIso(),
      };
    });
  }
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeImportVerificationKey(key) {
  return String(key || "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
}

function findSecretLikeImportPaths(data, prefix = "") {
  const matches = [];
  if (Array.isArray(data)) {
    data.forEach((item, index) => {
      matches.push(...findSecretLikeImportPaths(item, `${prefix}[${index}]`));
    });
    return matches;
  }
  if (!data || typeof data !== "object") {
    return matches;
  }
  for (const [key, value] of Object.entries(data)) {
    const currentPath = prefix ? `${prefix}.${key}` : String(key);
    if (IMPORT_VERIFICATION_FORBIDDEN_FIELD_NAMES.has(normalizeImportVerificationKey(key))) {
      matches.push(currentPath);
    }
    matches.push(...findSecretLikeImportPaths(value, currentPath));
  }
  return matches;
}

function summarizeImportVerificationPayload(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return {
      artifact_version: null,
      verified_at: "",
      verified_by: "",
      public_endpoint: "",
      mcp_endpoint: "",
      chatgpt_developer_mode_imported: false,
      oauth_flow_completed: false,
      tools_list_visible_in_chatgpt: false,
      required_tools_visible: [],
      manual_tool_call_results: {},
    };
  }
  const requiredToolsVisible = Array.isArray(data.required_tools_visible)
    ? data.required_tools_visible.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const manualToolCallResults = {};
  if (data.manual_tool_call_results && typeof data.manual_tool_call_results === "object" && !Array.isArray(data.manual_tool_call_results)) {
    for (const [key, value] of Object.entries(data.manual_tool_call_results)) {
      manualToolCallResults[String(key)] = String(value);
    }
  }
  return {
    artifact_version: data.artifact_version ?? null,
    verified_at: trimmed(data.verified_at),
    verified_by: trimmed(data.verified_by),
    public_endpoint: trimmed(data.public_endpoint),
    mcp_endpoint: trimmed(data.mcp_endpoint),
    chatgpt_developer_mode_imported: data.chatgpt_developer_mode_imported === true,
    oauth_flow_completed: data.oauth_flow_completed === true,
    tools_list_visible_in_chatgpt: data.tools_list_visible_in_chatgpt === true,
    required_tools_visible: requiredToolsVisible,
    manual_tool_call_results: manualToolCallResults,
  };
}

function validateImportVerificationPayload(data, publicEndpoint) {
  const errors = [];
  const warnings = [];
  const normalizedPublicEndpoint = String(publicEndpoint || "").replace(/\/+$/, "");
  const normalizedMcpEndpoint = `${normalizedPublicEndpoint}/mcp`;
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return {
      valid: false,
      verified: false,
      errors: ["artifact must be a JSON object"],
      warnings: [],
    };
  }
  if (findSecretLikeImportPaths(data).length) {
    errors.push("artifact contains forbidden secret-like field names");
  }
  if (data.artifact_version !== 1) {
    errors.push("artifact_version must be 1");
  }
  if (!trimmed(data.verified_at)) {
    errors.push("verified_at is required");
  }
  if (trimmed(data.verified_by) !== "manual") {
    errors.push("verified_by must be manual");
  }
  if (trimmed(data.public_endpoint).replace(/\/+$/, "") !== normalizedPublicEndpoint) {
    errors.push("public_endpoint does not match the checked public endpoint");
  }
  if (trimmed(data.mcp_endpoint).replace(/\/+$/, "") !== normalizedMcpEndpoint) {
    errors.push("mcp_endpoint must match the checked public endpoint /mcp path");
  }
  for (const key of ["chatgpt_developer_mode_imported", "oauth_flow_completed", "tools_list_visible_in_chatgpt"]) {
    if (data[key] !== true) {
      errors.push(`${key} must be true`);
    }
  }
  const visibleTools = Array.isArray(data.required_tools_visible)
    ? data.required_tools_visible.map((item) => String(item).trim()).filter(Boolean)
    : null;
  const visibleToolNames = new Set(visibleTools || []);
  if (!visibleTools) {
    errors.push("required_tools_visible must be a list");
  } else {
    const missingVisibleTools = IMPORT_VERIFICATION_REQUIRED_TOOLS.filter((tool) => !visibleToolNames.has(tool));
    if (missingVisibleTools.length) {
      errors.push(`required_tools_visible is missing: ${missingVisibleTools.join(", ")}`);
    }
  }
  const manualResults =
    data.manual_tool_call_results && typeof data.manual_tool_call_results === "object" && !Array.isArray(data.manual_tool_call_results)
      ? data.manual_tool_call_results
      : null;
  let manualToolCallsPassed = false;
  if (!manualResults) {
    errors.push("manual_tool_call_results must be an object");
  } else {
    const failedTools = IMPORT_VERIFICATION_REQUIRED_TOOLS.filter(
      (tool) => trimmed(manualResults[tool]).toLowerCase() !== "passed",
    );
    manualToolCallsPassed = failedTools.length === 0;
    if (failedTools.length) {
      errors.push(`manual_tool_call_results must mark passed for: ${failedTools.join(", ")}`);
    }
  }
  if (data.notes !== undefined && typeof data.notes !== "string") {
    warnings.push("notes should be a string when present");
  }
  const requiredToolsVisible =
    Array.isArray(visibleTools) && IMPORT_VERIFICATION_REQUIRED_TOOLS.every((tool) => visibleToolNames.has(tool));
  const valid = errors.length === 0;
  return {
    valid,
    verified: valid && requiredToolsVisible && manualToolCallsPassed,
    errors,
    warnings,
  };
}

function workerManualImportVerification(env, publicEndpoint) {
  const raw = trimmed(env[MANUAL_IMPORT_VERIFICATION_ENV]);
  const summary = {
    manual_import_verification_checked: false,
    manual_import_verified: false,
    manual_import_verification_path: MANUAL_IMPORT_VERIFICATION_PATH,
    manual_import_verification_summary: {},
  };
  if (!raw) {
    return summary;
  }
  summary.manual_import_verification_checked = true;
  summary.manual_import_verification_path = `env://${MANUAL_IMPORT_VERIFICATION_ENV}`;
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return summary;
  }
  const validation = validateImportVerificationPayload(payload, publicEndpoint);
  summary.manual_import_verified = validation.verified;
  if (validation.valid) {
    summary.manual_import_verification_summary = summarizeImportVerificationPayload(payload);
  }
  return summary;
}

function cloudId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function trimmed(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function firstNonEmpty(...values) {
  for (const value of values) {
    const text = trimmed(value);
    if (text) {
      return text;
    }
  }
  return "";
}

function requestTargetUrl(value) {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value.url === "string") {
    return value.url;
  }
  if (value instanceof URL) {
    return value.toString();
  }
  return "";
}

function asStringArray(value) {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function cloudNextPhase(currentPhase) {
  const index = LAB_PHASES.indexOf(currentPhase);
  if (index === -1 || index >= LAB_PHASES.length - 1) {
    return "completed";
  }
  return LAB_PHASES[index + 1];
}

function cloudNextActionsForPhase(phase) {
  if (phase === "completed") {
    return [];
  }
  const room = LAB_PHASE_TO_ROOM[phase] || "Main Lab Room";
  return [`Advance to ${phase} in ${room}.`, "Inspect newly saved artifacts, claims, and failures."];
}

function makeCloudTurn({
  sessionId,
  phase,
  agentRole,
  provider,
  modelName,
  inputSummary,
  output,
  status = "completed",
  requestedTools = [],
  toolResults = [],
  replyTo = [],
  error = "",
}) {
  return {
    session_id: sessionId,
    phase,
    room: LAB_PHASE_TO_ROOM[phase] || "Main Lab Room",
    agent_role: agentRole,
    provider,
    model_name: modelName,
    input_summary: inputSummary,
    output,
    extracted_claims: [],
    requested_tools: requestedTools,
    tool_results: toolResults,
    status,
    error,
    reply_to: replyTo,
    turn_id: cloudId("turn"),
    created_at: nowIso(),
  };
}

function extractCloudClaimPayloads(text, phase) {
  const claims = [];
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.replace(/^[-* \t]+/, "").trim();
    if (line.length < 18) {
      continue;
    }
    claims.push({
      text: line.slice(0, 400),
      claim_type: phase === "background_scan" ? "observation" : "hypothesis",
      status: phase === "knowledge_update" ? "TESTED" : "HEURISTIC",
      confidence: phase === "knowledge_update" ? "medium" : "low",
    });
    if (claims.length >= 5) {
      break;
    }
  }
  return claims;
}

function claimsFromTurn(sessionId, turn) {
  const payloads = extractCloudClaimPayloads(turn.output, turn.phase);
  turn.extracted_claims = payloads;
  return payloads.map((item) => ({
    session_id: sessionId,
    text: item.text,
    claim_type: item.claim_type,
    status: item.status,
    confidence: item.confidence,
    source_turn_id: turn.turn_id,
    supporting_evidence: [],
    refuting_evidence: [],
    related_experiments: [],
    related_failures: [],
    created_at: nowIso(),
    updated_at: nowIso(),
    claim_id: cloudId("claim"),
  }));
}

function makeFailure({
  sessionId,
  claimId = "",
  sourceTurnId = "",
  firstFatalError,
  failureType = "tool_error",
  lesson = "Cloud-native execution could not complete this step yet.",
  reusableAsTrainingData = false,
}) {
  return {
    session_id: sessionId,
    claim_id: claimId,
    source_turn_id: sourceTurnId,
    first_fatal_error: firstFatalError,
    failure_type: failureType,
    lesson,
    reusable_as_training_data: Boolean(reusableAsTrainingData),
    created_at: nowIso(),
    failure_id: cloudId("failure"),
  };
}

function makeMemoryEdge({ sessionId, fromId, toId, relation, evidence }) {
  return {
    session_id: sessionId,
    from_id: fromId,
    to_id: toId,
    relation,
    evidence,
    created_at: nowIso(),
    edge_id: cloudId("edge"),
  };
}

function findClaim(bundle, claimId) {
  return bundle.claims.find((item) => item.claim_id === claimId) || null;
}

function findExperiment(bundle, experimentId) {
  return bundle.experiments.find((item) => item.experiment_id === experimentId) || null;
}

function latestClaim(bundle) {
  return bundle.claims.length ? bundle.claims[bundle.claims.length - 1] : null;
}

function phaseContext(bundle, phase) {
  const parts = [
    `Current phase: ${phase}`,
    `Problem: ${bundle.session.problem}`,
    `Goal: ${bundle.session.goal}`,
    `Claims: ${bundle.claims.length}`,
    `Experiments: ${bundle.experiments.length}`,
    `Failures: ${bundle.failures.length}`,
  ];
  const claim = latestClaim(bundle);
  if (claim) {
    parts.push(`Latest claim: ${claim.text}`);
  }
  return parts.join("\n");
}

function contextFromIds(bundle, contextIds) {
  if (!Array.isArray(contextIds) || !contextIds.length) {
    return String(bundle.notebook_markdown || "").slice(-2000);
  }
  const parts = [];
  for (const turn of bundle.turns) {
    if (contextIds.includes(turn.turn_id)) {
      parts.push(turn.output);
    }
  }
  for (const claim of bundle.claims) {
    if (contextIds.includes(claim.claim_id)) {
      parts.push(claim.text);
    }
  }
  return parts.join("\n\n");
}

function providerSecret(env, names) {
  for (const name of names) {
    const value = String(env[name] || "").trim();
    if (value) {
      return value;
    }
  }
  return "";
}

function normalizeProviderId(value) {
  const normalized = trimmed(value).toLowerCase();
  if (normalized === "openai") {
    return "openai_compatible";
  }
  if (normalized === "google") {
    return "gemini";
  }
  if (["google-vertex-ai", "google_vertex", "vertex", "vertex_ai"].includes(normalized)) {
    return "google_vertex_ai";
  }
  if (normalized === "claude") {
    return "anthropic";
  }
  if (normalized === "custom" || normalized === "future" || normalized === "future/custom") {
    return "future_custom";
  }
  return normalized;
}

function providerRouteBaseUrl(env) {
  return trimmed(
    env.MYSTIC_PROVIDER_CONNECT_BASE_URL || env.MYSTIC_PUBLIC_BASE_URL || env.MYSTIC_PUBLIC_MCP_BASE_URL || env.MYSTIC_OAUTH_ISSUER,
    "https://mystic.dexproject.workers.dev",
  ).replace(/\/+$/, "");
}

function providerRouteUrls(env, providerId) {
  const baseUrl = providerRouteBaseUrl(env);
  return {
    providers_url: `${baseUrl}/providers`,
    connect_url: `${baseUrl}/providers/${providerId}/connect`,
    setup_url: `${baseUrl}/providers/${providerId}/setup`,
    status_url: `${baseUrl}/providers/${providerId}/status`,
    callback_url: `${baseUrl}/providers/oauth/callback?provider_id=${providerId}`,
  };
}

function providerCatalogEntry(env, providerId) {
  const normalized = normalizeProviderId(providerId);
  if (normalized === "openai_compatible") {
    return {
      provider_id: normalized,
      provider_type: "openai_compatible",
      default_auth_method: "api_key",
      supported_auth_methods: ["api_key", "oauth", "bearer_token"],
      supports_api_key: true,
      supports_oauth: true,
      secret_names: [
        "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY",
        "MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL",
        "MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL",
      ],
      required_secret_names: ["MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", "MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL"],
      optional_secret_names: ["MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL"],
      model_env_names: ["MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL"],
      external_setup_url: trimmed(env.MYSTIC_PROVIDER_OPENAI_COMPAT_SETUP_URL, "https://platform.openai.com/api-keys"),
      setup_instructions:
        "Set Cloudflare secret MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY, set MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL, and optionally set MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL.",
      scopes: ["model:generate"],
      default_models: ["openai-compatible"],
      oauth_env_prefix: "MYSTIC_PROVIDER_OPENAI_COMPAT",
      oauth_default_scopes: [],
    };
  }
  if (normalized === "gemini") {
    return {
      provider_id: normalized,
      provider_type: "gemini",
      default_auth_method: "api_key",
      supported_auth_methods: ["api_key"],
      supports_api_key: true,
      supports_oauth: false,
      secret_names: ["MYSTIC_PROVIDER_GEMINI_API_KEY", "MYSTIC_PROVIDER_GEMINI_MODEL"],
      required_secret_names: ["MYSTIC_PROVIDER_GEMINI_API_KEY"],
      optional_secret_names: ["MYSTIC_PROVIDER_GEMINI_MODEL"],
      model_env_names: ["MYSTIC_PROVIDER_GEMINI_MODEL"],
      external_setup_url: trimmed(env.MYSTIC_PROVIDER_GEMINI_SETUP_URL, "https://aistudio.google.com/app/apikey"),
      setup_instructions:
        "Set Cloudflare secret MYSTIC_PROVIDER_GEMINI_API_KEY and optionally set MYSTIC_PROVIDER_GEMINI_MODEL.",
      scopes: ["model:generate"],
      default_models: ["gemini-1.5-flash"],
    };
  }
  if (normalized === "google_vertex_ai") {
    return {
      provider_id: normalized,
      provider_type: "google_vertex_ai",
      default_auth_method: "oauth",
      supported_auth_methods: ["oauth"],
      supports_api_key: false,
      supports_oauth: true,
      secret_names: [
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL",
      ],
      required_secret_names: [
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
      ],
      optional_secret_names: ["MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL"],
      model_env_names: ["MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL"],
      external_setup_url: trimmed(
        env.MYSTIC_PROVIDER_GOOGLE_VERTEX_SETUP_URL,
        "https://console.cloud.google.com/apis/credentials",
      ),
      setup_instructions:
        "Set Cloudflare secrets MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID, MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET, MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID, MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION, and optionally MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL for Google OAuth-backed Vertex AI Gemini access.",
      scopes: ["model:generate"],
      default_models: ["gemini-2.5-flash"],
      oauth_env_prefix: "MYSTIC_PROVIDER_GOOGLE_VERTEX",
      oauth_default_scopes: [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/cloud-platform",
      ],
      oauth_default_authorization_endpoint: "https://accounts.google.com/o/oauth2/v2/auth",
      oauth_default_token_endpoint: "https://oauth2.googleapis.com/token",
      oauth_missing_status: "provider_required",
      oauth_require_client_secret: true,
      oauth_required_config_env_names: [
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
        "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
      ],
      oauth_token_storage_supported: false,
    };
  }
  if (normalized === "anthropic") {
    return {
      provider_id: normalized,
      provider_type: "anthropic",
      default_auth_method: "api_key",
      supported_auth_methods: ["api_key", "oauth", "bearer_token"],
      supports_api_key: true,
      supports_oauth: true,
      secret_names: ["MYSTIC_PROVIDER_ANTHROPIC_API_KEY", "MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
      required_secret_names: ["MYSTIC_PROVIDER_ANTHROPIC_API_KEY"],
      optional_secret_names: ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
      model_env_names: ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
      external_setup_url: trimmed(env.MYSTIC_PROVIDER_ANTHROPIC_SETUP_URL, "https://console.anthropic.com/settings/keys"),
      setup_instructions:
        "Set Cloudflare secret MYSTIC_PROVIDER_ANTHROPIC_API_KEY and optionally set MYSTIC_PROVIDER_ANTHROPIC_MODEL.",
      scopes: ["model:generate"],
      default_models: ["claude-3-5-sonnet-latest"],
      oauth_env_prefix: "MYSTIC_PROVIDER_ANTHROPIC",
      oauth_default_scopes: [],
    };
  }
  if (normalized === "mock") {
    return {
      provider_id: "mock",
      provider_type: "future/custom",
      default_auth_method: "none/mock",
      supported_auth_methods: ["none/mock"],
      supports_api_key: false,
      supports_oauth: false,
      secret_names: [],
      required_secret_names: [],
      optional_secret_names: [],
      model_env_names: [],
      external_setup_url: "",
      setup_instructions: "Mock provider is test-only and must not be used for production routing.",
      scopes: ["model:generate"],
      default_models: ["mock-model"],
      test_only: true,
    };
  }
  return {
    provider_id: "future_custom",
    provider_type: "future/custom",
    default_auth_method: "oauth",
    supported_auth_methods: ["api_key", "oauth", "bearer_token"],
    supports_api_key: false,
    supports_oauth: true,
    secret_names: [],
    required_secret_names: [],
    optional_secret_names: [],
    model_env_names: [],
    external_setup_url: "",
    setup_instructions:
      "Configure OAuth metadata for the future custom provider, then use provider_connect_start to generate a real authorization URL.",
    scopes: ["model:generate"],
    default_models: [],
    oauth_env_prefix: "MYSTIC_PROVIDER_FUTURE_CUSTOM",
    oauth_default_scopes: [],
  };
}

function providerSecretState(env, spec) {
  const configuredSecretNames = spec.secret_names.filter((name) => trimmed(env[name]));
  const missingSecretNames = spec.secret_names.filter((name) => !configuredSecretNames.includes(name));
  const missingRequiredSecretNames = spec.required_secret_names.filter((name) => !configuredSecretNames.includes(name));
  return {
    configured_secret_names: configuredSecretNames,
    missing_secret_names: missingSecretNames,
    missing_required_secret_names: missingRequiredSecretNames,
  };
}

function providerManualSecretInstructions(spec) {
  const instructions = [
    "Do not store provider secrets in Supabase.",
    "Store production provider secrets only in Cloudflare Worker secret storage or approved server-side secret storage.",
    "Do not paste API keys into tool output or chat transcripts.",
  ];
  for (const name of spec.required_secret_names) {
    instructions.push(`wrangler secret put ${name} --name mystic`);
  }
  for (const name of spec.optional_secret_names) {
    instructions.push(`Set optional provider variable or secret ${name} if needed.`);
  }
  return instructions;
}

function providerOauthMetadata(env, spec) {
  const prefix = spec.oauth_env_prefix || "";
  if (!prefix) {
    return {
      available: false,
      configured: false,
      enabled: false,
      authorization_endpoint: "",
      token_endpoint: "",
      client_id: "",
      redirect_uri: "",
      scopes: [],
      client_id_configured: false,
      client_secret_configured: false,
      required_config_names: [],
      missing_config_names: [],
      token_storage_supported: false,
    };
  }
  const enabled = ["1", "true", "yes", "on"].includes(trimmed(env[`${prefix}_OAUTH_ENABLED`]).toLowerCase());
  const authorizationEndpoint = trimmed(
    env[`${prefix}_AUTHORIZATION_ENDPOINT`],
    spec.oauth_default_authorization_endpoint || "",
  );
  const tokenEndpoint = trimmed(env[`${prefix}_TOKEN_ENDPOINT`], spec.oauth_default_token_endpoint || "");
  const clientId = trimmed(env[`${prefix}_CLIENT_ID`]);
  const clientSecret = trimmed(env[`${prefix}_CLIENT_SECRET`]);
  const redirectUri = trimmed(
    env[`${prefix}_REDIRECT_URI`],
    `${providerRouteBaseUrl(env)}/providers/oauth/callback?provider_id=${spec.provider_id}`,
  );
  const scopes = trimmed(env[`${prefix}_SCOPES`])
    ? trimmed(env[`${prefix}_SCOPES`])
        .split(/\s+/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [...(spec.oauth_default_scopes || [])];
  const requiredConfigNames = Array.isArray(spec.oauth_required_config_env_names)
    ? [...spec.oauth_required_config_env_names]
    : [];
  const missingConfigNames = requiredConfigNames.filter((name) => !trimmed(env[name]));
  const clientSecretConfigured = Boolean(clientSecret) || !Boolean(spec.oauth_require_client_secret);
  const available = Boolean(spec.supports_oauth);
  const tokenStorageSupported = Boolean(trimmed(env.MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY));
  return {
    available,
    configured: Boolean(
      available &&
        enabled &&
        authorizationEndpoint &&
        tokenEndpoint &&
        clientId &&
        redirectUri &&
        clientSecretConfigured &&
        missingConfigNames.length === 0,
    ),
    enabled,
    authorization_endpoint: authorizationEndpoint,
    token_endpoint: tokenEndpoint,
    client_id: clientId,
    redirect_uri: redirectUri,
    scopes,
    client_id_configured: Boolean(clientId),
    client_secret_configured: clientSecretConfigured,
    required_config_names: requiredConfigNames,
    missing_config_names: missingConfigNames,
    token_storage_supported: tokenStorageSupported,
  };
}

function providerModelList(env, spec, row = {}) {
  if (Array.isArray(row.model_list) && row.model_list.length) {
    return row.model_list.map((item) => String(item)).filter(Boolean);
  }
  const envModels = spec.model_env_names.map((name) => trimmed(env[name])).filter(Boolean);
  if (envModels.length) {
    return envModels;
  }
  return [...spec.default_models];
}

function providerDefaultFailureReason(spec, status, oauthMetadata, secretState) {
  if (status === "connected") {
    return "";
  }
  if (status === "oauth_callback_received") {
    return "oauth_callback_received";
  }
  if (status === "token_storage_required") {
    return "token_storage_required";
  }
  if (status === "provider_required") {
    return "oauth_metadata_missing";
  }
  if (status === "oauth_required" && !oauthMetadata.configured) {
    return "oauth_metadata_missing";
  }
  if (status === "api_key_required" && secretState.missing_required_secret_names.length) {
    return "missing_required_secrets";
  }
  if (status === "not_configured" && spec.supports_api_key) {
    return "provider_not_configured";
  }
  return "";
}

function resolveProviderStatus(spec, row, secretState, oauthMetadata) {
  const storedStatus = trimmed(row.status);
  if (["provider_required", "disconnected", "token_storage_required", "oauth_callback_received", "auth_failed", "rate_limited", "provider_unavailable"].includes(storedStatus)) {
    return storedStatus;
  }
  const authMethod = trimmed(row.auth_method, spec.default_auth_method);
  if (spec.test_only) {
    return "connected";
  }
  if (authMethod === "oauth") {
    if (storedStatus === "connected" && (spec.provider_id !== "google_vertex_ai" || Boolean(row.metadata && row.metadata.oauth_token_recorded))) {
      return "connected";
    }
    if (spec.oauth_missing_status === "provider_required" && (secretState.missing_required_secret_names.length || oauthMetadata.missing_config_names.length)) {
      return "provider_required";
    }
    if (oauthMetadata.configured) {
      return "oauth_required";
    }
    if (spec.supports_api_key) {
      return "api_key_required";
    }
    return spec.oauth_missing_status || "not_configured";
  }
  if (spec.required_secret_names.length && secretState.missing_required_secret_names.length === 0) {
    return "connected";
  }
  if (authMethod === "bearer_token") {
    if (storedStatus === "connected") {
      return "connected";
    }
    if (oauthMetadata.configured) {
      return "oauth_required";
    }
    if (spec.supports_api_key) {
      return "api_key_required";
    }
    return spec.oauth_missing_status || "not_configured";
  }
  if (!storedStatus && secretState.configured_secret_names.length === 0) {
    return "not_configured";
  }
  return "api_key_required";
}

function buildProviderRecord(env, providerId, row = {}) {
  const spec = providerCatalogEntry(env, providerId);
  const secretState = providerSecretState(env, spec);
  const oauthMetadata = providerOauthMetadata(env, spec);
  const routeUrls = providerRouteUrls(env, spec.provider_id);
  const modelList = providerModelList(env, spec, row);
  const authMethod = trimmed(row.auth_method, spec.default_auth_method);
  const status = resolveProviderStatus(spec, row, secretState, oauthMetadata);
  const metadata = row.metadata && typeof row.metadata === "object" && !Array.isArray(row.metadata) ? row.metadata : {};
  metadata.oauth_client_id_configured = metadata.oauth_client_id_configured ?? oauthMetadata.client_id_configured;
  metadata.oauth_client_secret_configured =
    metadata.oauth_client_secret_configured ?? oauthMetadata.client_secret_configured;
  metadata.oauth_missing_config_names = metadata.oauth_missing_config_names ?? oauthMetadata.missing_config_names;
  metadata.oauth_token_storage_supported =
    metadata.oauth_token_storage_supported ?? oauthMetadata.token_storage_supported;
  return {
    connection_id: trimmed(row.connection_id, `provider-${spec.provider_id}`),
    provider_id: spec.provider_id,
    provider_type: trimmed(row.provider_type, spec.provider_type),
    auth_method: authMethod,
    auth_mode: oauthMetadata.configured ? "oauth" : spec.supports_api_key ? "api_key" : authMethod,
    status,
    provider_status: status,
    scopes: Array.isArray(row.scopes) ? row.scopes.map((item) => String(item)) : [...spec.scopes],
    model_list: modelList,
    model_name: modelList[0] || spec.provider_id,
    setup_url: routeUrls.setup_url,
    connect_url: routeUrls.connect_url,
    status_url: routeUrls.status_url,
    external_setup_url: trimmed(metadata.external_setup_url, spec.external_setup_url || ""),
    setup_instructions: trimmed(row.setup_instructions, spec.setup_instructions),
    last_verified_at: trimmed(row.last_verified_at),
    failure_reason: trimmed(row.failure_reason, providerDefaultFailureReason(spec, status, oauthMetadata, secretState)),
    metadata: metadata,
    created_at: trimmed(row.created_at),
    updated_at: trimmed(row.updated_at),
    configured_secret_names: secretState.configured_secret_names,
    missing_secret_names: secretState.missing_secret_names,
    required_secret_names: [...spec.required_secret_names],
    missing_required_secret_names: secretState.missing_required_secret_names,
    configured: status === "connected",
    oauth_supported: oauthMetadata.available,
    oauth_configured: oauthMetadata.configured,
    oauth_authorization_endpoint: oauthMetadata.authorization_endpoint,
    ready: status === "connected",
  };
}

function providerStatusMessage(record) {
  const status = trimmed(record.provider_status || record.status);
  if (status === "connected") {
    return "Provider is connected.";
  }
  if (status === "oauth_required") {
    return "Provider OAuth connection is required. Start the secure OAuth flow and retry.";
  }
  if (status === "oauth_callback_received") {
    return "OAuth callback was received. Mystic LAB is finalizing secure token storage.";
  }
  if (status === "token_storage_required") {
    return "Encrypted server-side token storage is required before OAuth-backed provider access can be completed.";
  }
  if (status === "api_key_required") {
    return "Provider credentials are not configured. Complete the secure setup flow and retry.";
  }
  if (status === "provider_required") {
    return "Provider configuration is incomplete. Add the required OAuth metadata and retry.";
  }
  if (status === "auth_failed") {
    return "Provider authentication failed. Reconnect the provider and retry.";
  }
  if (status === "rate_limited") {
    return "Provider rate limited the last request. Retry later.";
  }
  if (status === "provider_unavailable") {
    return "Provider is temporarily unavailable. Retry later.";
  }
  if (status === "disconnected") {
    return "Provider is disconnected until an explicit reconnect.";
  }
  return "Provider configuration was checked without exposing secrets.";
}

function defaultProviderRegistry(env) {
  return PUBLIC_PROVIDER_IDS.map((providerId) => buildProviderRecord(env, providerId));
}

async function loadProviderRegistry(env) {
  const fallback = defaultProviderRegistry(env);
  const providerMap = new Map(fallback.map((item) => [item.provider_id, item]));
  const warnings = [];
  if (!supabaseState(env).configured) {
    return { providers: fallback, warnings };
  }
  try {
    const [rows, tokenRows] = await Promise.all([
      supabaseSelectRows(env, "provider_connections", {}, { order: "created_at.asc" }),
      supabaseSelectRows(env, "provider_oauth_tokens", {}, { order: "updated_at.asc" }),
    ]);
    const tokenMap = new Map(tokenRows.map((row) => [normalizeProviderId(row.provider_id), row]));
    for (const row of rows) {
      const providerId = normalizeProviderId(row.provider_id);
      if (!providerId) {
        continue;
      }
      const tokenRow = tokenMap.get(providerId);
      const mergedMetadata = {
        ...(row.metadata && typeof row.metadata === "object" ? row.metadata : {}),
      };
      if (tokenRow) {
        mergedMetadata.oauth_token_recorded = true;
        mergedMetadata.oauth_token_status = trimmed(tokenRow.status);
        mergedMetadata.oauth_token_metadata_safe =
          tokenRow.metadata_safe && typeof tokenRow.metadata_safe === "object" ? tokenRow.metadata_safe : {};
      }
      providerMap.set(providerId, buildProviderRecord(env, providerId, { ...row, metadata: mergedMetadata }));
    }
  } catch (error) {
    warnings.push(`provider_registry_unavailable:${String(error.message || error).slice(0, 120)}`);
  }
  return { providers: Array.from(providerMap.values()), warnings };
}

async function upsertProviderConnection(env, providerRecord, extra = {}) {
  const spec = providerCatalogEntry(env, providerRecord.provider_id);
  const routeUrls = providerRouteUrls(env, providerRecord.provider_id);
  const row = {
    connection_id: providerRecord.connection_id || `provider-${providerRecord.provider_id}`,
    provider_id: providerRecord.provider_id,
    provider_type: providerRecord.provider_type,
    auth_method: providerRecord.auth_method,
    status: providerRecord.status,
    scopes: Array.isArray(providerRecord.scopes) ? providerRecord.scopes : [],
    model_list: Array.isArray(providerRecord.model_list) ? providerRecord.model_list : [],
    setup_url: providerRecord.setup_url || routeUrls.setup_url,
    setup_instructions: providerRecord.setup_instructions || spec.setup_instructions,
    last_verified_at: providerRecord.last_verified_at || null,
    failure_reason: providerRecord.failure_reason || "",
    metadata: {
      connect_url: routeUrls.connect_url,
      status_url: routeUrls.status_url,
      external_setup_url: spec.external_setup_url || "",
      ...(providerRecord.metadata && typeof providerRecord.metadata === "object" ? providerRecord.metadata : {}),
    },
    created_at: providerRecord.created_at || nowIso(),
    updated_at: nowIso(),
    ...extra,
  };
  await supabaseUpsertRows(env, "provider_connections", [row], "connection_id");
  return row;
}

async function upsertProviderAuthFlow(env, flow) {
  const row = {
    flow_id: flow.flow_id,
    provider_id: flow.provider_id,
    auth_method: flow.auth_method,
    status: flow.status,
    authorization_url: flow.authorization_url || "",
    redirect_url: flow.redirect_url || "",
    state: flow.state || "",
    state_hash: flow.state_hash || "",
    code_challenge: flow.code_challenge || "",
    code_challenge_method: flow.code_challenge_method || "",
    callback_received_at: flow.callback_received_at || null,
    failure_reason: flow.failure_reason || "",
    metadata: flow.metadata && typeof flow.metadata === "object" ? flow.metadata : {},
    created_at: flow.created_at || nowIso(),
    updated_at: nowIso(),
  };
  await supabaseUpsertRows(env, "provider_auth_flows", [row], "flow_id");
  return row;
}

async function loadProviderAuthFlow(env, flowId) {
  return supabaseSelectOne(env, "provider_auth_flows", { flow_id: `eq.${flowId}` });
}

async function upsertProviderOauthToken(env, tokenRow) {
  const row = {
    token_id: trimmed(tokenRow.token_id),
    provider_id: normalizeProviderId(tokenRow.provider_id),
    connection_id: trimmed(tokenRow.connection_id),
    encrypted_access_token: trimmed(tokenRow.encrypted_access_token),
    encrypted_refresh_token: trimmed(tokenRow.encrypted_refresh_token),
    encrypted_id_token: trimmed(tokenRow.encrypted_id_token),
    token_type: trimmed(tokenRow.token_type),
    scope_hash: trimmed(tokenRow.scope_hash),
    expires_at: tokenRow.expires_at || null,
    status: trimmed(tokenRow.status, "connected"),
    metadata_safe:
      tokenRow.metadata_safe && typeof tokenRow.metadata_safe === "object" && !Array.isArray(tokenRow.metadata_safe)
        ? tokenRow.metadata_safe
        : {},
    created_at: tokenRow.created_at || nowIso(),
    updated_at: nowIso(),
  };
  await supabaseUpsertRows(env, "provider_oauth_tokens", [row], "token_id");
  return row;
}

async function loadProviderOauthToken(env, providerId) {
  return supabaseSelectOne(env, "provider_oauth_tokens", { provider_id: `eq.${normalizeProviderId(providerId)}` });
}

function publicProviderFlow(flow = {}) {
  return {
    flow_id: trimmed(flow.flow_id),
    provider_id: normalizeProviderId(flow.provider_id),
    auth_method: trimmed(flow.auth_method),
    status: trimmed(flow.status),
    authorization_url: trimmed(flow.authorization_url),
    redirect_url: trimmed(flow.redirect_url),
    state_hash: trimmed(flow.state_hash),
    code_challenge_method: trimmed(flow.code_challenge_method),
    callback_received_at: flow.callback_received_at || null,
    failure_reason: trimmed(flow.failure_reason),
    metadata:
      flow.metadata && typeof flow.metadata === "object" && !Array.isArray(flow.metadata)
        ? safeProviderMetadata(flow.metadata)
        : {},
    created_at: flow.created_at || "",
    updated_at: flow.updated_at || "",
  };
}

function base64UrlEncode(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value) {
  const normalized = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function tokenEncryptionKeyBytes(env) {
  const raw = trimmed(env.MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY);
  if (!raw) {
    throw new Error("MYSTIC_PROVIDER_TOKEN_ENCRYPTION_KEY is required");
  }
  try {
    const decoded = base64UrlDecode(raw);
    if (decoded.length >= 32) {
      return decoded.slice(0, 32);
    }
  } catch (_) {}
  const digest = await crypto.subtle.digest("SHA-256", textEncoder.encode(raw));
  return new Uint8Array(digest);
}

function concatUint8Arrays(parts) {
  const totalLength = parts.reduce((sum, part) => sum + part.length, 0);
  const combined = new Uint8Array(totalLength);
  let offset = 0;
  for (const part of parts) {
    combined.set(part, offset);
    offset += part.length;
  }
  return combined;
}

async function encryptProviderTokenValue(env, value) {
  const key = await tokenEncryptionKeyBytes(env);
  const nonce = new Uint8Array(16);
  crypto.getRandomValues(nonce);
  const plaintext = textEncoder.encode(String(value || ""));
  const encrypted = new Uint8Array(plaintext.length);
  let offset = 0;
  let counter = 0;
  while (offset < plaintext.length) {
    const counterBytes = new Uint8Array(4);
    new DataView(counterBytes.buffer).setUint32(0, counter);
    const digest = await crypto.subtle.digest("SHA-256", concatUint8Arrays([key, nonce, counterBytes]));
    const block = new Uint8Array(digest);
    for (let index = 0; index < block.length && offset < plaintext.length; index += 1) {
      encrypted[offset] = plaintext[offset] ^ block[index];
      offset += 1;
    }
    counter += 1;
  }
  const payload = concatUint8Arrays([textEncoder.encode("mlabtok_v1"), nonce, encrypted]);
  const hmacKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const tag = new Uint8Array(await crypto.subtle.sign("HMAC", hmacKey, payload));
  return `mlabtok_v1:${base64UrlEncode(nonce)}:${base64UrlEncode(encrypted)}:${base64UrlEncode(tag)}`;
}

async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", textEncoder.encode(String(value)));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function buildPkcePair() {
  const verifierBytes = new Uint8Array(32);
  crypto.getRandomValues(verifierBytes);
  const verifier = base64UrlEncode(verifierBytes);
  const challengeDigest = await crypto.subtle.digest("SHA-256", textEncoder.encode(verifier));
  const challenge = base64UrlEncode(new Uint8Array(challengeDigest));
  return { verifier, challenge };
}

function buildProviderAuthorizationUrl(env, spec, oauthMetadata, { flowId, stateValue, codeChallenge }) {
  const params = new URLSearchParams();
  params.set("response_type", "code");
  params.set("client_id", oauthMetadata.client_id);
  params.set("redirect_uri", oauthMetadata.redirect_uri);
  params.set("state", stateValue);
  params.set("flow_id", flowId);
  if (oauthMetadata.scopes.length) {
    params.set("scope", oauthMetadata.scopes.join(" "));
  }
  if (codeChallenge) {
    params.set("code_challenge", codeChallenge);
    params.set("code_challenge_method", "S256");
  }
  if (spec.provider_id === "google_vertex_ai") {
    params.set("access_type", "offline");
    params.set("prompt", "consent");
  }
  return `${oauthMetadata.authorization_endpoint}?${params.toString()}`;
}

function providerRegistryMap(registry) {
  return new Map(registry.providers.map((item) => [item.provider_id, item]));
}

function normalizeRequestedProvider(value) {
  const normalized = normalizeProviderId(trimmed(value, "auto"));
  if (normalized === "local") {
    return "local_backend";
  }
  return normalized;
}

function parseProviderParticipantAlias(value) {
  const raw = trimmed(value);
  if (raw.includes(":")) {
    const [providerId, model] = raw.split(":", 2);
    return { provider_id: normalizeRequestedProvider(providerId), model: trimmed(model) };
  }
  return { provider_id: normalizeRequestedProvider(raw), model: "" };
}

function localBackendDeferredResult() {
  return {
    status: "deferred",
    deferred: true,
    provider_required: false,
    provider: "local_backend",
    required_auth_method: "local_process",
    setup_url: "",
    setup_instructions: "Cloud-native mode does not use the local Mystic backend or a quick tunnel.",
    message: "This cloud-native LAB action cannot fall back to the local backend in public Worker mode.",
    supported_in_cloud_mode: false,
  };
}

function providerRequiredResult(providerRecord, message) {
  return {
    status: "provider_required",
    deferred: false,
    provider_required: true,
    provider: providerRecord.provider_id,
    provider_type: providerRecord.provider_type,
    required_auth_method: providerRecord.auth_method,
    setup_url: providerRecord.setup_url,
    setup_instructions: providerRecord.setup_instructions,
    scopes: providerRecord.scopes,
    created_at: providerRecord.created_at,
    message,
    supported_in_cloud_mode: true,
  };
}

function deferredResult(message, extra = {}) {
  return {
    status: "deferred",
    deferred: true,
    provider_required: false,
    supported_in_cloud_mode: false,
    message,
    ...extra,
  };
}

function providerCallStatusFromRecord(providerRecord) {
  if (providerRecord.ready) {
    return "connected";
  }
  if (providerRecord.status === "oauth_required") {
    return "oauth_required";
  }
  if (providerRecord.status === "oauth_callback_received") {
    return "provider_required";
  }
  if (providerRecord.status === "token_storage_required") {
    return "provider_required";
  }
  if (providerRecord.status === "not_configured") {
    return "api_key_required";
  }
  if (providerRecord.status === "api_key_required") {
    return "api_key_required";
  }
  if (providerRecord.status === "auth_failed") {
    return "provider_auth_failed";
  }
  if (providerRecord.status === "rate_limited") {
    return "rate_limited";
  }
  if (providerRecord.status === "provider_unavailable") {
    return "provider_unavailable";
  }
  return "provider_required";
}

function providerCallErrorMessage(providerRecord, status) {
  if (status === "oauth_required") {
    return "Provider OAuth connection is required. Start the secure OAuth flow and retry.";
  }
  if (providerRecord.status === "oauth_callback_received") {
    return "OAuth callback was received. Mystic LAB is finalizing secure token storage.";
  }
  if (providerRecord.status === "token_storage_required") {
    return "Encrypted server-side token storage is required before OAuth-backed provider access can be completed.";
  }
  if (status === "api_key_required") {
    return "Provider credentials are not configured. Complete the secure setup flow and retry.";
  }
  if (status === "provider_auth_failed") {
    return "Provider authentication failed. Verify credentials and retry.";
  }
  if (status === "rate_limited") {
    return "Provider rate limit reached. Retry later.";
  }
  if (status === "provider_unavailable") {
    return "Provider is temporarily unavailable. Retry later.";
  }
  return providerRecord.setup_instructions || "Provider must be connected before this call can run.";
}

function safeProviderMetadata(value) {
  if (Array.isArray(value)) {
    return value.slice(0, 12).map((item) => safeProviderMetadata(item));
  }
  if (value && typeof value === "object") {
    const sanitized = {};
    for (const [key, item] of Object.entries(value)) {
      const lowered = String(key).toLowerCase();
      if (
        IMPORT_VERIFICATION_FORBIDDEN_FIELD_NAMES.has(lowered) ||
        lowered.includes("secret") ||
        lowered.includes("token") ||
        lowered === "code_verifier" ||
        lowered === "state"
      ) {
        continue;
      }
      sanitized[key] = safeProviderMetadata(item);
    }
    return sanitized;
  }
  if (typeof value === "string") {
    return value.slice(0, 500);
  }
  return value;
}

async function providerPromptHash(messages) {
  return sha256Hex(JSON.stringify(messages || []));
}

function providerPromptExcerpt(messages, limit = 240) {
  const raw = (Array.isArray(messages) ? messages : [])
    .map((item) => `${trimmed(item.role)}:${trimmed(item.content)}`)
    .filter(Boolean)
    .join(" | ");
  return raw.replace(/\s+/g, " ").trim().slice(0, limit);
}

function providerMessageList({ prompt, systemPrompt, messages }) {
  if (Array.isArray(messages) && messages.length) {
    return messages
      .map((item) => ({ role: trimmed(item.role), content: trimmed(item.content) }))
      .filter((item) => item.role && item.content);
  }
  const normalized = [];
  if (trimmed(systemPrompt)) {
    normalized.push({ role: "system", content: trimmed(systemPrompt) });
  }
  normalized.push({ role: "user", content: trimmed(prompt, "ping") });
  return normalized;
}

function providerUserPrompt(messages) {
  const userParts = (Array.isArray(messages) ? messages : [])
    .filter((item) => item && item.role === "user" && trimmed(item.content))
    .map((item) => trimmed(item.content));
  if (userParts.length) {
    return userParts.join("\n\n");
  }
  return (Array.isArray(messages) ? messages : [])
    .map((item) => trimmed(item?.content))
    .filter(Boolean)
    .join("\n\n");
}

function safeUsagePayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {};
  }
  const safe = {};
  for (const [key, value] of Object.entries(payload)) {
    if (["string", "number", "boolean"].includes(typeof value) || value === null) {
      safe[key] = value;
    }
  }
  return safe;
}

async function saveCloudModelCall(env, record) {
  await supabaseUpsertRows(env, "model_calls", [record], "call_id");
  return `supabase://${supabaseState(env).schema}/model_calls/${record.call_id}`;
}

function selectCloudProvider(env, registry, requestedProvider) {
  const normalized = normalizeRequestedProvider(requestedProvider);
  if (normalized === "local_backend") {
    return { selection: null, deferred: localBackendDeferredResult() };
  }
  const providerMap = providerRegistryMap(registry);
  if (normalized && normalized !== "auto") {
    const selected = providerMap.get(normalized) || (normalized === "mock" ? buildProviderRecord(env, "mock") : null);
    if (!selected) {
      return { selection: null, deferred: deferredResult(`Unknown provider: ${requestedProvider}`) };
    }
    if (!selected.ready) {
      return {
        selection: null,
        providerRequired: providerRequiredResult(selected, `${selected.provider_id} must be explicitly connected before this LAB action can run.`),
      };
    }
    return { selection: selected };
  }
  const ready = registry.providers.find((item) => item.ready);
  if (ready) {
    return { selection: ready };
  }
  const preferred = registry.providers[0];
  return {
    selection: null,
    providerRequired: providerRequiredResult(
      preferred,
      "No cloud-native model provider is connected. Configure an external provider secret before running this LAB action.",
    ),
  };
}

async function providerRequestJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { raw: text };
  }
  if (!response.ok) {
    let errorType = "provider_error";
    if ([401, 403].includes(response.status)) {
      errorType = "provider_auth_failed";
    } else if (response.status === 429) {
      errorType = "rate_limited";
    } else if ([408, 500, 502, 503, 504].includes(response.status)) {
      errorType = "provider_unavailable";
    }
    throw { error_type: errorType, safe_message: `Provider request failed with HTTP ${response.status}.`, status_code: response.status };
  }
  return payload;
}

function normalizeTextOutput(value) {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item : typeof item?.text === "string" ? item.text : ""))
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

function extractOpenAICompatibleText(payload) {
  const choice = Array.isArray(payload?.choices) ? payload.choices[0] : null;
  if (!choice || typeof choice !== "object") {
    return "";
  }
  return normalizeTextOutput(choice.message?.content || choice.text || "");
}

function extractGeminiText(payload) {
  const candidate = Array.isArray(payload?.candidates) ? payload.candidates[0] : null;
  const parts = Array.isArray(candidate?.content?.parts) ? candidate.content.parts : [];
  return normalizeTextOutput(parts.map((item) => item?.text || ""));
}

function extractAnthropicText(payload) {
  return normalizeTextOutput(Array.isArray(payload?.content) ? payload.content.map((item) => item?.text || "") : []);
}

async function invokeCloudProvider(env, providerRecord, options = {}) {
  const messages = providerMessageList({
    prompt: options.prompt || "",
    systemPrompt: options.systemPrompt || "",
    messages: options.messages || [],
  });
  if (providerRecord.provider_id === "mock") {
    return {
      provider: "mock",
      model_name: trimmed(options.model, "mock-model"),
      output_text: `mock:${providerUserPrompt(messages) || "ping"}`,
      raw_usage_safe: {
        prompt_chars: providerPromptExcerpt(messages).length,
        completion_chars: providerUserPrompt(messages).length + 5,
      },
    };
  }
  if (providerRecord.provider_id === "google_vertex_ai") {
    throw {
      error_type: "provider_required",
      safe_message:
        "Google Vertex AI token storage is connected, but model-call routing is still deferred to the next provider-routing issue.",
    };
  }
  if (providerRecord.provider_id === "openai_compatible") {
    const baseUrl = normalizeBaseUrl(env.MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL || "");
    const secret = providerSecret(env, [
      "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY",
      "MYSTIC_PROVIDER_OPENAI_COMPAT_BEARER_TOKEN",
    ]);
    if (!baseUrl || !secret) {
      throw { error_type: "api_key_required", safe_message: "OpenAI-compatible provider is missing required configuration." };
    }
    const payload = await providerRequestJson(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        Authorization: `Bearer ${secret}`,
      },
      body: JSON.stringify({
        model: firstNonEmpty(options.model, env.MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL, providerRecord.model_name),
        messages,
        temperature: Number.isFinite(options.temperature) ? Number(options.temperature) : 0.2,
        max_tokens: Number.isFinite(options.maxTokens) ? Math.max(1, Number(options.maxTokens)) : 1024,
      }),
    });
    return {
      provider: providerRecord.provider_id,
      model_name: firstNonEmpty(options.model, env.MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL, providerRecord.model_name),
      output_text: extractOpenAICompatibleText(payload),
      raw_usage_safe: safeUsagePayload(payload?.usage),
    };
  }
  if (providerRecord.provider_id === "gemini") {
    const apiKey = providerSecret(env, ["MYSTIC_PROVIDER_GEMINI_API_KEY"]);
    const bearerToken = providerSecret(env, ["MYSTIC_PROVIDER_GEMINI_BEARER_TOKEN"]);
    if (!apiKey && !bearerToken) {
      throw { error_type: "api_key_required", safe_message: "Gemini provider is missing required configuration." };
    }
    const modelName = firstNonEmpty(options.model, env.MYSTIC_PROVIDER_GEMINI_MODEL, providerRecord.model_name);
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(modelName)}:generateContent`;
    const headers = { "content-type": "application/json" };
    if (apiKey) {
      headers["x-goog-api-key"] = apiKey;
    }
    if (bearerToken) {
      headers.Authorization = `Bearer ${bearerToken}`;
    }
    const payload = await providerRequestJson(url, {
      method: "POST",
      headers,
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: providerUserPrompt(messages) }] }],
      }),
    });
    return {
      provider: providerRecord.provider_id,
      model_name: modelName,
      output_text: extractGeminiText(payload),
      raw_usage_safe: safeUsagePayload(payload?.usageMetadata),
    };
  }
  if (providerRecord.provider_id === "anthropic") {
    const apiKey = providerSecret(env, ["MYSTIC_PROVIDER_ANTHROPIC_API_KEY"]);
    const bearerToken = providerSecret(env, ["MYSTIC_PROVIDER_ANTHROPIC_BEARER_TOKEN"]);
    if (!apiKey && !bearerToken) {
      throw { error_type: "api_key_required", safe_message: "Anthropic provider is missing required configuration." };
    }
    const headers = {
      "content-type": "application/json",
      "anthropic-version": "2023-06-01",
    };
    if (apiKey) {
      headers["x-api-key"] = apiKey;
    }
    if (bearerToken) {
      headers.Authorization = `Bearer ${bearerToken}`;
    }
    const payload = await providerRequestJson("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: firstNonEmpty(options.model, env.MYSTIC_PROVIDER_ANTHROPIC_MODEL, providerRecord.model_name),
        max_tokens: Number.isFinite(options.maxTokens) ? Math.max(1, Number(options.maxTokens)) : 1024,
        system: messages.find((item) => item.role === "system")?.content || "",
        messages: messages
          .filter((item) => item.role !== "system")
          .map((item) => ({ role: item.role === "user" ? "user" : "assistant", content: item.content })),
      }),
    });
    return {
      provider: providerRecord.provider_id,
      model_name: firstNonEmpty(options.model, env.MYSTIC_PROVIDER_ANTHROPIC_MODEL, providerRecord.model_name),
      output_text: extractAnthropicText(payload),
      raw_usage_safe: safeUsagePayload(payload?.usage),
    };
  }
  throw { error_type: "unsupported_provider", safe_message: `Unsupported provider_id: ${providerRecord.provider_id}` };
}

async function runCloudProviderCall({
  env,
  providerRecord,
  toolName,
  sessionId = "",
  agentRole = "",
  prompt = "",
  systemPrompt = "",
  messages = [],
  model = "",
  temperature = 0.2,
  maxTokens = 1024,
  metadata = {},
}) {
  const messageList = providerMessageList({ prompt, systemPrompt, messages });
  const promptHash = await providerPromptHash(messageList);
  const promptExcerptSafe = providerPromptExcerpt(messageList);
  const safeMetadata = safeProviderMetadata({
    runtime_mode: "cloud_native_worker_lab_v0",
    requested_model: model,
    temperature,
    max_tokens: maxTokens,
    ...metadata,
  });
  const callId = `call-${(await sha256Hex(`${providerRecord.provider_id}:${toolName}:${promptHash}:${Date.now()}`)).slice(0, 16)}`;
  const resolvedModel = firstNonEmpty(model, providerRecord.model_name, providerRecord.provider_id);
  const requiredStatus = providerCallStatusFromRecord(providerRecord);
  if (requiredStatus !== "connected" && providerRecord.provider_id !== "mock") {
    const record = {
      call_id: callId,
      session_id: trimmed(sessionId),
      provider_id: providerRecord.provider_id,
      model: resolvedModel,
      tool_name: toolName,
      agent_role: trimmed(agentRole),
      prompt_hash: promptHash,
      prompt_excerpt_safe: promptExcerptSafe,
      output_text: "",
      status: requiredStatus,
      error_type: requiredStatus,
      latency_ms: 0,
      usage_json: {},
      metadata: safeMetadata,
      created_at: nowIso(),
    };
    const storageRef = await saveCloudModelCall(env, record);
    return {
      status: requiredStatus,
      provider_id: providerRecord.provider_id,
      model: resolvedModel,
      output_text: "",
      raw_usage_safe: {},
      latency_ms: 0,
      error_type: requiredStatus,
      error_message_safe: providerCallErrorMessage(providerRecord, requiredStatus),
      call_id: callId,
      storage_ref: storageRef,
    };
  }

  const startedAt = Date.now();
  try {
    const response = await invokeCloudProvider(env, providerRecord, {
      prompt,
      systemPrompt,
      messages: messageList,
      model: resolvedModel,
      temperature,
      maxTokens,
    });
    const latencyMs = Date.now() - startedAt;
    const record = {
      call_id: callId,
      session_id: trimmed(sessionId),
      provider_id: providerRecord.provider_id,
      model: response.model_name || resolvedModel,
      tool_name: toolName,
      agent_role: trimmed(agentRole),
      prompt_hash: promptHash,
      prompt_excerpt_safe: promptExcerptSafe,
      output_text: response.output_text || "",
      status: "completed",
      error_type: "",
      latency_ms: latencyMs,
      usage_json: response.raw_usage_safe || {},
      metadata: safeMetadata,
      created_at: nowIso(),
    };
    const storageRef = await saveCloudModelCall(env, record);
    return {
      status: "completed",
      provider_id: providerRecord.provider_id,
      model: response.model_name || resolvedModel,
      output_text: response.output_text || "",
      raw_usage_safe: response.raw_usage_safe || {},
      latency_ms: latencyMs,
      error_type: "",
      error_message_safe: "",
      call_id: callId,
      storage_ref: storageRef,
    };
  } catch (error) {
    const latencyMs = Date.now() - startedAt;
    const errorType = trimmed(error?.error_type, "provider_error");
    const safeMessage = trimmed(error?.safe_message, "Provider request failed.");
    const record = {
      call_id: callId,
      session_id: trimmed(sessionId),
      provider_id: providerRecord.provider_id,
      model: resolvedModel,
      tool_name: toolName,
      agent_role: trimmed(agentRole),
      prompt_hash: promptHash,
      prompt_excerpt_safe: promptExcerptSafe,
      output_text: "",
      status: errorType,
      error_type: errorType,
      latency_ms: latencyMs,
      usage_json: {},
      metadata: safeMetadata,
      created_at: nowIso(),
    };
    const storageRef = await saveCloudModelCall(env, record);
    return {
      status: errorType,
      provider_id: providerRecord.provider_id,
      model: resolvedModel,
      output_text: "",
      raw_usage_safe: {},
      latency_ms: latencyMs,
      error_type: errorType,
      error_message_safe: safeMessage,
      call_id: callId,
      storage_ref: storageRef,
    };
  }
}

async function cloudMysticStatus(state, supabase, env) {
  const registry = await loadProviderRegistry(env);
  const verificationSummary = workerManualImportVerification(env, state.issuer);
  const importReadyCandidate = state.metadataAvailable && supabase.configured;
  const importReady = importReadyCandidate && verificationSummary.manual_import_verified;
  const toolStates = {
    mystic_status: "ready",
    health_check: "ready",
    lab_session_create: supabase.configured ? "ready" : "blocked",
    lab_session_get: supabase.configured ? "ready" : "blocked",
    lab_session_list: supabase.configured ? "ready" : "blocked",
    lab_scene_list: supabase.configured ? "ready" : "blocked",
    lab_activity_list: supabase.configured ? "ready" : "blocked",
    lab_session_advance: supabase.configured ? "ready" : "blocked",
    lab_agent_run: registry.providers.some((item) => item.ready) ? "ready" : "provider_required",
    lab_referee_review: supabase.configured ? (registry.providers.some((item) => item.ready) ? "ready" : "deferred") : "blocked",
    lab_experiment_create: supabase.configured ? "ready" : "blocked",
    lab_experiment_run: supabase.configured ? "deferred" : "blocked",
    lab_memory_search: supabase.configured ? "ready" : "blocked",
    lab_memory_write: supabase.configured ? "ready" : "blocked",
    lab_models_debate: registry.providers.some((item) => item.ready) ? "ready" : "provider_required",
    lab_report_generate: supabase.configured ? "ready" : "blocked",
    create_lab_scene: supabase.configured ? "ready" : "blocked",
    get_lab_scene: supabase.configured ? "ready" : "blocked",
    add_lab_object: supabase.configured ? "ready" : "blocked",
    update_lab_object: supabase.configured ? "ready" : "blocked",
    remove_lab_object: supabase.configured ? "ready" : "blocked",
    set_lab_parameters: supabase.configured ? "ready" : "blocked",
    run_lab_simulation: supabase.configured ? "ready" : "blocked",
    attach_simulation_to_scene: supabase.configured ? "ready" : "blocked",
    export_lab_snapshot: supabase.configured ? "ready" : "blocked",
    generate_lab_report: supabase.configured ? "ready" : "blocked",
    provider_list: "ready",
    provider_status: "ready",
    provider_connect_start: supabase.configured ? "ready" : "blocked",
    provider_connect_callback_status: supabase.configured ? "ready" : "blocked",
    provider_configure_secret_instructions: "ready",
    provider_verify: supabase.configured ? "ready" : "blocked",
    provider_disconnect: supabase.configured ? "ready" : "blocked",
    provider_model_list: "ready",
    provider_call_test: "ready",
  };
  const blockers = [];
  if (!state.enabled) {
    blockers.push("OAUTH_NOT_CONFIGURED");
  } else if (!state.configured) {
    blockers.push("OAUTH_METADATA_MISSING");
  } else if (!importReady) {
    blockers.push("MANUAL_IMPORT_NOT_VERIFIED");
  }
  if (!supabase.configured) {
    blockers.push("LAB_STORAGE_NOT_CONFIGURED");
  }
  return {
    models: {},
    provider_registry: registry.providers.map((item) => ({
      provider_id: item.provider_id,
      provider_type: item.provider_type,
      auth_method: item.auth_method,
      status: item.status,
      scopes: item.scopes,
      created_at: item.created_at,
      setup_url: item.setup_url,
      setup_instructions: item.setup_instructions,
    })),
    tools: toolStates,
    lab_core_available: true,
    lab_tools_count: CLOUD_TOOL_DEFINITIONS.filter((tool) => !["mystic_status", "health_check"].includes(tool.name)).length,
    phase_1_tools_count: CLOUD_REQUIRED_TOOL_NAMES.length,
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
    chatgpt_remote_import_ready: importReady,
    chatgpt_remote_import_ready_candidate: importReadyCandidate,
    manual_import_verification_checked: verificationSummary.manual_import_verification_checked,
    manual_import_verified: verificationSummary.manual_import_verified,
    manual_import_verification_path: verificationSummary.manual_import_verification_path,
    manual_import_verification_summary: verificationSummary.manual_import_verification_summary,
    blockers,
    datasets: {},
    adapter_status: {
      available: ["math.sympy", "physics.simple_projectile", "physics.simple_collision", "scene.three_json"],
      limited_subsets: ["math.sympy"],
      engine_required: [],
    },
    recent_runs: [],
    recent_errors: registry.warnings,
    mcp_server_status: "ready",
    runtime_mode: "cloud_native_worker_lab_v0",
  };
}

async function cloudHealthCheck(state, supabase, env) {
  const registry = await loadProviderRegistry(env);
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
    phase_1_tools: CLOUD_REQUIRED_TOOL_NAMES,
    provider_registry: registry.providers.map((item) => ({
      provider_id: item.provider_id,
      status: item.status,
      auth_method: item.auth_method,
    })),
  };
}

function cloudExperimentSummary(experiment, claimStatus) {
  return {
    experiment_id: experiment.experiment_id,
    verdict: experiment.verdict,
    outputs: experiment.outputs,
    evidence_summary: experiment.evidence_summary,
    updated_claim_status: claimStatus || "UNKNOWN",
  };
}

function parseProviderRefereeOutput(text) {
  try {
    const payload = JSON.parse(String(text || ""));
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("invalid");
    }
    const verdict = ["VALID", "INVALID", "UNKNOWN"].includes(String(payload.verdict || "").toUpperCase())
      ? String(payload.verdict).toUpperCase()
      : "UNKNOWN";
    return {
      verdict,
      critique: trimmed(payload.critique),
      first_fatal_error: trimmed(payload.first_fatal_error),
      recommended_next_action: trimmed(payload.recommended_next_action, "Review referee verdict."),
    };
  } catch {
    return {
      verdict: "UNKNOWN",
      critique: trimmed(text, "Provider referee did not return parseable JSON."),
      first_fatal_error: "",
      recommended_next_action: "Review provider-backed referee output manually.",
    };
  }
}

function providerVerdictToClaimStatus(verdict) {
  if (verdict === "VALID") {
    return "TESTED";
  }
  if (verdict === "INVALID") {
    return "REFUTED";
  }
  return "UNKNOWN";
}

async function runCloudAgentTurn({
  env,
  bundle,
  phase,
  agentRole,
  task,
  providerPreference,
  contextIds = [],
  replyTo = [],
}) {
  const registry = await loadProviderRegistry(env);
  const providerDecision = selectCloudProvider(env, registry, providerPreference);
  const context = contextFromIds(bundle, contextIds) || phaseContext(bundle, phase);
  const prompt = [
    `Agent role: ${agentRole}`,
    `Phase: ${phase}`,
    `Problem: ${bundle.session.problem}`,
    `Goal: ${bundle.session.goal}`,
    `Task: ${task}`,
    "",
    "Context:",
    context,
  ].join("\n");
  if (providerDecision.deferred) {
    const turn = makeCloudTurn({
      sessionId: bundle.session.session_id,
      phase,
      agentRole,
      provider: "tool",
      modelName: "local_backend_unavailable",
      inputSummary: task.slice(0, 200),
      output: providerDecision.deferred.message,
      status: "blocked",
      requestedTools: [],
      toolResults: [providerDecision.deferred],
      replyTo,
    });
    bundle.turns.push(turn);
    bundle.session.status = "waiting_for_user";
    bundle.session.next_actions = [providerDecision.deferred.setup_instructions || providerDecision.deferred.message];
    return { turn, claims: [], response: providerDecision.deferred };
  }
  if (providerDecision.providerRequired) {
    const turn = makeCloudTurn({
      sessionId: bundle.session.session_id,
      phase,
      agentRole,
      provider: providerDecision.providerRequired.provider,
      modelName: providerDecision.providerRequired.provider,
      inputSummary: task.slice(0, 200),
      output: providerDecision.providerRequired.message,
      status: "AUTH_REQUIRED",
      requestedTools: [],
      toolResults: [providerDecision.providerRequired],
      replyTo,
    });
    bundle.turns.push(turn);
    bundle.session.status = "waiting_for_user";
    bundle.session.next_actions = [
      providerDecision.providerRequired.setup_instructions,
      "Retry the same LAB action after connecting the provider.",
    ];
    return { turn, claims: [], response: providerDecision.providerRequired };
  }

  const invocation = await runCloudProviderCall({
    env,
    providerRecord: providerDecision.selection,
    toolName: "lab_agent_run",
    sessionId: bundle.session.session_id,
    agentRole,
    systemPrompt: `You are Mystic LAB agent ${agentRole} operating in phase ${phase}.`,
    prompt,
    metadata: { phase },
  });
  const turnStatus =
    invocation.status === "completed"
      ? "completed"
      : ["provider_required", "api_key_required", "provider_auth_failed"].includes(invocation.status)
        ? "AUTH_REQUIRED"
        : "ERROR";
  const turn = makeCloudTurn({
    sessionId: bundle.session.session_id,
    phase,
    agentRole,
    provider: invocation.provider_id,
    modelName: invocation.model || providerDecision.selection.model_name,
    inputSummary: task.slice(0, 200),
    output: invocation.output_text || invocation.error_message_safe || "Provider returned no text output.",
    status: turnStatus,
    requestedTools: [],
    toolResults: [invocation],
    replyTo,
    error: turnStatus === "completed" ? "" : invocation.error_type || "provider_error",
  });
  const claims = turnStatus === "completed" ? claimsFromTurn(bundle.session.session_id, turn) : [];
  bundle.turns.push(turn);
  if (claims.length) {
    bundle.claims.push(...claims);
  }
  bundle.session.status = turnStatus === "completed" ? "running" : "waiting_for_user";
  bundle.session.next_actions =
    turnStatus === "completed"
      ? ["Review the new agent turn.", "Decide whether to advance the session or run a referee review."]
      : [invocation.error_message_safe || "Retry after resolving the provider requirement or error."];
  return { turn, claims, response: invocation };
}

async function cloudMemorySearch(env, { query, domain, statusFilter, limit }) {
  const queryText = String(query || "").toLowerCase();
  const [sessionRows, claimRows, failureRows, memoryEdgeRows] = await Promise.all([
    supabaseSelectRows(env, "lab_sessions", {}, { order: "updated_at.desc" }),
    supabaseSelectRows(env, "claims", {}, { order: "updated_at.desc" }),
    supabaseSelectRows(env, "failures", {}, { order: "created_at.desc" }),
    supabaseSelectRows(env, "memory_edges", {}, { order: "created_at.desc" }),
  ]);
  const matchingSessions = [];
  const claims = [];
  const failures = [];
  const experiments = [];
  const edges = [];
  const eligibleSessionIds = new Set();
  for (const sessionRow of sessionRows) {
    if (domain && trimmed(sessionRow.domain) !== domain) {
      continue;
    }
    const sessionId = trimmed(sessionRow.session_id);
    if (!sessionId) {
      continue;
    }
    eligibleSessionIds.add(sessionId);
    if (String(JSON.stringify(sessionRow) || "").toLowerCase().includes(queryText)) {
      matchingSessions.push(sessionRow);
    }
    const experimentRows = Array.isArray(sessionRow.experiments_json) ? sessionRow.experiments_json : [];
    for (const experiment of experimentRows) {
      if (String(JSON.stringify(experiment) || "").toLowerCase().includes(queryText)) {
        experiments.push(experiment);
      }
    }
  }
  for (const claim of claimRows) {
    if (!eligibleSessionIds.has(trimmed(claim.session_id))) {
      continue;
    }
    if (statusFilter && trimmed(claim.status) !== statusFilter) {
      continue;
    }
    if (String(claim.text || "").toLowerCase().includes(queryText)) {
      claims.push(claim);
    }
  }
  for (const failure of failureRows) {
    if (!eligibleSessionIds.has(trimmed(failure.session_id))) {
      continue;
    }
    if (String(JSON.stringify(failure) || "").toLowerCase().includes(queryText)) {
      failures.push(failure);
    }
  }
  for (const edge of memoryEdgeRows) {
    if (!eligibleSessionIds.has(trimmed(edge.session_id))) {
      continue;
    }
    if (String(JSON.stringify(edge) || "").toLowerCase().includes(queryText)) {
      edges.push(edge);
    }
  }
  return {
    matching_sessions: matchingSessions.slice(0, limit),
    claims: claims.slice(0, limit),
    failures: failures.slice(0, limit),
    experiments: experiments.slice(0, limit),
    memory_edges: edges.slice(0, limit),
  };
}

async function callCloudTool(name, args, env, state) {
  const supabase = supabaseState(env);
  if (name === "mystic_status") {
    return cloudMysticStatus(state, supabase, env);
  }
  if (name === "health_check") {
    return cloudHealthCheck(state, supabase, env);
  }
  if (!supabase.configured) {
    throw new Error("Supabase storage is not configured for cloud-native LAB mode.");
  }
  const limit = Math.min(100, Math.max(1, Number.isInteger(args.limit) ? args.limit : 50));
  if (name === "lab_session_list") {
    const filters = { ...(trimmed(args.status_filter) ? { status: `eq.${trimmed(args.status_filter)}` } : {}), ...(trimmed(args.domain_filter) ? { domain: `eq.${trimmed(args.domain_filter)}` } : {}), ...(trimmed(args.updated_after) ? { updated_at: `gt.${trimmed(args.updated_after)}` } : {}) };
    const rows = await supabaseSelectRows(env, "lab_sessions", filters, { order: "updated_at.desc", params: { limit: String(limit) } });
    return { records: rows.map((row) => ({ session_id: row.session_id, problem: row.problem, domain: row.domain, goal: row.goal, mode: row.mode, phase: row.current_phase, status: row.status, participants: asStringArray(row.participants), created_at: row.created_at, updated_at: row.updated_at })), next_cursor: "" };
  }
  if (name === "lab_scene_list") {
    const rows = await supabaseRpc(env, "mystic_list_lab_scenes", { p_limit: limit, p_session_id: trimmed(args.session_id) || null, p_updated_after: trimmed(args.updated_after) || null });
    const records = (Array.isArray(rows) ? rows : []).map((row) => ({ scene_id: row.scene_id, session_id: row.session_id, title: row.title, description: row.description, object_count: Number(row.object_count || 0), simulation_count: Number(row.simulation_count || 0), revision: Number(row.revision || 1), status: "ready", created_at: row.created_at, updated_at: row.updated_at }));
    return { records, next_cursor: "" };
  }
  if (name === "lab_activity_list") {
    const rows = await supabaseSelectRows(env, "lab_activity_events", { ...(trimmed(args.session_id) ? { session_id: `eq.${trimmed(args.session_id)}` } : {}), ...(trimmed(args.updated_after) ? { created_at: `gt.${trimmed(args.updated_after)}` } : {}) }, { order: "created_at.desc", params: { limit: String(limit) } });
    return { records: rows.map((row) => ({ event_id: row.event_id, event_type: row.event_type, session_id: row.session_id, scene_id: row.scene_id, tool_name: row.tool_name, status: row.status, safe_summary: row.safe_summary, created_at: row.created_at, metadata_safe: objectMapping(row.metadata_safe) })), next_cursor: "" };
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
  if (name === "lab_session_advance") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const newTurns = [];
    const newClaims = [];
    const newExperiments = [];
    const newFailures = [];
    const maxSteps = Number.isInteger(args.max_steps) ? args.max_steps : 1;
    for (let index = 0; index < Math.max(1, maxSteps); index += 1) {
      const phase = bundle.session.current_phase;
      if (phase === "completed") {
        break;
      }
      if (phase === "problem_intake") {
        const turn = makeCloudTurn({
          sessionId: bundle.session.session_id,
          phase,
          agentRole: "Director",
          provider: "tool",
          modelName: "cloud_worker",
          inputSummary: bundle.session.problem.slice(0, 200),
          output: "Cloud-native intake recorded the problem, goal, and participants in Supabase.",
          status: "completed",
          requestedTools: [],
        });
        bundle.turns.push(turn);
        newTurns.push(turn);
        bundle.notebook_markdown += `\n## ${phase}\n\n${turn.output}\n`;
        bundle.session.current_phase = cloudNextPhase(phase);
        bundle.session.active_room = LAB_PHASE_TO_ROOM[bundle.session.current_phase] || bundle.session.active_room;
        bundle.session.status = "running";
        bundle.session.next_actions = cloudNextActionsForPhase(bundle.session.current_phase);
      } else if (phase === "experiment_design") {
        const claim = latestClaim(bundle);
        const experiment = {
          session_id: bundle.session.session_id,
          claim_id: claim ? claim.claim_id : "",
          question: claim ? `Test claim: ${claim.text}` : `Design an experiment for: ${bundle.session.problem}`,
          method: args.use_verifier === false ? "manual_review" : "python_bruteforce",
          inputs: {
            candidate_answer: claim ? claim.text : "",
            source: "cloud_native_auto_planner",
          },
          outputs: {},
          tool_name: args.use_verifier === false ? "manual_review" : "cloud_deferred_verifier",
          verdict: "inconclusive",
          evidence_summary: "Cloud-native LAB planned the next experiment and stored it in Supabase.",
          created_at: nowIso(),
          experiment_id: cloudId("experiment"),
        };
        bundle.experiments.push(experiment);
        newExperiments.push(experiment);
        if (claim) {
          bundle.memory_edges.push(
            makeMemoryEdge({
              sessionId: bundle.session.session_id,
              fromId: claim.claim_id,
              toId: experiment.experiment_id,
              relation: "generated_experiment",
              evidence: experiment.question,
            }),
          );
        }
        const turn = makeCloudTurn({
          sessionId: bundle.session.session_id,
          phase,
          agentRole: "ExperimentDesigner",
          provider: "tool",
          modelName: "cloud_worker",
          inputSummary: experiment.question.slice(0, 200),
          output: `Experiment planned: ${experiment.question}`,
          status: "completed",
        });
        bundle.turns.push(turn);
        newTurns.push(turn);
        bundle.notebook_markdown += `\n## ${phase}\n\n${turn.output}\n`;
        bundle.session.current_phase = cloudNextPhase(phase);
        bundle.session.active_room = LAB_PHASE_TO_ROOM[bundle.session.current_phase] || bundle.session.active_room;
        bundle.session.next_actions = cloudNextActionsForPhase(bundle.session.current_phase);
      } else if (phase === "failure_archive") {
        const turn = makeCloudTurn({
          sessionId: bundle.session.session_id,
          phase,
          agentRole: "Archivist",
          provider: "tool",
          modelName: "cloud_worker",
          inputSummary: "Archive current failures",
          output: `Failure archive contains ${bundle.failures.length} recorded failures.`,
          status: "completed",
        });
        bundle.turns.push(turn);
        newTurns.push(turn);
        bundle.notebook_markdown += `\n## ${phase}\n\n${turn.output}\n`;
        bundle.session.current_phase = cloudNextPhase(phase);
        bundle.session.active_room = LAB_PHASE_TO_ROOM[bundle.session.current_phase] || bundle.session.active_room;
        bundle.session.next_actions = cloudNextActionsForPhase(bundle.session.current_phase);
      } else if (phase === "report_generation") {
        const report = renderCloudReport(bundle);
        bundle.report_markdown = report.markdown;
        const turn = makeCloudTurn({
          sessionId: bundle.session.session_id,
          phase,
          agentRole: "PaperWriter",
          provider: "tool",
          modelName: "cloud_worker",
          inputSummary: "Generate final markdown report",
          output: "Cloud-native report generated and stored in Supabase.",
          status: "completed",
        });
        bundle.turns.push(turn);
        newTurns.push(turn);
        bundle.session.current_phase = "completed";
        bundle.session.active_room = LAB_PHASE_TO_ROOM.completed;
        bundle.session.status = "completed";
        bundle.session.next_actions = [];
      } else if (phase === "referee_review") {
        const deferred = deferredResult(
          "Cloud-native referee review is exposed but still requires a future worker-native verifier or an explicitly connected verifier-capable provider.",
          { required_capability: "referee_review" },
        );
        const turn = makeCloudTurn({
          sessionId: bundle.session.session_id,
          phase,
          agentRole: "Referee",
          provider: "tool",
          modelName: "cloud_referee_deferred",
          inputSummary: bundle.session.problem.slice(0, 200),
          output: deferred.message,
          status: "blocked",
          toolResults: [deferred],
        });
        bundle.turns.push(turn);
        newTurns.push(turn);
        bundle.session.status = "waiting_for_user";
        bundle.session.next_actions = [deferred.message];
        break;
      } else {
        const role = LAB_PHASE_TO_AGENT_ROLE[phase] || "Director";
        const outcome = await runCloudAgentTurn({
          env,
          bundle,
          phase,
          agentRole: role,
          task: `Advance the Mystic LAB through ${phase} for problem: ${bundle.session.problem}`,
          providerPreference: "auto",
        });
        newTurns.push(outcome.turn);
        if (outcome.claims.length) {
          newClaims.push(...outcome.claims);
        }
        bundle.notebook_markdown += `\n## ${phase}\n\n${outcome.turn.output.slice(0, 500)}\n`;
        if (outcome.response.status !== "completed") {
          break;
        }
        bundle.session.current_phase = cloudNextPhase(phase);
        bundle.session.active_room = LAB_PHASE_TO_ROOM[bundle.session.current_phase] || bundle.session.active_room;
        bundle.session.next_actions = cloudNextActionsForPhase(bundle.session.current_phase);
      }
      if (args.target_phase && bundle.session.current_phase === args.target_phase) {
        break;
      }
    }
    bundle.session.updated_at = nowIso();
    const paths = await saveCloudBundle(env, bundle);
    return {
      updated_session: bundle.session,
      new_turns: newTurns,
      new_claims: newClaims,
      new_experiments: newExperiments,
      new_failures: newFailures,
      next_actions: bundle.session.next_actions,
      paths,
    };
  }
  if (name === "lab_agent_run") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const outcome = await runCloudAgentTurn({
      env,
      bundle,
      phase: bundle.session.current_phase,
      agentRole: args.agent_role,
      task: args.task,
      providerPreference: args.provider,
      contextIds: asStringArray(args.context_ids),
    });
    bundle.session.updated_at = nowIso();
    await saveCloudBundle(env, bundle);
    return {
      turn_id: outcome.turn.turn_id,
      status: outcome.turn.status,
      output: outcome.turn.output,
      extracted_claims: outcome.claims,
      next_actions: bundle.session.next_actions,
      provider_result: outcome.response,
    };
  }
  if (name === "lab_referee_review") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const requestedProvider = normalizeRequestedProvider(args.provider || "");
    if (requestedProvider && requestedProvider !== "auto" && requestedProvider !== "local_backend") {
      const registry = await loadProviderRegistry(env);
      const record = providerRegistryMap(registry).get(requestedProvider) || buildProviderRecord(env, requestedProvider);
      const targetText = trimmed(args.text) || trimmed(findClaim(bundle, trimmed(args.claim_id))?.text);
      const providerResult = await runCloudProviderCall({
        env,
        providerRecord: record,
        toolName: "lab_referee_review",
        sessionId: bundle.session.session_id,
        agentRole: "Referee",
        systemPrompt: "You are a strict Mystic LAB referee. Return JSON with keys verdict, critique, first_fatal_error, recommended_next_action.",
        prompt: [
          `Problem: ${bundle.session.problem}`,
          `Strictness: ${trimmed(args.strictness, "hostile")}`,
          `Claim text: ${targetText}`,
          "If you cannot verify completely, return verdict UNKNOWN and explain the remaining gap.",
        ].join("\n"),
        metadata: { strictness: trimmed(args.strictness, "hostile"), claim_id: trimmed(args.claim_id) },
      });
      const parsed = parseProviderRefereeOutput(providerResult.output_text);
      const turnStatus =
        providerResult.status === "completed"
          ? "completed"
          : ["provider_required", "api_key_required", "provider_auth_failed"].includes(providerResult.status)
            ? "AUTH_REQUIRED"
            : "ERROR";
      const claim = findClaim(bundle, trimmed(args.claim_id));
      const failures = [];
      const updatedClaims = [];
      if (turnStatus === "completed" && claim) {
        claim.status = providerVerdictToClaimStatus(parsed.verdict);
        claim.updated_at = nowIso();
        updatedClaims.push(claim);
        if (parsed.first_fatal_error) {
          const failure = makeFailure({
            sessionId: bundle.session.session_id,
            claimId: claim.claim_id,
            sourceTurnId: "",
            firstFatalError: parsed.first_fatal_error,
            failureType: "logic_gap",
            lesson: "Provider-backed referee identified a failure or proof gap.",
          });
          bundle.failures.push(failure);
          failures.push(failure);
        }
      }
      const turn = makeCloudTurn({
        sessionId: bundle.session.session_id,
        phase: "referee_review",
        agentRole: "Referee",
        provider: record.provider_id,
        modelName: providerResult.model || record.model_name,
        inputSummary: String(args.text || "").slice(0, 200),
        output: providerResult.output_text || providerResult.error_message_safe,
        status: turnStatus,
        requestedTools: ["lab_referee_review"],
        toolResults: [providerResult],
        replyTo: args.claim_id ? [args.claim_id] : [],
        error: turnStatus === "completed" ? "" : providerResult.error_type || "provider_error",
      });
      bundle.turns.push(turn);
      bundle.session.status = turnStatus === "completed" ? "running" : "waiting_for_user";
      bundle.session.next_actions = [parsed.recommended_next_action || providerResult.error_message_safe || "Review referee verdict."];
      bundle.session.updated_at = nowIso();
      await saveCloudBundle(env, bundle);
      return {
        verdict: turnStatus === "completed" ? parsed.verdict : providerResult.status.toUpperCase(),
        first_fatal_error: parsed.first_fatal_error,
        critique: parsed.critique || providerResult.error_message_safe,
        recommended_next_action: parsed.recommended_next_action || providerResult.error_message_safe,
        updated_claims: updatedClaims,
        failures,
        turn_id: turn.turn_id,
        provider_result: providerResult,
      };
    }
    const deferred = deferredResult(
      "Cloud-native referee review is not yet backed by a worker-native deterministic verifier. Use an explicitly connected future verifier provider or local mode for strict proof review.",
      { required_capability: "referee_review" },
    );
    const turn = makeCloudTurn({
      sessionId: bundle.session.session_id,
      phase: "referee_review",
      agentRole: "Referee",
      provider: "tool",
      modelName: "cloud_referee_deferred",
      inputSummary: String(args.text || "").slice(0, 200),
      output: deferred.message,
      status: "blocked",
      requestedTools: ["lab_referee_review"],
      toolResults: [deferred],
      replyTo: args.claim_id ? [args.claim_id] : [],
    });
    bundle.turns.push(turn);
    bundle.session.status = "waiting_for_user";
    bundle.session.next_actions = [deferred.message];
    bundle.session.updated_at = nowIso();
    await saveCloudBundle(env, bundle);
    return {
      verdict: "DEFERRED",
      first_fatal_error: "",
      critique: deferred.message,
      recommended_next_action: deferred.message,
      updated_claims: [],
      failures: [],
      turn_id: turn.turn_id,
      deferred,
    };
  }
  if (name === "lab_experiment_create") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const experiment = {
      session_id: bundle.session.session_id,
      claim_id: args.claim_id.trim(),
      question: args.question.trim(),
      method: args.method.trim(),
      inputs: args.inputs,
      outputs: {},
      tool_name: "",
      verdict: "inconclusive",
      evidence_summary: "",
      created_at: nowIso(),
      experiment_id: cloudId("experiment"),
    };
    bundle.experiments.push(experiment);
    bundle.memory_edges.push(
      makeMemoryEdge({
        sessionId: bundle.session.session_id,
        fromId: experiment.claim_id,
        toId: experiment.experiment_id,
        relation: "generated_experiment",
        evidence: experiment.question,
      }),
    );
    bundle.session.updated_at = nowIso();
    bundle.session.next_actions = [`Run experiment ${experiment.experiment_id}.`];
    await saveCloudBundle(env, bundle);
    return { experiment_id: experiment.experiment_id, status: experiment.verdict };
  }
  if (name === "lab_experiment_run") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const experiment = findExperiment(bundle, args.experiment_id.trim());
    if (!experiment) {
      throw new Error(`Unknown experiment_id: ${args.experiment_id}`);
    }
    const claim = findClaim(bundle, experiment.claim_id);
    if (args.dry_run === true) {
      return cloudExperimentSummary(experiment, claim?.status);
    }
    let response;
    if (experiment.method === "model_debate") {
      response = deferredResult(
        "Cloud-native experiment runs with method=model_debate require an explicitly connected external provider before execution can continue.",
        { required_capability: "model_debate" },
      );
    } else {
      response = deferredResult(
        `Cloud-native experiment execution for method=${experiment.method} is exposed but deferred until a worker-native execution backend is added.`,
        { required_capability: experiment.method },
      );
    }
    experiment.outputs = response;
    experiment.tool_name = experiment.method === "model_debate" ? "lab_models_debate" : `deferred_${experiment.method}`;
    experiment.verdict = "inconclusive";
    experiment.evidence_summary = response.message;
    bundle.session.updated_at = nowIso();
    bundle.session.status = "waiting_for_user";
    bundle.session.next_actions = [response.message];
    await saveCloudBundle(env, bundle);
    return { ...cloudExperimentSummary(experiment, claim?.status), deferred: response };
  }
  if (name === "lab_memory_search") {
    return cloudMemorySearch(env, {
      query: args.query.trim(),
      domain: args.domain ? String(args.domain).trim() : "",
      statusFilter: args.status_filter ? String(args.status_filter).trim() : "",
      limit: Number.isInteger(args.limit) ? args.limit : 10,
    });
  }
  if (name === "lab_memory_write") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const payload = args.payload || {};
    let writtenObjectId = "";
    let pathKey = "session";
    if (args.kind === "claim") {
      const claim = {
        session_id: bundle.session.session_id,
        text: trimmed(payload.text),
        claim_type: trimmed(payload.claim_type, "observation"),
        status: trimmed(payload.status, "UNKNOWN"),
        confidence: trimmed(payload.confidence, "low"),
        source_turn_id: trimmed(payload.source_turn_id),
        supporting_evidence: Array.isArray(payload.supporting_evidence) ? payload.supporting_evidence.map(String) : [],
        refuting_evidence: Array.isArray(payload.refuting_evidence) ? payload.refuting_evidence.map(String) : [],
        related_experiments: Array.isArray(payload.related_experiments) ? payload.related_experiments.map(String) : [],
        related_failures: Array.isArray(payload.related_failures) ? payload.related_failures.map(String) : [],
        created_at: nowIso(),
        updated_at: nowIso(),
        claim_id: trimmed(payload.claim_id, cloudId("claim")),
      };
      bundle.claims.push(claim);
      writtenObjectId = claim.claim_id;
      pathKey = "claims";
    } else if (args.kind === "failure") {
      const failure = makeFailure({
        sessionId: bundle.session.session_id,
        claimId: trimmed(payload.claim_id),
        sourceTurnId: trimmed(payload.source_turn_id),
        firstFatalError: trimmed(payload.first_fatal_error),
        failureType: trimmed(payload.failure_type, "tool_error"),
        lesson: trimmed(payload.lesson, "Cloud-native operator note."),
        reusableAsTrainingData: Boolean(payload.reusable_as_training_data),
      });
      bundle.failures.push(failure);
      writtenObjectId = failure.failure_id;
      pathKey = "failures";
    } else if (args.kind === "experiment") {
      const experiment = {
        session_id: bundle.session.session_id,
        claim_id: trimmed(payload.claim_id),
        question: trimmed(payload.question),
        method: trimmed(payload.method, "manual_review"),
        inputs: payload.inputs && typeof payload.inputs === "object" ? payload.inputs : {},
        outputs: payload.outputs && typeof payload.outputs === "object" ? payload.outputs : {},
        tool_name: trimmed(payload.tool_name),
        verdict: trimmed(payload.verdict, "inconclusive"),
        evidence_summary: trimmed(payload.evidence_summary),
        created_at: nowIso(),
        experiment_id: trimmed(payload.experiment_id, cloudId("experiment")),
      };
      bundle.experiments.push(experiment);
      writtenObjectId = experiment.experiment_id;
      pathKey = "experiments";
    } else if (args.kind === "edge") {
      const edge = makeMemoryEdge({
        sessionId: bundle.session.session_id,
        fromId: trimmed(payload.from_id),
        toId: trimmed(payload.to_id),
        relation: trimmed(payload.relation, "supports"),
        evidence: trimmed(payload.evidence),
      });
      bundle.memory_edges.push(edge);
      writtenObjectId = edge.edge_id;
      pathKey = "memory_edges";
    } else if (args.kind === "note") {
      const note = trimmed(payload.text);
      bundle.notebook_markdown += `${bundle.notebook_markdown.endsWith("\n") ? "" : "\n"}- ${note}\n`;
      writtenObjectId = "note";
      pathKey = "notebook";
    } else {
      throw new Error(`Unsupported memory kind: ${args.kind}`);
    }
    bundle.session.updated_at = nowIso();
    await saveCloudBundle(env, bundle);
    return { written_object_id: writtenObjectId, path: bundle.session.artifact_paths[pathKey] || bundle.session.artifact_paths.session };
  }
  if (name === "lab_models_debate") {
    const bundle = await loadCloudBundle(env, args.session_id.trim());
    if (!bundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    if (args.use_existing_research_table !== true) {
      const deferred = deferredResult(
        "Cloud-native Model Arena currently requires use_existing_research_table=true semantics, but executes through direct provider calls instead of the local Research Table backend.",
        { required_capability: "cloud_model_arena" },
      );
      return { debate_session_id: "", research_table_session_id: "", imported_claims: 0, imported_failures: 0, summary: deferred.message, deferred };
    }
    const registry = await loadProviderRegistry(env);
    const selectedProviders = asStringArray(args.participants)
      .map((item) => parseProviderParticipantAlias(item))
      .filter((item) => item.provider_id && item.provider_id !== "auto");
    if (selectedProviders.some((item) => item.provider_id === "local_backend")) {
      const deferred = localBackendDeferredResult();
      return {
        debate_session_id: "",
        research_table_session_id: "",
        imported_claims: 0,
        imported_failures: 0,
        summary: deferred.message,
        deferred,
        transcript: [],
        final_synthesis: "",
      };
    }
    const providerMap = providerRegistryMap(registry);
    const missing = selectedProviders
      .map((item) => providerMap.get(item.provider_id) || buildProviderRecord(env, item.provider_id))
      .find((record) => record && providerCallStatusFromRecord(record) !== "connected");
    if (missing) {
      const requiredStatus = providerCallStatusFromRecord(missing);
      const required = {
        status: requiredStatus,
        provider_id: missing.provider_id,
        model: missing.model_name,
        output_text: "",
        raw_usage_safe: {},
        latency_ms: 0,
        error_type: requiredStatus,
        error_message_safe: providerCallErrorMessage(missing, requiredStatus),
        call_id: "",
        storage_ref: "",
      };
      const turn = makeCloudTurn({
        sessionId: bundle.session.session_id,
        phase: "simulation_or_execution",
        agentRole: "ModelArena",
        provider: missing.provider_id,
        modelName: missing.model_name,
        inputSummary: args.question.slice(0, 200),
        output: required.error_message_safe,
        status: "AUTH_REQUIRED",
        toolResults: [required],
      });
      bundle.turns.push(turn);
      bundle.session.status = "waiting_for_user";
      bundle.session.next_actions = [required.error_message_safe];
      bundle.session.updated_at = nowIso();
      await saveCloudBundle(env, bundle);
      return {
        debate_session_id: "",
        research_table_session_id: "",
        imported_claims: 0,
        imported_failures: 0,
        summary: required.error_message_safe,
        provider_result: required,
        transcript: [],
        final_synthesis: "",
      };
    }
    const readyProviders =
      selectedProviders.length > 0
        ? selectedProviders
            .map((item) => ({
              record: providerMap.get(item.provider_id) || buildProviderRecord(env, item.provider_id),
              requested_model: item.model,
            }))
            .filter((item) => item.record)
        : registry.providers.filter((item) => item.ready).slice(0, 3);
    if (!readyProviders.length) {
      const required = {
        status: "provider_required",
        provider_id: registry.providers[0].provider_id,
        model: registry.providers[0].model_name,
        output_text: "",
        raw_usage_safe: {},
        latency_ms: 0,
        error_type: "provider_required",
        error_message_safe: "No cloud-native model provider is connected. Configure one before running Model Arena.",
        call_id: "",
        storage_ref: "",
      };
      return {
        debate_session_id: "",
        research_table_session_id: "",
        imported_claims: 0,
        imported_failures: 0,
        summary: required.error_message_safe,
        provider_result: required,
        transcript: [],
        final_synthesis: "",
      };
    }
    const debateSessionId = cloudId("debate");
    let importedClaims = 0;
    const transcript = [];
    for (const item of readyProviders.slice(0, 3)) {
      const providerRecord = item.record || item;
      const invocation = await runCloudProviderCall({
        env,
        providerRecord,
        toolName: "lab_models_debate",
        sessionId: bundle.session.session_id,
        agentRole: "ModelArena",
        model: item.requested_model || "",
        systemPrompt: "You are one participant in a structured Mystic LAB research debate. Be explicit about assumptions and uncertainty.",
        prompt: [
          `Cloud-native Model Arena debate for session ${bundle.session.session_id}.`,
          `Question: ${args.question}`,
          `Rounds requested: ${asStringArray(args.rounds).join(", ")}`,
          `Problem: ${bundle.session.problem}`,
          `Transcript so far: ${JSON.stringify(transcript)}`,
        ].join("\n"),
        metadata: { rounds: asStringArray(args.rounds), question: args.question },
      });
      const turn = makeCloudTurn({
        sessionId: bundle.session.session_id,
        phase: "simulation_or_execution",
        agentRole: "ModelArena",
        provider: invocation.provider_id,
        modelName: invocation.model || providerRecord.model_name,
        inputSummary: args.question.slice(0, 200),
        output: invocation.output_text || invocation.error_message_safe || "Provider returned no text output.",
        status: invocation.status === "completed" ? "completed" : "ERROR",
        toolResults: [invocation],
      });
      const claims = invocation.status === "completed" ? claimsFromTurn(bundle.session.session_id, turn) : [];
      bundle.turns.push(turn);
      bundle.claims.push(...claims);
      importedClaims += claims.length;
      transcript.push({
        provider_id: invocation.provider_id,
        model: invocation.model,
        status: invocation.status,
        output_text: invocation.output_text || invocation.error_message_safe,
        call_id: invocation.call_id,
      });
    }
    const synthesisProvider = readyProviders[0].record || readyProviders[0];
    const synthesisInvocation = await runCloudProviderCall({
      env,
      providerRecord: synthesisProvider,
      toolName: "lab_models_debate",
      sessionId: bundle.session.session_id,
      agentRole: "Synthesizer",
      model: readyProviders[0].requested_model || "",
      systemPrompt: "You are the final synthesizer for a provider-backed Mystic LAB debate. Summarize agreement, disagreement, and next checks.",
      prompt: [`Question: ${args.question}`, `Transcript: ${JSON.stringify(transcript)}`].join("\n"),
      metadata: { synthesis: true, rounds: asStringArray(args.rounds) },
    });
    const summaryTurn = makeCloudTurn({
      sessionId: bundle.session.session_id,
      phase: "simulation_or_execution",
      agentRole: "Synthesizer",
      provider: synthesisInvocation.provider_id,
      modelName: synthesisInvocation.model || synthesisProvider.model_name,
      inputSummary: args.question.slice(0, 200),
      output:
        synthesisInvocation.output_text ||
        `Cloud-native Model Arena completed with ${readyProviders.length} provider participants and imported ${importedClaims} claims.`,
      status: synthesisInvocation.status === "completed" ? "completed" : "ERROR",
      toolResults: [synthesisInvocation],
    });
    bundle.turns.push(summaryTurn);
    bundle.session.status = "running";
    bundle.session.next_actions = ["Review imported Model Arena claims.", "Run referee review on contested claims when a verifier is available."];
    bundle.session.updated_at = nowIso();
    await saveCloudBundle(env, bundle);
    return {
      debate_session_id: debateSessionId,
      research_table_session_id: "",
      imported_claims: importedClaims,
      imported_failures: 0,
      summary: summaryTurn.output,
      transcript,
      final_synthesis: summaryTurn.output,
    };
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
  if (name === "provider_list") {
    const registry = await loadProviderRegistry(env);
    return { providers: registry.providers, warnings: registry.warnings };
  }
  if (name === "provider_status") {
    const registry = await loadProviderRegistry(env);
    const providerId = normalizeProviderId(args.provider_id);
    return providerRegistryMap(registry).get(providerId) || buildProviderRecord(env, providerId);
  }
  if (name === "provider_connect_start") {
    const providerId = normalizeProviderId(args.provider_id);
    const spec = providerCatalogEntry(env, providerId);
    const requestedAuthMethod = trimmed(args.auth_method, spec.default_auth_method);
    const oauthMetadata = providerOauthMetadata(env, spec);
    if (providerId === "mock" && requestedAuthMethod === "none/mock") {
      const record = buildProviderRecord(env, "mock", { auth_method: "none/mock", status: "connected", model_list: ["mock-model"] });
      await upsertProviderConnection(env, record);
      return { ...record, message: "Mock provider connected for tests." };
    }
    if (["oauth", "bearer_token"].includes(requestedAuthMethod) && oauthMetadata.configured) {
      const { verifier, challenge } = await buildPkcePair();
      const flowId = `flow-${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
      const stateValue = `${flowId}.${base64UrlEncode(crypto.getRandomValues(new Uint8Array(18)))}`;
      const authorizationUrl = buildProviderAuthorizationUrl(env, spec, oauthMetadata, {
        flowId,
        stateValue,
        codeChallenge: challenge,
      });
      const flow = {
        flow_id: flowId,
        provider_id: spec.provider_id,
        auth_method: "oauth",
        status: "oauth_required",
        authorization_url: authorizationUrl,
        redirect_url: oauthMetadata.redirect_uri,
        state: "",
        state_hash: await sha256Hex(stateValue),
        code_challenge: challenge,
        code_challenge_method: "S256",
        callback_received_at: null,
        failure_reason: "",
        metadata: {
          runtime_mode: "cloud_native_worker_lab_v0",
          authorization_endpoint: oauthMetadata.authorization_endpoint,
          token_endpoint: oauthMetadata.token_endpoint,
          client_id: oauthMetadata.client_id,
          scopes: oauthMetadata.scopes,
          pkce_enabled: true,
          code_verifier: verifier,
          code_verifier_present: Boolean(verifier),
          token_storage_supported: oauthMetadata.token_storage_supported,
        },
        created_at: nowIso(),
        updated_at: nowIso(),
      };
      await upsertProviderAuthFlow(env, flow);
      const record = buildProviderRecord(env, providerId, { auth_method: "oauth", status: "oauth_required" });
      const saved = await upsertProviderConnection(env, record, {
        metadata: {
          ...(record.metadata || {}),
          oauth_enabled: true,
          oauth_redirect_uri: oauthMetadata.redirect_uri,
          oauth_client_id_configured: true,
          oauth_client_secret_configured: oauthMetadata.client_secret_configured,
          oauth_missing_config_names: oauthMetadata.missing_config_names,
          oauth_token_storage_supported: oauthMetadata.token_storage_supported,
        },
      });
      return {
        ...buildProviderRecord(env, providerId, saved),
        authorization_url: authorizationUrl,
        flow: publicProviderFlow(flow),
        message: "Provider connect start produced a real OAuth authorization URL.",
      };
    }
    if (["oauth", "bearer_token"].includes(requestedAuthMethod) && spec.supports_api_key) {
      const record = buildProviderRecord(env, providerId, {
        auth_method: "api_key",
        status: "api_key_required",
        failure_reason: "oauth_not_configured",
      });
      const saved = await upsertProviderConnection(env, record);
      return {
        ...buildProviderRecord(env, providerId, saved),
        auth_method: "api_key",
        status: "api_key_required",
        provider_status: "api_key_required",
        message: "OAuth is not configured for this provider. Use the secure setup page and Cloudflare secret instructions.",
      };
    }
    if (requestedAuthMethod === "oauth" || requestedAuthMethod === "bearer_token") {
      const record = buildProviderRecord(env, providerId);
      return {
        ...record,
        status: spec.oauth_missing_status || "provider_required",
        provider_status: spec.oauth_missing_status || "provider_required",
        failure_reason: providerDefaultFailureReason(spec, spec.oauth_missing_status || "provider_required", oauthMetadata, providerSecretState(env, spec)),
        message: providerStatusMessage({
          ...record,
          status: spec.oauth_missing_status || "provider_required",
          provider_status: spec.oauth_missing_status || "provider_required",
          failure_reason: providerDefaultFailureReason(spec, spec.oauth_missing_status || "provider_required", oauthMetadata, providerSecretState(env, spec)),
        }),
      };
    }
    const record = buildProviderRecord(env, providerId, {
      auth_method: requestedAuthMethod,
      status: requestedAuthMethod === "api_key" && !buildProviderRecord(env, providerId).configured ? "api_key_required" : "",
    });
    const status = record.configured ? "connected" : "api_key_required";
    const saved = await upsertProviderConnection(env, record, {
      status,
    });
    return {
      ...buildProviderRecord(env, providerId, saved),
      status,
      provider_status: status,
      message: "Provider connect start returned the secure Mystic LAB setup page.",
    };
  }
  if (name === "provider_connect_callback_status") {
    const providerId = normalizeProviderId(args.provider_id);
    const flow = await loadProviderAuthFlow(env, args.flow_id.trim());
    if (!flow || normalizeProviderId(flow.provider_id) !== providerId) {
      throw new Error(`Unknown provider auth flow: ${args.flow_id}`);
    }
    const registry = await loadProviderRegistry(env);
    return {
      provider: providerRegistryMap(registry).get(providerId) || buildProviderRecord(env, providerId),
      flow: publicProviderFlow(flow),
      callback_received: Boolean(flow.callback_received_at),
    };
  }
  if (name === "provider_configure_secret_instructions") {
    const providerId = normalizeProviderId(args.provider_id);
    const spec = providerCatalogEntry(env, providerId);
    const record = buildProviderRecord(env, providerId);
    return {
      ...record,
      secret_names: [...spec.secret_names],
      required_secret_names: [...spec.required_secret_names],
      optional_secret_names: [...spec.optional_secret_names],
      instructions: providerManualSecretInstructions(spec),
      direct_secret_write_supported: false,
      runtime_mode: "cloud_native_worker_lab_v0",
    };
  }
  if (name === "provider_verify") {
    const providerId = normalizeProviderId(args.provider_id);
    const existing = await supabaseSelectOne(env, "provider_connections", { provider_id: `eq.${providerId}` });
    const tokenRow = providerId === "google_vertex_ai" ? await loadProviderOauthToken(env, providerId) : null;
    if (existing && trimmed(existing.status) === "disconnected") {
      return {
        ...buildProviderRecord(env, providerId, existing),
        verified_at: nowIso(),
        message: "Provider remains disconnected until an explicit reconnect.",
      };
    }
    const record = buildProviderRecord(env, providerId, existing || {});
    const nextStatus =
      providerId === "google_vertex_ai"
        ? tokenRow && trimmed(tokenRow.status) === "connected"
          ? "connected"
          : record.status === "connected"
            ? "token_storage_required"
            : record.status
        : record.status;
    const saved = await upsertProviderConnection(env, record, {
      status: nextStatus,
      auth_method: record.auth_method,
      model_list: record.model_list,
      last_verified_at: nowIso(),
      failure_reason: nextStatus === "token_storage_required" ? "token_storage_required" : "",
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_token_recorded: Boolean(tokenRow),
        oauth_token_status: tokenRow ? trimmed(tokenRow.status) : "",
        oauth_token_metadata_safe:
          tokenRow && tokenRow.metadata_safe && typeof tokenRow.metadata_safe === "object" ? tokenRow.metadata_safe : {},
      },
    });
    return {
      ...buildProviderRecord(env, providerId, saved),
      connection_id: saved.connection_id,
      verified_at: saved.last_verified_at,
      message: providerStatusMessage(buildProviderRecord(env, providerId, saved)),
    };
  }
  if (name === "provider_disconnect") {
    const providerId = normalizeProviderId(args.provider_id);
    const existing = (await supabaseSelectOne(env, "provider_connections", { provider_id: `eq.${providerId}` })) || {};
    const metadata = existing.metadata && typeof existing.metadata === "object" && !Array.isArray(existing.metadata) ? existing.metadata : {};
    const record = buildProviderRecord(env, providerId, { ...existing, status: "disconnected" });
    const saved = await upsertProviderConnection(env, record, {
      status: "disconnected",
      metadata: { ...metadata, disconnected_at: nowIso() },
    });
    return {
      ...buildProviderRecord(env, providerId, saved),
      connection_id: saved.connection_id,
      message: "Provider was marked disconnected. Existing secrets were not deleted.",
    };
  }
  if (name === "provider_model_list") {
    const registry = await loadProviderRegistry(env);
    const providerId = normalizeProviderId(args.provider_id);
    const record = providerRegistryMap(registry).get(providerId) || buildProviderRecord(env, providerId);
    if (record.status !== "connected") {
      return {
        provider_id: record.provider_id,
        provider_type: record.provider_type,
        auth_method: record.auth_method,
        status: record.status,
        model_list: [],
        setup_url: record.setup_url,
        setup_instructions: record.setup_instructions,
      };
    }
    return {
      provider_id: record.provider_id,
      provider_type: record.provider_type,
      auth_method: record.auth_method,
      status: record.status,
      model_list: record.model_list,
    };
  }
  if (name === "provider_call_test") {
    const providerId = normalizeProviderId(args.provider_id);
    const registry = await loadProviderRegistry(env);
    const record = providerRegistryMap(registry).get(providerId) || buildProviderRecord(env, providerId);
    const result = await runCloudProviderCall({
      env,
      providerRecord: record,
      toolName: "provider_call_test",
      sessionId: "",
      agentRole: "ProviderTest",
      prompt: trimmed(args.prompt, "ping"),
      metadata: { test_only: providerId === "mock" },
    });
    return {
      provider_id: record.provider_id,
      provider_type: record.provider_type,
      auth_method: record.auth_method,
      status: result.status,
      model: result.model,
      output: result.output_text,
      output_text: result.output_text,
      latency_ms: result.latency_ms,
      usage: result.raw_usage_safe,
      error_type: result.error_type,
      message: result.error_message_safe,
      error_message_safe: result.error_message_safe,
      call_id: result.call_id,
      storage_ref: result.storage_ref,
      setup_url: record.setup_url,
      connect_url: record.connect_url,
      setup_instructions: record.setup_instructions,
      test_only: providerId === "mock",
    };
  }
  if (name === "create_lab_scene") {
    const sessionBundle = await loadCloudBundle(env, args.session_id.trim());
    if (!sessionBundle) {
      throw new Error(`Unknown session_id: ${args.session_id}`);
    }
    const sceneId = cloudId("scene");
    const scene = {
      scene_id: sceneId,
      session_id: sessionBundle.session.session_id,
      domain: sessionBundle.session.domain,
      title: args.title.trim(),
      description: trimmed(args.description),
      units: objectMapping(args.units),
      parameters: objectMapping(args.parameters),
      attached_simulations: [],
      evidence_refs: [],
      report_refs: [],
      metadata: { scene_adapter: "scene.three_json", ...objectMapping(args.metadata) },
      artifact_paths: cloudSceneArtifactPaths(supabase.schema, sceneId),
      exports_json: {},
      report_markdown: "",
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    const sceneBundle = { scene, objects: [], simulations: [] };
    const paths = await saveCloudSceneBundle(env, sceneBundle, undefined, cloudSceneMutationActivity(name, sceneBundle));
    return { scene_id: sceneId, session_id: scene.session_id, paths, scene };
  }
  if (name === "get_lab_scene") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    return cloudScenePayload(sceneBundle);
  }
  if (name === "add_lab_object") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const sceneObject = normalizeSceneObjectPayload(sceneBundle.scene.scene_id, args.object);
    sceneBundle.objects.push(sceneObject);
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return { scene_id: sceneBundle.scene.scene_id, object_id: sceneObject.id, object: sceneObject, paths };
  }
  if (name === "update_lab_object") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const index = sceneBundle.objects.findIndex((item) => item.id === args.object_id.trim());
    if (index === -1) {
      throw new Error(`Unknown scene object id: ${args.object_id}`);
    }
    const updated = normalizeSceneObjectPayload(sceneBundle.scene.scene_id, args.patch, sceneBundle.objects[index]);
    sceneBundle.objects[index] = updated;
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return { scene_id: sceneBundle.scene.scene_id, object_id: updated.id, object: updated, paths };
  }
  if (name === "remove_lab_object") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const objectId = args.object_id.trim();
    const existing = sceneBundle.objects.find((item) => item.id === objectId);
    if (!existing) {
      throw new Error(`Unknown scene object id: ${args.object_id}`);
    }
    sceneBundle.objects = sceneBundle.objects.filter((item) => item.id !== objectId);
    sceneBundle.simulations = sceneBundle.simulations.map((item) => ({
      ...item,
      attached_object_ids: item.attached_object_ids.filter((attachedId) => attachedId !== objectId),
      updated_at: nowIso(),
    }));
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return { scene_id: sceneBundle.scene.scene_id, removed_object_id: objectId, paths };
  }
  if (name === "set_lab_parameters") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    sceneBundle.scene.parameters = { ...sceneBundle.scene.parameters, ...objectMapping(args.parameters) };
    if (args.units !== undefined) {
      sceneBundle.scene.units = { ...sceneBundle.scene.units, ...objectMapping(args.units) };
    }
    if (args.metadata !== undefined) {
      sceneBundle.scene.metadata = { ...sceneBundle.scene.metadata, ...objectMapping(args.metadata) };
    }
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return {
      scene_id: sceneBundle.scene.scene_id,
      parameters: sceneBundle.scene.parameters,
      units: sceneBundle.scene.units,
      paths,
    };
  }
  if (name === "run_lab_simulation") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const result = runCloudSceneAdapter(args.adapter_id.trim(), sceneBundle, objectMapping(args.inputs));
    const objectIds = asStringArray(args.inputs.object_ids);
    const singleObjectId = trimmed(args.inputs.object_id);
    const simulation = {
      simulation_id: cloudId("sim"),
      scene_id: sceneBundle.scene.scene_id,
      session_id: sceneBundle.scene.session_id,
      adapter_id: args.adapter_id.trim(),
      status: result.status,
      inputs: objectMapping(args.inputs),
      outputs: objectMapping(result.outputs),
      evidence: objectMapping(result.evidence),
      warnings: asStringArray(result.warnings),
      errors: asStringArray(result.errors),
      attached_object_ids: objectIds.length ? objectIds : singleObjectId ? [singleObjectId] : [],
      metadata: {
        engine_status: result.status,
        scene_adapter: sceneBundle.scene.metadata.scene_adapter || "scene.three_json",
      },
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    sceneBundle.simulations.push(simulation);
    const simulationRef = `simulation:${simulation.simulation_id}`;
    if (!sceneBundle.scene.evidence_refs.includes(simulationRef)) {
      sceneBundle.scene.evidence_refs.push(simulationRef);
    }
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return {
      scene_id: sceneBundle.scene.scene_id,
      simulation_id: simulation.simulation_id,
      status: simulation.status,
      result,
      paths,
    };
  }
  if (name === "attach_simulation_to_scene") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const simulation = sceneBundle.simulations.find((item) => item.simulation_id === args.simulation_id.trim());
    if (!simulation) {
      throw new Error(`Unknown simulation_id: ${args.simulation_id}`);
    }
    const selectedObjectIds = asStringArray(args.object_ids);
    simulation.attached_object_ids = selectedObjectIds.length ? selectedObjectIds : simulation.attached_object_ids;
    if (!sceneBundle.scene.attached_simulations.includes(simulation.simulation_id)) {
      sceneBundle.scene.attached_simulations.push(simulation.simulation_id);
    }
    for (const ref of asStringArray(args.evidence_refs)) {
      if (!sceneBundle.scene.evidence_refs.includes(ref)) {
        sceneBundle.scene.evidence_refs.push(ref);
      }
    }
    for (const ref of asStringArray(args.report_refs)) {
      if (!sceneBundle.scene.report_refs.includes(ref)) {
        sceneBundle.scene.report_refs.push(ref);
      }
    }
    if (args.apply_object_updates === true && simulation.status === "completed") {
      applyCloudSimulationToScene(sceneBundle, simulation, simulation.attached_object_ids);
    }
    simulation.updated_at = nowIso();
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return {
      scene_id: sceneBundle.scene.scene_id,
      simulation_id: simulation.simulation_id,
      attached_object_ids: simulation.attached_object_ids,
      attached_simulations: sceneBundle.scene.attached_simulations,
      paths,
    };
  }
  if (name === "export_lab_snapshot") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    const exportResult = exportCloudScene(sceneBundle, args.adapter_id.trim(), args.include_simulations === true);
    let paths = sceneBundle.scene.artifact_paths;
    if (exportResult.status === "completed") {
      sceneBundle.scene.exports_json[args.adapter_id.trim()] = exportResult.outputs.snapshot;
      sceneBundle.scene.updated_at = nowIso();
      paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    }
    return {
      scene_id: sceneBundle.scene.scene_id,
      adapter_id: args.adapter_id.trim(),
      status: exportResult.status,
      snapshot: exportResult.outputs ? exportResult.outputs.snapshot : null,
      paths,
    };
  }
  if (name === "generate_lab_report") {
    const sceneBundle = await loadCloudSceneBundle(env, args.scene_id.trim());
    if (!sceneBundle) {
      throw new Error(`Unknown scene_id: ${args.scene_id}`);
    }
    sceneBundle.scene.report_markdown = renderCloudSceneReport(sceneBundle);
    const reportPath = sceneBundle.scene.artifact_paths.report || cloudSceneArtifactPaths(supabase.schema, sceneBundle.scene.scene_id).report;
    if (!sceneBundle.scene.report_refs.includes(reportPath)) {
      sceneBundle.scene.report_refs.push(reportPath);
    }
    sceneBundle.simulations = sceneBundle.simulations.map((item) => {
      const reportRefs = Array.isArray(item.metadata.report_refs) ? item.metadata.report_refs.map(String) : [];
      if (!reportRefs.includes(reportPath)) {
        reportRefs.push(reportPath);
      }
      return {
        ...item,
        metadata: { ...item.metadata, report_refs: reportRefs },
        updated_at: nowIso(),
      };
    });
    sceneBundle.scene.updated_at = nowIso();
    const paths = await saveCloudSceneBundle(env, sceneBundle, args.expected_revision, cloudSceneMutationActivity(name, sceneBundle));
    return {
      scene_id: sceneBundle.scene.scene_id,
      report_path: paths.report,
      markdown: sceneBundle.scene.report_markdown,
      summary: {
        objects: args.include_objects ? sceneBundle.objects.length : 0,
        simulations: args.include_simulations ? sceneBundle.simulations.length : 0,
        attached_simulations: sceneBundle.scene.attached_simulations.length,
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
    return jsonRpcResponse(requestId, { tools: CLOUD_TOOL_DEFINITIONS });
  }
  if (method !== "tools/call") {
    return jsonRpcError(requestId, -32601, `Unknown method: ${method}`);
  }
  const params = payload.params || {};
  const name = String(params.name || "");
  const args = params.arguments || {};
  if (!CLOUD_TOOL_NAMES.has(name)) {
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
  const codeId = await randomToken();
  const payload = {
    iss: state.issuer,
    aud: state.resource,
    jti: codeId,
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: scope || DEFAULT_SCOPES,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    exp: Math.floor(Date.now() / 1000) + 600,
    iat: Math.floor(Date.now() / 1000),
    type: "authorization_code",
  };
  const code = await signEnvelope(payload, state.signingSecret);
  await storeAuthorizationCode(codeId, payload, state);
  return code;
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

async function exchangeAuthorizationCode({ code, clientId, redirectUri, codeVerifier, state, requireStoredCode = false }) {
  const signedPayload = await verifyEnvelope(code, state.signingSecret);
  let payload = signedPayload;
  if (signedPayload?.jti) {
    const storedPayload = await loadAuthorizationCode(signedPayload.jti, state);
    payload = storedPayload || (!requireStoredCode ? signedPayload : null);
  }
  if (!payload || payload.type !== "authorization_code") {
    return { ok: false, error: "invalid_grant", error_description: "Authorization code is invalid." };
  }
  if (payload.exp <= Math.floor(Date.now() / 1000)) {
    if (payload.jti) {
      await deleteAuthorizationCode(payload.jti, state);
    }
    return { ok: false, error: "invalid_grant", error_description: "Authorization code expired." };
  }
  if (payload.client_id !== clientId || payload.redirect_uri !== redirectUri) {
    return { ok: false, error: "invalid_grant", error_description: "Authorization code client binding mismatch." };
  }
  if (payload.code_challenge_method !== "S256" || (await sha256Base64Url(codeVerifier)) !== payload.code_challenge) {
    return { ok: false, error: "invalid_grant", error_description: "PKCE verification failed." };
  }
  if (payload.jti) {
    await deleteAuthorizationCode(payload.jti, state);
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

async function randomToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64UrlEncodeBytes(bytes);
}

function usesCacheAuthorizationCodeStore() {
  return Boolean(globalThis.caches && caches.default);
}

function base64UrlEncodeBytes(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function authorizationCodeCacheKey(codeId, state) {
  return `${state.issuer}/.well-known/mystic/oauth-codes/${encodeURIComponent(codeId)}`;
}

async function storeAuthorizationCode(code, payload, state) {
  const cacheKey = authorizationCodeCacheKey(code, state);
  const record = JSON.stringify(payload);
  if (usesCacheAuthorizationCodeStore()) {
    await caches.default.put(
      new Request(cacheKey, { method: "GET" }),
      new Response(record, {
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "private, max-age=600",
        },
      }),
    );
    return;
  }
  authorizationCodeMemoryStore.set(cacheKey, record);
}

async function loadAuthorizationCode(code, state) {
  const cacheKey = authorizationCodeCacheKey(code, state);
  let record = "";
  if (usesCacheAuthorizationCodeStore()) {
    const response = await caches.default.match(new Request(cacheKey, { method: "GET" }));
    if (!response) {
      return null;
    }
    record = await response.text();
  } else {
    record = authorizationCodeMemoryStore.get(cacheKey) || "";
    if (!record) {
      return null;
    }
  }
  try {
    return JSON.parse(record);
  } catch {
    return null;
  }
}

async function deleteAuthorizationCode(code, state) {
  const cacheKey = authorizationCodeCacheKey(code, state);
  if (usesCacheAuthorizationCodeStore()) {
    await caches.default.delete(new Request(cacheKey, { method: "GET" }));
    return;
  }
  authorizationCodeMemoryStore.delete(cacheKey);
}

async function authorizeMcpRequest(request, state, env = {}) {
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
  const consoleServiceToken = String(env.MYSTIC_CONSOLE_SERVICE_TOKEN || "").trim();
  if (consoleServiceToken && constantTimeEqual(token, consoleServiceToken)) {
    return { ok: true, auth: { type: "console_service", scope: DEFAULT_SCOPES, sub: "mystic-console" } };
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

function authorizeErrorPage(title, message) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>${title}</title>
    <style>
      body { background:#0b1020; color:#e7ecf3; font-family:ui-sans-serif,system-ui,sans-serif; padding:40px; }
      main { max-width:720px; margin:0 auto; background:#111827; border:1px solid #243041; border-radius:16px; padding:24px; }
      code { font-family:ui-monospace,SFMono-Regular,monospace; }
      p.error { color:#fca5a5; }
    </style>
  </head>
  <body>
    <main>
      <h1>${title}</h1>
      <p class="error">${message}</p>
    </main>
  </body>
</html>`;
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
      if (validationError === "Redirect URI is not allowed.") {
        return htmlResponse(authorizeErrorPage("Mystic MCP OAuth", validationError), 200);
      }
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

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function providerPage(title, content) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>${escapeHtml(title)}</title>
    <style>
      body { background:#f3f4f6; color:#111827; font-family:ui-sans-serif,system-ui,sans-serif; margin:0; padding:32px 20px; }
      main { max-width:900px; margin:0 auto; background:white; border:1px solid #d1d5db; border-radius:18px; padding:28px; box-shadow:0 18px 40px rgba(15,23,42,.08); }
      h1, h2 { margin-top:0; }
      a { color:#1d4ed8; }
      code, pre { font-family:ui-monospace,SFMono-Regular,monospace; background:#f3f4f6; border-radius:8px; }
      code { padding:2px 6px; }
      pre { padding:14px; overflow:auto; }
      ul { padding-left:20px; }
      .card { border:1px solid #d1d5db; border-radius:14px; padding:18px; margin:14px 0; background:#fafafa; }
      .status { display:inline-block; border-radius:999px; padding:4px 10px; background:#e5e7eb; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.03em; }
      .warn { color:#991b1b; }
      .muted { color:#4b5563; }
    </style>
  </head>
  <body>
    <main>${content}</main>
  </body>
</html>`;
}

function renderProviderListPage(registry) {
  const cards = registry.providers
    .map(
      (provider) => `<section class="card">
        <h2>${escapeHtml(provider.provider_id)}</h2>
        <p><span class="status">${escapeHtml(provider.status)}</span></p>
        <p><strong>Auth mode:</strong> <code>${escapeHtml(provider.auth_mode || provider.auth_method)}</code></p>
        <p class="muted">Configured: <strong>${provider.configured ? "true" : "false"}</strong></p>
        <p>
          <a href="${escapeHtml(provider.connect_url)}">Connect</a> ·
          <a href="${escapeHtml(provider.setup_url)}">Setup</a> ·
          <a href="${escapeHtml(provider.status_url)}">Status JSON</a>
        </p>
      </section>`,
    )
    .join("");
  return providerPage(
    "Mystic LAB Providers",
    `<h1>Mystic LAB Provider Connect</h1>
     <p class="muted">These pages show provider status, auth mode, and required secret names without exposing any stored secret values.</p>
     ${cards}`,
  );
}

function renderProviderSetupPage(provider, spec) {
  const commands = provider.required_secret_names.map((name) => `wrangler secret put ${name} --name mystic`).join("\n");
  return providerPage(
    `Setup ${provider.provider_id}`,
    `<h1>Setup ${escapeHtml(provider.provider_id)}</h1>
     <p><span class="status">${escapeHtml(provider.provider_status)}</span></p>
     <p><strong>Required auth method:</strong> <code>${escapeHtml(provider.auth_mode || provider.auth_method)}</code></p>
     <p>${escapeHtml(provider.setup_instructions)}</p>
     <div class="card">
       <h2>Required Cloudflare secrets</h2>
       <ul>${provider.required_secret_names.map((name) => `<li><code>${escapeHtml(name)}</code></li>`).join("") || "<li>None</li>"}</ul>
       <p class="muted">Configured secret names: ${provider.configured_secret_names.map((name) => `<code>${escapeHtml(name)}</code>`).join(", ") || "none"}</p>
       <p class="muted">Missing secret names: ${provider.missing_secret_names.map((name) => `<code>${escapeHtml(name)}</code>`).join(", ") || "none"}</p>
     </div>
     <div class="card">
       <h2>Manual setup</h2>
       <p>Mystic LAB does not write provider secrets from this page unless dedicated encrypted secret-write infrastructure is configured. Use the Cloudflare secret commands below.</p>
       <pre>${escapeHtml(commands || "# No required secrets for this provider")}</pre>
       ${
         spec.external_setup_url
           ? `<p><a href="${escapeHtml(spec.external_setup_url)}" target="_blank" rel="noreferrer">Open provider key setup page</a></p>`
           : ""
       }
     </div>
     <p><a href="/providers">Back to providers</a></p>`,
  );
}

function renderProviderConnectPage(provider, spec, oauthMetadata, flow) {
  const flowBlock = flow
    ? `<div class="card">
         <h2>Latest flow</h2>
         <p><strong>Flow ID:</strong> <code>${escapeHtml(flow.flow_id)}</code></p>
       <p><strong>Status:</strong> <code>${escapeHtml(flow.status)}</code></p>
       <p><strong>Callback received:</strong> ${flow.callback_received_at ? "true" : "false"}</p>
      </div>`
    : "";
  const oauthMissingMessage = spec.supports_api_key
    ? "Mystic LAB will not pretend OAuth exists for this provider. Use the secure setup page to configure the required provider credentials."
    : "Mystic LAB will not pretend OAuth exists for this provider. Use the secure setup page to configure the required provider metadata.";
  const oauthBlock = oauthMetadata.configured
    ? `<div class="card">
         <h2>OAuth ready</h2>
         <p>OAuth metadata is configured for this provider. Start the real connection from <code>provider_connect_start</code> to generate a one-time authorization URL.</p>
         <p><strong>Authorization endpoint:</strong> <code>${escapeHtml(oauthMetadata.authorization_endpoint)}</code></p>
         <p><strong>Redirect URI:</strong> <code>${escapeHtml(oauthMetadata.redirect_uri)}</code></p>
       </div>`
    : `<div class="card">
         <h2>OAuth not configured</h2>
         <p class="warn">${escapeHtml(oauthMissingMessage)}</p>
         <p><a href="${escapeHtml(provider.setup_url)}">Open secure setup page</a></p>
       </div>`;
  return providerPage(
    `Connect ${provider.provider_id}`,
    `<h1>Connect ${escapeHtml(provider.provider_id)}</h1>
     <p><span class="status">${escapeHtml(provider.provider_status)}</span></p>
     <p><strong>Current auth mode:</strong> <code>${escapeHtml(provider.auth_mode || provider.auth_method)}</code></p>
     ${oauthBlock}
     ${flowBlock}
     <p class="muted">This page never displays stored secret values.</p>
     <p><a href="/providers">Back to providers</a></p>`,
  );
}

function renderProviderCallbackPage(provider, flow, message) {
  return providerPage(
    `OAuth callback ${provider.provider_id}`,
    `<h1>OAuth callback recorded</h1>
     <p><span class="status">${escapeHtml(flow.status)}</span></p>
     <p>${escapeHtml(message)}</p>
     <div class="card">
       <p><strong>Provider:</strong> <code>${escapeHtml(provider.provider_id)}</code></p>
       <p><strong>Flow ID:</strong> <code>${escapeHtml(flow.flow_id)}</code></p>
       <p><strong>Provider status:</strong> <code>${escapeHtml(provider.provider_status)}</code></p>
     </div>
     <p class="muted">No authorization code, token, or secret value is displayed on this page.</p>
     <p><a href="${escapeHtml(provider.connect_url)}">Back to provider connect page</a></p>`,
  );
}

async function handleProviderOauthCallback(request, env) {
  const sourceUrl = new URL(request.url);
  const flowId = trimmed(sourceUrl.searchParams.get("flow_id"));
  const providerId = normalizeProviderId(trimmed(sourceUrl.searchParams.get("provider_id")));
  const callbackState = trimmed(sourceUrl.searchParams.get("state"));
  const callbackError = trimmed(sourceUrl.searchParams.get("error"));
  const callbackCode = trimmed(sourceUrl.searchParams.get("code"));
  if (!flowId) {
    return htmlResponse(providerPage("Provider callback error", "<h1>Provider callback error</h1><p class=\"warn\">Missing flow_id.</p>"), 400);
  }
  const flow = await loadProviderAuthFlow(env, flowId);
  if (!flow) {
    return htmlResponse(providerPage("Provider callback error", "<h1>Provider callback error</h1><p class=\"warn\">Unknown provider auth flow.</p>"), 404);
  }
  const resolvedProviderId = normalizeProviderId(providerId || flow.provider_id);
  if (resolvedProviderId !== normalizeProviderId(flow.provider_id)) {
    return htmlResponse(providerPage("Provider callback error", "<h1>Provider callback error</h1><p class=\"warn\">Provider mismatch.</p>"), 400);
  }
  if (!callbackState && trimmed(flow.state_hash)) {
    const failedFlow = {
      ...flow,
      status: "failed",
      failure_reason: "oauth_state_missing",
      updated_at: nowIso(),
    };
    await upsertProviderAuthFlow(env, failedFlow);
    return htmlResponse(providerPage("Provider callback error", "<h1>Provider callback error</h1><p class=\"warn\">OAuth state is required.</p>"), 400);
  }
  if (callbackState && trimmed(flow.state_hash)) {
    const callbackStateHash = await sha256Hex(callbackState);
    if (callbackStateHash !== trimmed(flow.state_hash)) {
      const failedFlow = {
        ...flow,
        status: "failed",
        failure_reason: "oauth_state_mismatch",
        updated_at: nowIso(),
      };
      await upsertProviderAuthFlow(env, failedFlow);
      return htmlResponse(providerPage("Provider callback error", "<h1>Provider callback error</h1><p class=\"warn\">OAuth state validation failed.</p>"), 400);
    }
  }
  const spec = providerCatalogEntry(env, resolvedProviderId);
  const oauthMetadata = providerOauthMetadata(env, spec);
  const nextStatus = callbackError ? "failed" : "callback_received";
  const updatedFlow = {
    ...flow,
    status: nextStatus,
    callback_received_at: nowIso(),
    failure_reason: callbackError || "",
    metadata: {
      ...(flow.metadata && typeof flow.metadata === "object" ? flow.metadata : {}),
      authorization_code_received: Boolean(callbackCode),
      oauth_error: callbackError || "",
    },
    updated_at: nowIso(),
  };
  await upsertProviderAuthFlow(env, updatedFlow);
  const existing = (await supabaseSelectOne(env, "provider_connections", { provider_id: `eq.${resolvedProviderId}` })) || {};
  const record = buildProviderRecord(env, resolvedProviderId, existing);
  if (callbackError) {
    const failedConnection = await upsertProviderConnection(env, record, {
      auth_method: "oauth",
      status: "auth_failed",
      failure_reason: callbackError,
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_callback_received_at: nowIso(),
        oauth_authorization_code_received: Boolean(callbackCode),
        oauth_token_storage_supported: oauthMetadata.token_storage_supported,
      },
      last_verified_at: nowIso(),
    });
    const provider = buildProviderRecord(env, resolvedProviderId, failedConnection);
    return htmlResponse(
      renderProviderCallbackPage(provider, publicProviderFlow(updatedFlow), `Provider returned OAuth error: ${callbackError}`),
      400,
    );
  }
  if (!callbackCode) {
    const failedFlow = {
      ...updatedFlow,
      status: "failed",
      failure_reason: "oauth_code_missing",
      updated_at: nowIso(),
    };
    await upsertProviderAuthFlow(env, failedFlow);
    const failedConnection = await upsertProviderConnection(env, record, {
      auth_method: "oauth",
      status: "auth_failed",
      failure_reason: "oauth_code_missing",
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_callback_received_at: nowIso(),
        oauth_authorization_code_received: false,
        oauth_token_storage_supported: oauthMetadata.token_storage_supported,
      },
      last_verified_at: nowIso(),
    });
    const provider = buildProviderRecord(env, resolvedProviderId, failedConnection);
    return htmlResponse(
      renderProviderCallbackPage(provider, publicProviderFlow(failedFlow), "Provider callback did not include an authorization code."),
      400,
    );
  }
  if (!oauthMetadata.token_storage_supported) {
    const tokenStorageFlow = {
      ...updatedFlow,
      status: "callback_received",
      failure_reason: "token_storage_required",
      updated_at: nowIso(),
    };
    await upsertProviderAuthFlow(env, tokenStorageFlow);
    const waitingConnection = await upsertProviderConnection(env, record, {
      auth_method: "oauth",
      status: "token_storage_required",
      failure_reason: "token_storage_required",
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_callback_received_at: nowIso(),
        oauth_authorization_code_received: true,
        oauth_token_storage_supported: false,
      },
      last_verified_at: nowIso(),
    });
    const provider = buildProviderRecord(env, resolvedProviderId, waitingConnection);
    return htmlResponse(
      renderProviderCallbackPage(
        provider,
        publicProviderFlow(tokenStorageFlow),
        "Mystic LAB received the OAuth callback, but encrypted server-side token storage is required before provider access can be completed.",
      ),
      200,
    );
  }

  const tokenRequestBody = new URLSearchParams();
  tokenRequestBody.set("grant_type", "authorization_code");
  tokenRequestBody.set("code", callbackCode);
  tokenRequestBody.set("redirect_uri", oauthMetadata.redirect_uri);
  tokenRequestBody.set("client_id", oauthMetadata.client_id);
  const codeVerifier =
    updatedFlow.metadata && typeof updatedFlow.metadata === "object" ? trimmed(updatedFlow.metadata.code_verifier) : "";
  if (codeVerifier) {
    tokenRequestBody.set("code_verifier", codeVerifier);
  }
  const clientSecret = trimmed(env[`${spec.oauth_env_prefix}_CLIENT_SECRET`]);
  if (clientSecret) {
    tokenRequestBody.set("client_secret", clientSecret);
  }
  let tokenPayload = null;
  try {
    const tokenResponse = await fetch(oauthMetadata.token_endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        accept: "application/json",
      },
      body: tokenRequestBody.toString(),
    });
    if (!tokenResponse.ok) {
      throw new Error(`token_exchange_http_${tokenResponse.status}`);
    }
    tokenPayload = await tokenResponse.json();
  } catch (_) {
    const failedFlow = {
      ...updatedFlow,
      status: "failed",
      failure_reason: "oauth_token_exchange_failed",
      updated_at: nowIso(),
    };
    await upsertProviderAuthFlow(env, failedFlow);
    const failedConnection = await upsertProviderConnection(env, record, {
      auth_method: "oauth",
      status: "auth_failed",
      failure_reason: "oauth_token_exchange_failed",
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_callback_received_at: nowIso(),
        oauth_authorization_code_received: true,
        oauth_token_storage_supported: true,
      },
      last_verified_at: nowIso(),
    });
    const provider = buildProviderRecord(env, resolvedProviderId, failedConnection);
    return htmlResponse(
      renderProviderCallbackPage(provider, publicProviderFlow(failedFlow), "OAuth token exchange failed. Reconnect the provider and retry."),
      400,
    );
  }
  const accessToken = trimmed(tokenPayload && tokenPayload.access_token);
  if (!accessToken) {
    const failedFlow = {
      ...updatedFlow,
      status: "failed",
      failure_reason: "oauth_token_exchange_failed",
      updated_at: nowIso(),
    };
    await upsertProviderAuthFlow(env, failedFlow);
    const failedConnection = await upsertProviderConnection(env, record, {
      auth_method: "oauth",
      status: "auth_failed",
      failure_reason: "oauth_token_exchange_failed",
      metadata: {
        ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
        oauth_callback_received_at: nowIso(),
        oauth_authorization_code_received: true,
        oauth_token_storage_supported: true,
      },
      last_verified_at: nowIso(),
    });
    const provider = buildProviderRecord(env, resolvedProviderId, failedConnection);
    return htmlResponse(
      renderProviderCallbackPage(provider, publicProviderFlow(failedFlow), "OAuth token exchange did not return an access token."),
      400,
    );
  }

  const callbackReceivedConnection = await upsertProviderConnection(env, record, {
    auth_method: "oauth",
    status: "oauth_callback_received",
    failure_reason: "",
    metadata: {
      ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
      oauth_callback_received_at: nowIso(),
      oauth_authorization_code_received: true,
      oauth_token_storage_supported: true,
    },
    last_verified_at: nowIso(),
  });
  const scopeText = trimmed(tokenPayload.scope);
  const oauthTokenRow = await upsertProviderOauthToken(env, {
    token_id: trimmed((await loadProviderOauthToken(env, resolvedProviderId))?.token_id, `oauth-token-${resolvedProviderId}`),
    provider_id: resolvedProviderId,
    connection_id: callbackReceivedConnection.connection_id,
    encrypted_access_token: await encryptProviderTokenValue(env, accessToken),
    encrypted_refresh_token: trimmed(tokenPayload.refresh_token)
      ? await encryptProviderTokenValue(env, trimmed(tokenPayload.refresh_token))
      : "",
    encrypted_id_token: trimmed(tokenPayload.id_token) ? await encryptProviderTokenValue(env, trimmed(tokenPayload.id_token)) : "",
    token_type: trimmed(tokenPayload.token_type, "Bearer"),
    scope_hash: scopeText ? await sha256Hex(scopeText) : "",
    expires_at:
      Number.isFinite(Number(tokenPayload.expires_in)) && Number(tokenPayload.expires_in) > 0
        ? new Date(Date.now() + Number(tokenPayload.expires_in) * 1000).toISOString()
        : null,
    status: "connected",
    metadata_safe: {
      scopes: scopeText ? scopeText.split(/\s+/).filter(Boolean) : [],
      refresh_token_present: Boolean(trimmed(tokenPayload.refresh_token)),
      id_token_present: Boolean(trimmed(tokenPayload.id_token)),
      expires_in_present: Number.isFinite(Number(tokenPayload.expires_in)) && Number(tokenPayload.expires_in) > 0,
    },
  });
  const completedFlow = {
    ...updatedFlow,
    status: "completed",
    failure_reason: "",
    updated_at: nowIso(),
  };
  await upsertProviderAuthFlow(env, completedFlow);
  const updatedConnection = await upsertProviderConnection(env, record, {
    auth_method: "oauth",
    status: "connected",
    failure_reason: "",
    metadata: {
      ...(record.metadata && typeof record.metadata === "object" ? record.metadata : {}),
      oauth_callback_received_at: nowIso(),
      oauth_authorization_code_received: true,
      oauth_token_storage_supported: true,
      oauth_token_recorded: true,
      oauth_token_status: "connected",
      oauth_token_metadata_safe:
        oauthTokenRow.metadata_safe && typeof oauthTokenRow.metadata_safe === "object" ? oauthTokenRow.metadata_safe : {},
    },
    last_verified_at: nowIso(),
  });
  const provider = buildProviderRecord(env, resolvedProviderId, updatedConnection);
  return htmlResponse(
    renderProviderCallbackPage(provider, publicProviderFlow(completedFlow), "Mystic LAB completed the OAuth callback and stored encrypted provider tokens."),
    200,
  );
}

async function handleProviderRoute(request, env) {
  const sourceUrl = new URL(request.url);
  const pathname = sourceUrl.pathname;
  if (pathname === "/providers") {
    const registry = await loadProviderRegistry(env);
    return htmlResponse(renderProviderListPage(registry));
  }
  if (pathname === "/providers/oauth/callback") {
    return handleProviderOauthCallback(request, env);
  }
  const match = pathname.match(/^\/providers\/([^/]+)\/(connect|setup|secret|status)$/);
  if (!match) {
    return null;
  }
  const providerId = normalizeProviderId(decodeURIComponent(match[1]));
  const action = match[2];
  if (![...PUBLIC_PROVIDER_IDS, "mock"].includes(providerId)) {
    return errorResponse("Unknown provider.", 404);
  }
  const spec = providerCatalogEntry(env, providerId);
  const registry = await loadProviderRegistry(env);
  const provider = providerRegistryMap(registry).get(providerId) || buildProviderRecord(env, providerId);
  const oauthMetadata = providerOauthMetadata(env, spec);
  if (action === "status") {
    return jsonResponse(provider, 200, { "cache-control": "no-store" });
  }
  if (action === "setup") {
    return htmlResponse(renderProviderSetupPage(provider, spec));
  }
  if (action === "connect") {
    const flowId = trimmed(sourceUrl.searchParams.get("flow_id"));
    const flow = flowId ? await loadProviderAuthFlow(env, flowId) : null;
    return htmlResponse(renderProviderConnectPage(provider, spec, oauthMetadata, flow ? publicProviderFlow(flow) : null));
  }
  if (action === "secret") {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }
    await request.text();
    return jsonResponse(
      {
        provider_id: provider.provider_id,
        status: "direct_secret_write_unavailable",
        direct_secret_write_supported: false,
        required_secret_names: provider.required_secret_names,
        missing_secret_names: provider.missing_secret_names,
        setup_url: provider.setup_url,
        instructions: providerManualSecretInstructions(spec),
        message:
          "Direct secret writing is not available in this deployment. Configure Cloudflare secrets manually with the listed names. Submitted values were not stored or echoed.",
      },
      501,
      { "cache-control": "no-store" },
    );
  }
  return null;
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

  if (phase1CloudMode && pathname.startsWith("/providers")) {
    const providerResponse = await handleProviderRoute(request, env);
    if (providerResponse) {
      return providerResponse;
    }
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
    const authorization = await authorizeMcpRequest(request, state, env);
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
      const target = requestTargetUrl(url);
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
          (typeof item.key === "string" && (item.key === key || item.key === target)) ||
          (typeof item.prefix === "string" && target.startsWith(item.prefix)) ||
          (typeof item.methodPrefix === "string" && key.startsWith(item.methodPrefix)),
      );
      if (!entry) {
        throw new Error(`Unexpected fetch: ${key}`);
      }
      const status = entry.status || 200;
      const responseBody =
        status === 204 || status === 205 || status === 304
          ? null
          : entry.body === undefined
            ? ""
            : JSON.stringify(entry.body);
      return new Response(responseBody, {
        status,
        headers: entry.headers || { "content-type": "application/json; charset=utf-8" },
      });
    };
  }
  try {
    const request = new Request(input.requestUrl, {
      method: input.method || "POST",
      headers: input.headers || {},
      body:
        input.rawBody !== undefined
          ? input.rawBody
          : input.body === undefined
            ? undefined
            : JSON.stringify(input.body),
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
    const decision = await authorizeMcpRequest(request, state, input.env || {});
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
      requireStoredCode: Boolean(input.requireStoredCode),
    });
  },
  async validateAccessToken(input) {
    const state = oauthState(input.env || {}, input.requestUrl || "https://mystic.dexproject.workers.dev/mcp");
    return validateAccessToken(input.token, state);
  },
  async pkceChallenge(input) {
    return sha256Base64Url(input.codeVerifier);
  },
  async exerciseAuthorizeFlow(input) {
    authorizationCodeMemoryStore.clear();
    const env = input.env || {};
    const requestUrl = input.requestUrl || "https://mystic.dexproject.workers.dev/mcp";
    const state = oauthState(env, requestUrl);
    const authorizeUrl = `${state.authorizationEndpoint}?response_type=code&client_id=${encodeURIComponent(input.clientId)}&redirect_uri=${encodeURIComponent(input.redirectUri)}&state=${encodeURIComponent(input.stateValue)}&scope=${encodeURIComponent(input.scope || DEFAULT_SCOPES)}&code_challenge=${encodeURIComponent(input.codeChallenge)}&code_challenge_method=S256`;
    const page = await routeRequest(new Request(authorizeUrl, { method: "GET" }), env);
    const approval = await routeRequest(
      new Request(state.authorizationEndpoint, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          response_type: "code",
          client_id: input.clientId,
          redirect_uri: input.redirectUri,
          state: input.stateValue,
          scope: input.scope || DEFAULT_SCOPES,
          code_challenge: input.codeChallenge,
          code_challenge_method: "S256",
          decision: "approve",
        }),
      }),
      env,
    );
    const location = approval.headers.get("location") || "";
    const redirect = new URL(location);
    const code = redirect.searchParams.get("code") || "";
    const firstExchange = await exchangeAuthorizationCode({
      code,
      clientId: input.clientId,
      redirectUri: input.redirectUri,
      codeVerifier: input.codeVerifier,
      state,
      requireStoredCode: true,
    });
    const secondExchange = await exchangeAuthorizationCode({
      code,
      clientId: input.clientId,
      redirectUri: input.redirectUri,
      codeVerifier: input.codeVerifier,
      state,
      requireStoredCode: true,
    });
    return {
      pageStatus: page.status,
      pageContentType: page.headers.get("content-type") || "",
      pageBody: await page.text(),
      approvalStatus: approval.status,
      approvalLocation: location,
      firstExchange,
      secondExchange,
    };
  },
  resetAuthorizationCodeStore() {
    authorizationCodeMemoryStore.clear();
    return { ok: true };
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
