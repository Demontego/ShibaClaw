from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TrustLevel(str, Enum):
    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"
    CUSTOM = "custom"


class RuntimeType(str, Enum):
    MCP_REMOTE = "mcp_remote"
    MCP_LOCAL = "mcp_local"
    NATIVE_PLUGIN = "native_plugin"


class AuthType(str, Enum):
    NONE = "none"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BEARER = "bearer"
    CUSTOM = "custom"


class AuthState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    EXPIRED = "expired"
    REFRESH_FAILED = "refresh_failed"
    NEEDS_REAUTH = "needs_reauthentication"


class AppAuthField(BaseModel):
    key: str
    label: str
    type: str = "text"
    required: bool = True
    placeholder: str = ""
    help_text: str = ""


class AppAuthDefinition(BaseModel):
    type: str = "none"
    auth_url: str = ""
    token_url: str = ""
    client_id: str = ""
    scopes: list[str] = Field(default_factory=list)
    requires_client_credentials: bool = False
    fields: list[AppAuthField] = Field(default_factory=list)


class AppDefinition(BaseModel):
    id: str
    name: str
    description: str
    icon: str = "extension"
    category: str = "productivity"
    source: str = "curated"
    runtime_type: str = "mcp_remote"
    trust_level: str = "official"
    version: str = "1.0.0"
    auth: AppAuthDefinition = Field(default_factory=AppAuthDefinition)
    capabilities: list[str] = Field(default_factory=list)
    package_name: str | None = None
    mcp_config: dict[str, Any] = Field(default_factory=dict)
    installed: bool = False
    enabled: bool = True
    status: str = "ready"
    tools_count: int = 0
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    warning: str | None = None
    installed_at: float | None = None
    installed_version: str | None = None
    update_available: bool = False


class InstalledAppRecord(BaseModel):
    id: str
    name: str
    source: str = "curated"
    runtime_type: str = "mcp_remote"
    version: str = "1.0.0"
    installed_at: float = 0.0
    enabled: bool = True
    auth_state: str = "disconnected"
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])
    mcp_server_name: str | None = None
    package_name: str | None = None
    custom_config: dict[str, Any] = Field(default_factory=dict)
