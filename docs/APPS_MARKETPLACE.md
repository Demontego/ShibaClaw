# ShibaClaw Apps & Integrations Marketplace

The Apps Marketplace transforms ShibaClaw's integrations layer into a user-friendly app store experience inspired by ChatGPT and modern developer platforms. Non-technical users can discover, install, configure, and authenticate integrations in one click without dealing with MCP servers, transport protocols, configuration files, or Python entry points.

---

## 1. Core Architecture

The architecture unifies heterogeneous integration backends under a common domain model while reusing ShibaClaw's existing configuration, security vault, and gateway hot-reload systems.

```
                      +-----------------------------+
                      |      WebUI / Frontend       |
                      |   Apps & Marketplace Tab    |
                      +--------------+--------------+
                                     |
                                     v REST API (/api/apps/*)
                      +-----------------------------+
                      |     Apps Router & Core      |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+-----------------+         +-----------------+         +-----------------+
|   Curated App   |         |  Official MCP   |         |  Native Plugin  |
|    Registry     |         |    Registry     |         |    Registry     |
+-----------------+         +-----------------+         +-----------------+
         |                           |                           |
         +---------------------------+---------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |    App Installer & State    |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+-----------------+         +-----------------+         +-----------------+
|  MCP Servers    |         |  Credential &   |         | Gateway Hot-    |
| Config (schema) |         |  OAuth Vault    |         | Reload System   |
+-----------------+         +-----------------+         +-----------------+
```

### Unified App Model

Each application is described by an `AppDefinition`:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique slug identifier (e.g. `google-workspace`, `github`, `postgres`) |
| `name` | `str` | User-facing display name |
| `description`| `str` | Friendly summary of the app's capabilities |
| `category` | `str` | Category (`productivity`, `development`, `database`, `channels`, `audio`, etc.) |
| `source` | `str` | Origin catalog (`curated`, `mcp_registry`, `native`, `custom`) |
| `runtime_type`| `str` | Execution engine: `mcp_remote`, `mcp_local`, `native_plugin` |
| `trust_level` | `str` | Trust classification: `official`, `verified`, `community` |
| `auth` | `AppAuthDefinition` | Standardized authentication requirements and schema |
| `capabilities` | `list[str]` | Human-readable bullet points shown on the card |
| `mcp_config` | `dict` | Pre-configured MCP transport settings (for MCP runtime types) |
| `package_name` | `str` | Python package name (for native plugins) |

---

## 2. Multi-Source Catalogs

Marketplace integrations are sourced and prioritized through `AppRegistryManager`:

1. **Curated Registry (`CuratedAppRegistry`)**:
   - Highest priority.
   - Ships bundled in `shibaclaw/apps/curated_registry.json`.
   - Features verified integrations (Google Workspace, GitHub, Notion, PostgreSQL, WhatsApp, Brave Search, Supertonic TTS, RAG).
   - Can sync remotely from ShibaClaw's official GitHub repository with automatic fallback to bundled definitions.
2. **Native Plugin Registry (`NativePluginRegistryProvider`)**:
   - Discovers installed and installable native Python plugins (`shibaclaw-channel-*`, `shibaclaw-tts-*`, etc.).
3. **Official MCP Registry (`MCPRegistryProvider`)**:
   - Queries `https://registry.modelcontextprotocol.io/v0.1/servers`.
   - Features 4.0-second network timeouts, secure URL validation, and local disk caching (`~/.shibaclaw/cache/mcp_registry_cache.json`) with stale cache fallback.
   - Transports (`streamable-http`, `stdio`) are automatically translated into ShibaClaw MCP server definitions.

---

## 3. Installation & Lifecycle

