from __future__ import annotations

import hashlib
import os as _os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.integrations.klavis_client import KlavisLimitError

@dataclass
class ConnectedAppDef:
    id: str
    name: str
    category: str
    icon: str
    description: str
    klavis_server_name: str
    mcp_server_key: str = field(init=False)

    def __post_init__(self) -> None:
        self.mcp_server_key = self.id

CONNECTED_APPS: dict[str, ConnectedAppDef] = {
    "gmail": ConnectedAppDef(id="gmail", name="Gmail", category="google", icon="email",
        description="Send and read emails via Google Gmail.", klavis_server_name="Gmail"),
    "gdrive": ConnectedAppDef(id="gdrive", name="Google Drive", category="google", icon="folder",
        description="Read and write files on Google Drive.", klavis_server_name="Google Drive"),
    "gsheets": ConnectedAppDef(id="gsheets", name="Google Sheets", category="google", icon="table_chart",
        description="Manage spreadsheets and data in Google Sheets.", klavis_server_name="Google Sheets"),
    "gdocs": ConnectedAppDef(id="gdocs", name="Google Docs", category="google", icon="description",
        description="Read and write documents in Google Docs.", klavis_server_name="Google Docs"),
    "gcalendar": ConnectedAppDef(id="gcalendar", name="Google Calendar", category="google", icon="calendar_today",
        description="Manage events and schedules in Google Calendar.", klavis_server_name="Google Calendar"),
    "outlook": ConnectedAppDef(id="outlook", name="Outlook Mail", category="microsoft", icon="mail",
        description="Send and read emails via Microsoft Outlook.", klavis_server_name="Outlook Mail"),
    "onedrive": ConnectedAppDef(id="onedrive", name="OneDrive", category="microsoft", icon="cloud",
        description="Read and write files on Microsoft OneDrive.", klavis_server_name="OneDrive"),
    "outlook_calendar": ConnectedAppDef(id="outlook_calendar", name="Outlook Calendar",
        category="microsoft", icon="event",
        description="Manage events and schedules in Outlook Calendar.", klavis_server_name="Outlook Calendar"),
    "slack": ConnectedAppDef(id="slack", name="Slack", category="productivity", icon="chat",
        description="Send messages and manage channels in Slack.", klavis_server_name="Slack"),
    "notion": ConnectedAppDef(id="notion", name="Notion", category="productivity", icon="notes",
        description="Read and write pages and databases in Notion.", klavis_server_name="Notion"),
    "linear": ConnectedAppDef(id="linear", name="Linear", category="productivity", icon="notes",
        description="Manage projects and issues in Linear.", klavis_server_name="Linear"),
    "github": ConnectedAppDef(id="github", name="GitHub", category="dev", icon="code",
        description="Manage repos, issues and pull requests on GitHub.", klavis_server_name="GitHub"),
    "gitlab": ConnectedAppDef(id="gitlab", name="GitLab", category="dev", icon="merge_type",
        description="Manage repos, issues and merge requests on GitLab.", klavis_server_name="GitLab"),
    "jira": ConnectedAppDef(id="jira", name="Jira", category="dev", icon="bug_report",
        description="Manage projects and issues in Jira.", klavis_server_name="Jira"),
    "confluence": ConnectedAppDef(id="confluence", name="Confluence", category="dev", icon="article",
        description="Read and write pages in Confluence.", klavis_server_name="Confluence"),
    "dropbox": ConnectedAppDef(id="dropbox", name="Dropbox", category="storage", icon="inventory_2",
        description="Read and write files in Dropbox.", klavis_server_name="Dropbox"),
    "box": ConnectedAppDef(id="box", name="Box", category="storage", icon="archive",
        description="Manage files and folders in Box.", klavis_server_name="Box"),
    "figma": ConnectedAppDef(id="figma", name="Figma", category="design", icon="palette",
        description="Browse and comment on designs in Figma.", klavis_server_name="Figma"),
    "hubspot": ConnectedAppDef(id="hubspot", name="HubSpot", category="crm", icon="contacts",
        description="Manage contacts and deals in HubSpot CRM.", klavis_server_name="HubSpot"),
    "salesforce": ConnectedAppDef(id="salesforce", name="Salesforce", category="crm", icon="business_center",
        description="Manage CRM records in Salesforce.", klavis_server_name="Salesforce"),
    "stripe": ConnectedAppDef(id="stripe", name="Stripe", category="crm", icon="payment",
        description="Access payments and subscriptions via Stripe.", klavis_server_name="Stripe"),
}

