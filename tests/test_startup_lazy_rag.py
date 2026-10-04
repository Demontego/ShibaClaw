"""Cold-start regressions: optional ML imports must not delay the desktop UI."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("rag_installed", [True, False])
def test_cold_gateway_and_webui_start_without_loading_rag(tmp_path, rag_installed):
    # A fresh interpreter is essential: collection of other RAG tests can warm
    # sys.modules and hide the first-launch regression.
    script = r'''
import asyncio
import builtins
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

workspace = Path(sys.argv[1])
installed = sys.argv[2] == "True"
heavy = {"langchain", "langchain_core", "langchain_community",
         "langchain_text_splitters", "faiss", "transformers", "torch",
         "sentence_transformers"}
real_import = builtins.__import__
real_find_spec = importlib.util.find_spec
attempted_imports = []

def guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in heavy:
        attempted_imports.append(name)
        raise AssertionError(f"Startup imported optional ML dependency: {name}")
    return real_import(name, *args, **kwargs)

def find_spec(name, *args, **kwargs):
    if name in heavy or name == "filelock":
        return importlib.machinery.ModuleSpec(name, loader=None) if installed else None
    return real_find_spec(name, *args, **kwargs)

with patch.object(builtins, "__import__", side_effect=guarded_import), \
     patch.object(importlib.util, "find_spec", side_effect=find_spec), \
     patch("pathlib.Path.home", return_value=workspace):
    from shibaclaw.agent.knowledge_manager import KnowledgeManager, is_rag_available
    assert is_rag_available() is installed

    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.config.schema import Config
    cfg = Config()
    cfg.agents.defaults.workspace = str(workspace)
    async def start_brain():
        brain = ShibaBrain(
            bus=MagicMock(), provider=None, workspace=workspace, config=cfg,
            web_search_config=cfg.tools.web.search, exec_config=cfg.tools.exec,
        )
        try:
            assert brain.tools.has("knowledge_search") is installed
        finally:
            await brain.close_mcp()
    asyncio.run(start_brain())

    # The WebUI asks for collection metadata during startApp(), even with no
    # knowledge bases configured. This must not initialize the text splitter.
    km = KnowledgeManager(workspace)
    assert km.list_collections() == []
    from shibaclaw.webui.agent_manager import agent_manager
    from shibaclaw.webui.routers.knowledge import api_knowledge_list
    agent_manager.config = cfg
    response = asyncio.run(api_knowledge_list(None))
    assert response.status_code == (200 if installed else 500)
    assert attempted_imports == [], attempted_imports
print("cold-start-ok")
'''
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(rag_installed)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cold-start-ok" in result.stdout


def test_rag_operations_report_missing_dependencies(tmp_path, monkeypatch):
    from shibaclaw.agent import knowledge_manager as module

    monkeypatch.setattr(module, "_rag_available", False)
    monkeypatch.setattr(module, "_rag_loaded", False)
    km = module.KnowledgeManager(tmp_path)
    assert km.list_collections() == []
    with pytest.raises(RuntimeError, match="RAG dependencies are not installed"):
        km.search(["example"], "query")
    with pytest.raises(RuntimeError, match="RAG dependencies are not installed"):
        km.add_document("example", tmp_path / "sample.txt", "sample.txt")
