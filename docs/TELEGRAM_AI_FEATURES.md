# Telegram AI / Agent Features (Bot API 9.3–10.x)

ShibaClaw's Telegram channel supports the Bot API capabilities introduced for AI agents
in late 2025 / 2026. Enable or disable them under `channels.telegram` in `config.json`.

Security-sensitive features are **opt-in** (`false` by default). Only `streaming` defaults
to `true` (private-chat UX; no access-control impact).

| Config key | Default | Feature |
|---|---|---|
| `streaming` | `true` | `sendMessageDraft` streaming in private chats |
| `guestMode` | `false` | Guest bots — reply when `@username` is used in any chat |
| `allowBotMessages` | `false` | Bot-to-bot messages (also enable in BotFather) |
| `businessEnabled` | `false` | Chat Automation / Business connection messages |
| `managedBotsEnabled` | `false` | Track Managed Bot create/token updates |
| `richMessages` | `false` | Bot API 10.1 `sendRichMessage` / rich draft (opt-in) |
| `openGroups` | `false` | Groups accept any member; private bot DMs stay on `allowFrom` |

## Access notes for Rich Messages

- **`richMessages: true`** sends agent replies via `sendRichMessage`. Plain text uses `rich_message.markdown`. PTB 22.8 has no wrappers — ShibaClaw calls the Bot API through `Bot.do_api_request`.
- **Auto blocks:** display math (`$$…$$` / ` ```math `), GFM pipe-tables, and ≥2 consecutive `![](https://…)` images are converted to explicit `blocks` (mathematical_expression / table / collage). Blocks failure retries markdown, then HTML/`sendMessage`.
- Private streaming with rich enabled uses `sendRichMessageDraft`; on failure it falls back to `sendMessageDraft` / HTML `sendMessage`.
- Some Telegram clients still show unsupported placeholders for rich content — keep the flag off until your clients render it well.
- Chat Automation supports `business_connection_id` on `sendRichMessage` when the connected user can send rich messages.

## Access control (`allowFrom` + `openGroups`)

- **Private bot DMs** always require `allowFrom` (owner allowlist). `"*"` still means everyone.
- **`openGroups: true`** — group/supergroup members may talk to the bot (reply policy still follows `groupPolicy`). Senders not on `allowFrom` get `metadata.is_allowlisted=false` and the agent loop strips FS/exec/MCP tools.
- **`businessEnabled: true`** — Chat Automation peer DMs are accepted even when `allowFrom` is owner-only (otherwise the archive never receives peer traffic). Same tool lockdown for non-allowlisted peers.
- **Guest Mode** always requires `allowFrom` (never opened by `openGroups`).
- Slash commands `/new`, `/stop`, `/restart` in groups remain allowlist-only.

Forwarded messages include a content prefix `[Forwarded from: …]` and forward metadata (`is_forward`, `forward_label`, …) so the model can see the origin.

## BotFather / client setup

These flags alone are not enough — Telegram must allow the capability for your bot:

1. **Guest Mode** — enable Guest Mode for the bot (see [Telegram Guest Bots guide](https://core.telegram.org/bots/features#guest-bots)).
2. **Bot-to-bot** — enable bot-to-bot communication for both bots.
3. **Chat Automation** — users connect the bot under *Settings → Chat Automation*; the bot receives `business_connection` / `business_message` updates.
4. **Managed bots** — manager bots create child bots via the request-managed-bot keyboard flow; ShibaClaw records `managed_bot` updates (it does not auto-spawn unmanaged agents).

## Behaviour notes

- **Streaming drafts** work only in **private** chats (Telegram API constraint). Groups keep the existing progress-edit path. Draft IDs are derived from the inbound `message_id` so they survive process restarts.
- **Guest replies** use `answerGuestQuery` (not `sendMessage`). Guest turns get an isolated session key `telegram:guest:<query_id>`. Guest Mode still respects `allowFrom` — unauthorised senders are ignored.
- **Rich Messages** use `sendRichMessage` / `sendRichMessageDraft` when `richMessages` is enabled; any API error falls back to the legacy HTML/`sendMessage` path.
- **Auto blocks:** plain replies stay `rich_message.markdown`. When the text has display math (`$$…$$` / ` ```math `), a GFM pipe-table, or ≥2 consecutive image URLs, ShibaClaw builds explicit `blocks` (mathematical_expression / table / collage). If blocks fail, it retries markdown once, then HTML.

## Example config

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "allowFrom": ["123456789"],
      "openGroups": true,
      "streaming": true,
      "richMessages": true,
      "guestMode": true,
      "allowBotMessages": true,
      "businessEnabled": true,
      "managedBotsEnabled": true
    }
  }
}
```