# Klavis-hosted servers beyond the first set. Category matches the Klavis directory.
_EXTRA_APPS: tuple[tuple[str, str, str, str, str], ...] = (
    ("discord", "Discord", "communication", "forum", "Send messages and manage Discord servers."),
    ("microsoft_teams", "Microsoft Teams", "communication", "groups", "Chat and meetings in Microsoft Teams."),
    ("whatsapp", "WhatsApp", "communication", "chat", "Send and read WhatsApp messages."),
    ("linkedin", "LinkedIn", "communication", "work", "Read and post on LinkedIn."),
    ("dialpad", "Dialpad", "communication", "call", "Calls and messages in Dialpad."),
    ("instagram", "Instagram", "communication", "photo_camera", "Read and publish Instagram content."),
    ("youtube", "YouTube", "media", "smart_display", "Search and manage YouTube videos."),
    ("resend", "Resend", "communication", "mail", "Send transactional email through Resend."),
    ("hacker_news", "Hacker News", "communication", "newspaper", "Read Hacker News stories and comments."),
    ("calcom", "Cal.com", "meetings", "event", "Book and manage Cal.com meetings."),
    ("calendly", "Calendly", "meetings", "event_available", "Read and schedule Calendly events."),
    ("clockwise", "Clockwise", "meetings", "schedule", "Find focus time and meetings in Clockwise."),
    ("fireflies", "Fireflies", "meetings", "mic", "Read meeting notes from Fireflies."),
    ("fathom", "Fathom", "meetings", "record_voice_over", "Read meeting recordings from Fathom."),
    ("asana", "Asana", "projects", "task_alt", "Manage tasks and projects in Asana."),
    ("clickup", "ClickUp", "projects", "checklist", "Manage tasks and docs in ClickUp."),
    ("monday", "Monday", "projects", "view_kanban", "Manage boards and items in Monday."),
    ("motion", "Motion", "projects", "today", "Plan tasks and calendar blocks in Motion."),
    ("airtable", "Airtable", "productivity", "grid_on", "Read and update Airtable bases."),
    ("wordpress", "WordPress", "productivity", "article", "Read and publish WordPress posts."),
    ("jotform", "Jotform", "productivity", "dynamic_form", "Read Jotform submissions."),
    ("zendesk", "Zendesk", "productivity", "support_agent", "Read and reply to Zendesk tickets."),
    ("canva", "Canva", "design", "brush", "Browse and create Canva designs."),
    ("cloudflare", "Cloudflare", "dev", "cloud", "Manage Cloudflare zones and workers."),
    ("google_cloud", "Google Cloud", "dev", "cloud_queue", "Inspect Google Cloud resources."),
    ("vercel", "Vercel", "dev", "rocket_launch", "Inspect Vercel projects and deployments."),
    ("netlify", "Netlify", "dev", "dns", "Inspect Netlify sites and deploys."),
    ("postman", "Postman", "dev", "api", "Browse Postman collections."),
    ("sentry", "Sentry", "dev", "bug_report", "Read Sentry issues and events."),
    ("postgres", "Postgres", "databases", "storage", "Query a Postgres database."),
    ("supabase", "Supabase", "databases", "dataset", "Query Supabase tables and auth."),
    ("snowflake", "Snowflake", "databases", "ac_unit", "Query a Snowflake warehouse."),
    ("huggingface", "Hugging Face", "ai", "psychology", "Browse Hugging Face models and datasets."),
    ("mem0", "Mem0", "ai", "memory", "Read and write Mem0 memories."),
    ("openrouter", "Openrouter", "ai", "hub", "Call models through OpenRouter."),
    ("brave_search", "Brave Search", "search", "search", "Search the web with Brave."),
    ("exa", "Exa", "search", "travel_explore", "Search the web with Exa."),
    ("tavily", "Tavily", "search", "manage_search", "Search the web with Tavily."),
    ("perplexity", "Perplexity", "search", "psychology_alt", "Ask Perplexity for sourced answers."),
    ("firecrawl_search", "Firecrawl Web Search", "search", "travel_explore", "Search pages with Firecrawl."),
    ("firecrawl_research", "Firecrawl Deep Research", "search", "science", "Run a Firecrawl research pass."),
    ("affinity", "Affinity", "crm", "handshake", "Manage relationship data in Affinity."),
    ("attio", "Attio", "crm", "contacts", "Manage people and deals in Attio."),
    ("close", "Close", "crm", "call", "Manage leads and calls in Close."),
    ("pipedrive", "Pipedrive", "crm", "filter_alt", "Manage the Pipedrive pipeline."),
    ("intercom", "Intercom", "crm", "chat_bubble", "Read and reply to Intercom conversations."),
    ("freshdesk", "Freshdesk", "crm", "confirmation_number", "Read and reply to Freshdesk tickets."),
    ("gong", "Gong", "crm", "graphic_eq", "Read call insights from Gong."),
    ("shopify", "Shopify", "sales", "storefront", "Manage Shopify products and orders."),
    ("sendgrid", "SendGrid", "sales", "forward_to_inbox", "Send email through SendGrid."),
    ("klaviyo", "Klaviyo", "sales", "campaign", "Read Klaviyo lists and campaigns."),
    ("paypal", "PayPal", "payments", "payments", "Read PayPal payments."),
    ("square", "Square", "payments", "point_of_sale", "Read Square payments and catalog."),
    ("coinbase", "Coinbase", "finance", "currency_bitcoin", "Read Coinbase accounts and prices."),
    ("quickbooks", "QuickBooks", "finance", "account_balance", "Read QuickBooks invoices and books."),
    ("docusign", "DocuSign", "documents", "draw", "Send and track DocuSign envelopes."),
)