Installation is transactional:
1. **Validation**: Validates runtime compatibility, package name safety (`^shibaclaw-[a-zA-Z0-9_\-]+$`), command safety, and remote URL validity (disallowing RFC 1918 / loopback IPs in untrusted contexts).
2. **Registration**: Creates and persists an `InstalledAppRecord` in `installed_apps.json` and updates `config.apps`.
3. **Execution**:
   - For `mcp_remote` / `mcp_local`: writes configuration into `config.tools.mcp_servers` and hot-reloads the agent.
   - For `native_plugin`: invokes the package installer and reloads the gateway.
4. **Rollback**: On failure, intermediate configurations and state entries are cleaned up automatically.

### Enabling & Disabling
Apps can be toggled on and off without losing credentials:
- Disabling an MCP app sets its `enabled_tools` to `[]`, immediately withdrawing its tools from the agent's context.
- Disabling a native channel plugin turns off the channel in configuration.
- Re-enabling restores tool access without requiring re-authentication.

---

## 4. Authentication Architecture

The Apps layer unifies authentication across providers:

- **None**: App works immediately upon installation (e.g. Filesystem, RAG, Brave Search with no credentials).
- **API Key / Bearer**: Users enter their API key/token in the UI. Keys are stored encrypted in `CredentialManager` and injected into HTTP headers dynamically.
- **OAuth 2.0 + PKCE**:
  - Automatically starts a local callback server on an ephemeral loopback port (`http://127.0.0.1:<port>/callback/<token>`).
  - Generates PKCE verifier/challenge and state for CSRF protection.
  - Automatically exchanges authorization code for tokens and saves them in `OAuthTokenStore`.
  - Seamlessly handles refresh tokens before expiration.
- **Bring Your Own (BYO) Client Credentials**:
  - Providers that do not support public PKCE prompt the user for their Client ID and Client Secret.
  - Client secrets are stored securely in `CredentialManager` and never written to configuration JSON files or returned to the browser.

---

## 5. Security Guardrails

The Apps Marketplace enforces defense-in-depth:
- **SSRF Prevention**: Remote MCP URLs must use HTTP/HTTPS and are prohibited from targeting loopback (`127.0.0.1`, `localhost`) or private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- **Command Injection Guard**: Local stdio apps from registries can only execute vetted runners: `npx`, `uvx`, `python`, `node`, `docker`. Arbitrary shell commands or chained arguments are rejected.
- **Package Integrity**: Native plugin packages are strictly verified against the trusted naming convention `shibaclaw-*`.
- **Zero Secret Exposure**: Tokens, passwords, and private API keys are filtered from API outputs, client state, and log messages.

---

## 6. Tool & Capability Permissions

Administrators can control which tools an installed app exposes to the ShibaClaw agent:
- Every app supports granular tool allowlisting via `enabled_tools`.
- Users can view tool descriptions and toggle individual tools on or off in the App Settings modal.
- Disabled tools are stripped from the LLM prompt and tool invocation dispatcher.

---

## 7. REST API Endpoints

All endpoints are mounted under `/api/apps`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/apps` | `GET` | List apps across all catalogs with search, category, and tab filters |
| `/api/apps/{app_id}` | `GET` | Get detailed metadata, live status, and available tools |
| `/api/apps/install` | `POST` | Transactionally install an app |
| `/api/apps/{app_id}/uninstall`| `POST` | Uninstall an app and revoke stored credentials |
| `/api/apps/{app_id}/enable` | `POST` | Enable an installed app |
| `/api/apps/{app_id}/disable`| `POST` | Disable an installed app without losing credentials |
| `/api/apps/{app_id}/connect`| `POST` | Authenticate an app (OAuth2 initiation, API key, or credentials) |
| `/api/apps/{app_id}/disconnect`| `POST` | Revoke and clear credentials |
| `/api/apps/{app_id}/auth-status`| `GET` | Check live authentication state |
| `/api/apps/{app_id}/tools` | `GET` | Get available MCP tools and their enabled status |
| `/api/apps/{app_id}/tools` | `PUT` | Update tool allowlist for an integration |
| `/api/apps/custom` | `POST` | Register a custom local/remote MCP app (Developer mode) |
