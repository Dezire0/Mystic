const CONFIG_URL = "https://gist.githubusercontent.com/Dezire0/778759ccca8f7d9a54c1f98662b6a9ec/raw/mystic-origin.json";
const DEFAULT_SCOPES = "tools:read tools:execute";
const DEFAULT_TOKEN_TTL_SECONDS = 3600;
const MANUAL_IMPORT_VERIFICATION_PATH = "/mystic_data/e2e/remote_mcp_lab_smoke/chatgpt_import_verified.json";
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

  if (pathname === "/mcp") {
    const authorization = await authorizeMcpRequest(request, state);
    if (!authorization.ok) {
      return authorization.response;
    }
  }

  return proxyRequest(request, env, sourceUrl, state);
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
};

export default {
  async fetch(request, env) {
    return routeRequest(request, env);
  },
};