for _id, _name, _category, _icon, _description in _EXTRA_APPS:
    CONNECTED_APPS[_id] = ConnectedAppDef(
        id=_id,
        name=_name,
        category=_category,
        icon=_icon,
        description=_description,
        klavis_server_name=_name,
    )

CONNECTED_APPS_KEY = "connected_apps"
STRATA_KEY = "__strata__"
_APP_META_KEYS = frozenset({"__backend__", "__strata__", "klavis"})
DEFAULT_TRANSPORT = "streamableHttp"
KLAVIS_API_BASE = "https://api.klavis.ai"
LIMIT_ERROR_MSG = (
    "Klavis account has reached the maximum number of Strata instances (limit: 3). "
    "To fix: open the Klavis dashboard (https://www.klavis.ai/dashboard), find an existing "
    "Strata ID, then call POST /api/apps/backend/reset with body "
    '{"strata_id": "<your-existing-strata-id>", "mcp_url": "<strataServerUrl>"} '
    "to reuse it without creating a new one."
)


def cfg_to_dict(cfg: Any) -> dict:
    if cfg is None:
        return {}
    try:
        return cfg.model_dump(mode="json", exclude_none=False)
    except Exception:
        pass
    try:
        return dict(cfg)
    except Exception:
        return {}


def get_apps_cfg(cfg_dict: dict) -> dict:
    return cfg_dict.get(CONNECTED_APPS_KEY) or {}


def get_strata_meta(cfg_dict: dict) -> dict:
    return get_apps_cfg(cfg_dict).get(STRATA_KEY) or {}


def get_app_state(cfg_dict: dict, app_id: str) -> dict:
    return get_apps_cfg(cfg_dict).get(app_id) or {}


def is_klavis_server(k: str, v: Any) -> bool:
    if isinstance(v, dict) and v.get("klavis_app"):
        return True
    return k.endswith("-klavis")


def sync_app_to_mcp(
    cfg_dict: dict,
    app_def: ConnectedAppDef,
    strata_mcp_url: str,
    headers: dict[str, str] | None = None,
) -> None:
    if "tools" not in cfg_dict or cfg_dict["tools"] is None:
        cfg_dict["tools"] = {}
    tools = cfg_dict["tools"]
    if "mcp_servers" in tools and "mcpServers" not in tools:
        tools["mcpServers"] = tools.pop("mcp_servers")
    if tools.get("mcpServers") is None:
        tools["mcpServers"] = {}
    entry: dict[str, Any] = {
        "type": DEFAULT_TRANSPORT,
        "url": strata_mcp_url,
        "klavis_app": app_def.id,
    }
    if headers:
        entry["headers"] = headers
    tools["mcpServers"][app_def.mcp_server_key] = entry


def remove_app_from_mcp(cfg_dict: dict, app_def: ConnectedAppDef) -> None:
    tools = cfg_dict.get("tools") or {}
    servers = tools.get("mcpServers") or tools.get("mcp_servers") or {}
    servers.pop(app_def.mcp_server_key, None)


def slug_server_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")[:48]


def catalog_app_for_name(name: str) -> ConnectedAppDef | None:
    key = name.strip().casefold()
    if not key:
        return None
    for app in CONNECTED_APPS.values():
        if key in {app.id, app.name.casefold(), app.klavis_server_name.casefold()}:
            return app
    return None


def custom_app_def(server_name: str, app_id: str | None = None) -> ConnectedAppDef:
    name = server_name.strip()
    return ConnectedAppDef(
        id=app_id or slug_server_name(name),
        name=name,
        category="custom",
        icon="extension",
        description=f"Klavis server {name}.",
        klavis_server_name=name,
    )


def with_custom_identity(app_def: ConnectedAppDef, state: dict) -> dict:
    if app_def.id not in CONNECTED_APPS:
        state["klavis_server_name"] = app_def.klavis_server_name
        state["name"] = app_def.name
    return state


