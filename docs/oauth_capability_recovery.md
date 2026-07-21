# OAuth Capability Recovery

Issue #108 preserves real Mystic OAuth functionality without reviving placeholders or unimplemented integrations.

## Recovery Map

| Capability | Historical evidence | Current disposition |
| --- | --- | --- |
| OAuth authorization code + PKCE | `5e592f43` (`#61`) | Preserved and tested. |
| Fixed ChatGPT public client | ChatGPT production authorization requests use `mystic-chatgpt` | Registered in Worker with the exact connector callback. |
| Dynamic client registration | Feature flag and metadata conditional existed; `/oauth/register` returned `501` | Not advertised or enabled. No real historical DCR handler was found. |
| CIMD | No implementation found in all refs, reflogs, or reachable history | Disabled and not advertised. |
| OIDC userinfo/JWKS/ID tokens | No real endpoint implementation found | Disabled and not advertised. OAuth discovery remains available as an authorization-server document. |
| Home Assistant / IoT | No provider, tools, or API implementation found in repository history | Not restored or advertised. A separate issue must define credentials, scope policy, confirmation, audit storage, and safe allowlists. |

## ChatGPT Client

- Public client ID: `mystic-chatgpt`
- Redirect URI: `https://chatgpt.com/connector/oauth/wpja_UKVNtTE`
- Resource: `https://mystic.dexproject.workers.dev/mcp`
- Token endpoint authentication: `none`
- PKCE: `S256` required
- Scopes: `tools:read tools:execute`

The callback is exact-match only. Wildcards, modified callbacks, unknown clients, non-S256 PKCE, and scopes outside the advertised allowlist are rejected.

## Metadata Contract

The Worker publishes only operational OAuth fields. It does not publish a registration endpoint, CIMD support, `userinfo_endpoint`, or a placeholder URL unless a real implementation is added and tested.
