from __future__ import annotations

from shibaclaw.apps.models import AppDefinition, TrustLevel, RuntimeType, AppAuthDefinition
from shibaclaw.apps.registry.base import BaseAppRegistry
from shibaclaw.config.loader import load_config
from shibaclaw.integrations.registry import discover_plugins, discover_local_plugins
from shibaclaw.tts.registry import discover_tts_plugins
from shibaclaw.agent.knowledge_manager import is_rag_available


_WELL_KNOWN_NATIVE_PLUGINS = [
    {
        "id": "whatsapp",
        "name": "WhatsApp",
        "package_name": "shibaclaw-channel-whatsapp",
        "description": "WhatsApp channel integration using a Node.js bridge (Baileys).",
        "icon": "chat",
        "category": "communication",
        "capabilities": ["Direct messaging", "Group chats", "Media delivery"],
    },
    {
        "id": "supertonic-tts",
        "name": "Supertonic TTS",
        "package_name": "shibaclaw-tts-supertonic",
        "description": "Local offline Text-to-Speech using the Supertonic ONNX engine.",
        "icon": "volume_up",
        "category": "media",
        "capabilities": ["Offline voice synthesis", "Low latency", "Multi-voice"],
    },
    {
        "id": "shibaclaw-rag",
        "name": "RAG & Knowledge Base",
        "package_name": "shibaclaw-rag",
        "description": "Semantic search and document uploading (PDF, CSV, HTML, TXT) via Hybrid RAG.",
        "icon": "menu_book",
        "category": "ai",
        "capabilities": ["Document ingestion", "Semantic search", "Knowledge retrieval"],
    },
]


class NativePluginRegistryProvider(BaseAppRegistry):
    def __init__(self) -> None:
        pass

    async def list_apps(self) -> list[AppDefinition]:
        cfg = load_config()
        installed_channels = {**discover_plugins(), **discover_local_plugins()}
        installed_tts = discover_tts_plugins()
        rag_installed = is_rag_available()

        apps: list[AppDefinition] = []

        # Well-known plugins
        for item in _WELL_KNOWN_NATIVE_PLUGINS:
            pkg = item["package_name"]
            is_inst = False
            is_en = False

            if pkg == "shibaclaw-channel-whatsapp":
                is_inst = "whatsapp" in installed_channels
                ch_sec = getattr(cfg.channels, "whatsapp", None)
                if isinstance(ch_sec, dict):
                    is_en = ch_sec.get("enabled", False)
                elif ch_sec:
                    is_en = getattr(ch_sec, "enabled", False)
            elif pkg == "shibaclaw-tts-supertonic":
                is_inst = "supertonic" in installed_tts
                is_en = bool(getattr(cfg.audio, "tts_provider", "") == "supertonic")
            elif pkg == "shibaclaw-rag":
                is_inst = rag_installed
                is_en = rag_installed

            apps.append(
                AppDefinition(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    icon=item["icon"],
                    category=item["category"],
                    source="native",
                    runtime_type=RuntimeType.NATIVE_PLUGIN.value,
                    trust_level=TrustLevel.OFFICIAL.value,
                    version="1.0.0",
                    package_name=pkg,
                    installed=is_inst,
                    enabled=is_en,
                    status="connected" if (is_inst and is_en) else ("disabled" if is_inst else "ready"),
                    auth=AppAuthDefinition(type="none"),
                    capabilities=item["capabilities"],
                )
            )

        # Also capture any other custom installed channels or TTS plugins
        known_ids = {a.id for a in apps}
        for name, cls in installed_channels.items():
            if name in ("whatsapp",) or name in known_ids:
                continue
            disp = getattr(cls, "display_name", name.title())
            ch_sec = getattr(cfg.channels, name, None)
            enabled = False
            if isinstance(ch_sec, dict):
                enabled = ch_sec.get("enabled", False)
            elif ch_sec:
                enabled = getattr(ch_sec, "enabled", False)

            apps.append(
                AppDefinition(
                    id=f"channel-{name}",
                    name=disp,
                    description=f"{disp} chat channel integration.",
                    icon="forum",
                    category="communication",
                    source="native",
                    runtime_type=RuntimeType.NATIVE_PLUGIN.value,
                    trust_level=TrustLevel.VERIFIED.value,
                    version="1.0.0",
                    package_name=f"shibaclaw-channel-{name}",
                    installed=True,
                    enabled=enabled,
                    status="connected" if enabled else "disabled",
                    auth=AppAuthDefinition(type="none"),
                    capabilities=["Channel messaging"],
                )
            )

        for name, cls in installed_tts.items():
            if name in ("supertonic",) or name in known_ids:
                continue
            disp = getattr(cls, "display_name", name.title())
            enabled = bool(getattr(cfg.audio, "tts_provider", "") == name)
            apps.append(
                AppDefinition(
                    id=f"tts-{name}",
                    name=disp,
                    description=f"{disp} text-to-speech engine.",
                    icon="volume_up",
                    category="media",
                    source="native",
                    runtime_type=RuntimeType.NATIVE_PLUGIN.value,
                    trust_level=TrustLevel.VERIFIED.value,
                    version="1.0.0",
                    package_name=f"shibaclaw-tts-{name}",
                    installed=True,
                    enabled=enabled,
                    status="connected" if enabled else "disabled",
                    auth=AppAuthDefinition(type="none"),
                    capabilities=["Speech synthesis"],
                )
            )

        return apps

    async def get_app(self, app_id: str) -> AppDefinition | None:
        apps = await self.list_apps()
        for a in apps:
            if a.id == app_id or a.package_name == app_id:
                return a
        return None