def mark_disconnected(prev: dict | None) -> dict:
    state = {"enabled": False, "connected": False, "pending_oauth": False}
    if isinstance(prev, dict) and isinstance(prev.get("klavis_server_name"), str):
        state["klavis_server_name"] = prev["klavis_server_name"]
        if isinstance(prev.get("name"), str):
            state["name"] = prev["name"]
    return state


def resolve_app(cfg_dict: dict, app_id: str) -> ConnectedAppDef | None:
    if app_id in CONNECTED_APPS:
        return CONNECTED_APPS[app_id]
    if app_id in _APP_META_KEYS:
        return None
    state = get_app_state(cfg_dict, app_id)
    server = state.get("klavis_server_name") if isinstance(state, dict) else None
    if not isinstance(server, str) or not server.strip():
        return None
    return custom_app_def(server, app_id)


def visible_apps(cfg_dict: dict) -> list[ConnectedAppDef]:
    apps = list(CONNECTED_APPS.values())
    seen = {app.id for app in apps}
    for key, state in get_apps_cfg(cfg_dict).items():
        if key in seen or key in _APP_META_KEYS or not isinstance(state, dict):
            continue
        server = state.get("klavis_server_name")
        if isinstance(server, str) and server.strip():
            apps.append(custom_app_def(server, key))
    return apps


def build_app_response(app_def: ConnectedAppDef, app_state: dict) -> dict:
    return {
        "id": app_def.id,
        "name": app_def.name,
        "category": app_def.category,
        "icon": app_def.icon,
        "description": app_def.description,
        "enabled": app_state.get("enabled", False),
        "connected": app_state.get("connected", False),
        "mcp_server_key": app_def.mcp_server_key,
    }


async def save_and_reload(cfg_dict: dict) -> JSONResponse | None:
    try:
        from shibaclaw.config.loader import save_config
        from shibaclaw.config.schema import Config
        new_cfg = Config.model_validate(cfg_dict)
        save_config(new_cfg)
        await agent_manager.reload_config(new_cfg)
        return None
    except Exception as exc:
        logger.exception("Failed to save config")
        return JSONResponse({"error": str(exc)}, status_code=500)


def get_or_create_user_id(cfg_dict: dict) -> str:
    uid = get_strata_meta(cfg_dict).get("user_id") or ""
    if uid:
        return uid
    try:
        token = cfg_dict.get("gateway", {}).get("token") or ""
        if token:
            return hashlib.sha256(token.encode()).hexdigest()[:32]
    except Exception:
        pass
    return _os.urandom(16).hex()


def get_klavis_client_clean() -> Any:
    from shibaclaw.integrations.klavis_client import reload_klavis_client
    return reload_klavis_client(base_url=KLAVIS_API_BASE)


def clear_stale_strata(cfg_dict: dict) -> None:
    apps_cfg = cfg_dict.get(CONNECTED_APPS_KEY)
    if isinstance(apps_cfg, dict):
        apps_cfg.pop(STRATA_KEY, None)
        for k in list(apps_cfg.keys()):
            if k not in _APP_META_KEYS:
                prev = apps_cfg[k] if isinstance(apps_cfg[k], dict) else None
                apps_cfg[k] = mark_disconnected(prev)

    tools = cfg_dict.get("tools")
    if isinstance(tools, dict):
        servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
        if tools.get(servers_key):
            tools[servers_key] = {
                k: v for k, v in tools[servers_key].items() if not is_klavis_server(k, v)
            }
    logger.warning("Cleared stale strata_id from config and disconnected apps.")


async def ensure_strata(
    klavis: Any,
    cfg_dict: dict,
    user_id: str,
    server_name: str,
) -> tuple[str, str, bool, dict]:
    strata_meta = get_strata_meta(cfg_dict)
    strata_id = strata_meta.get("strata_id") or ""
    mcp_url = strata_meta.get("mcp_url") or ""

    if strata_id:
        try:
            info = await klavis.get_strata(strata_id)
            if info.mcp_url:
                mcp_url = info.mcp_url
            return strata_id, mcp_url, False, info.oauth_urls
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                clear_stale_strata(cfg_dict)
                strata_id = ""
            else:
                raise

    try:
        info = await klavis.create_strata(user_id, [server_name])
        strata_id = info.strata_id
        mcp_url = info.mcp_url
        if CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[CONNECTED_APPS_KEY] is None:
            cfg_dict[CONNECTED_APPS_KEY] = {}
        cfg_dict[CONNECTED_APPS_KEY][STRATA_KEY] = {
            "strata_id": strata_id,
            "mcp_url": mcp_url,
            "user_id": user_id,
        }
        return strata_id, mcp_url, True, info.oauth_urls
    except KlavisLimitError:
        raise KlavisLimitError(LIMIT_ERROR_MSG)
