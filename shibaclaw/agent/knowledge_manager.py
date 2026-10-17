# host-anchor: shibaclaw/agent/knowledge_manager.py
"""BM25 search over knowledge-base Markdown. Tantivy replaces the FAISS RAG stack."""

from __future__ import annotations

import json
import re
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_TEXT_SUFFIXES = {".md", ".txt", ".markdown"}
_INDEX_LOCK = threading.Lock()


def is_rag_available() -> bool:
    """True when Tantivy is importable. The name stays for existing callers."""
    try:
        import tantivy  # noqa: F401
    except ImportError:
        return False
    return True


def __getattr__(name: str) -> Any:
    if name == "RAG_AVAILABLE":
        return is_rag_available()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class KnowledgeManager:
    def __init__(self, workspace_path: Path | str):
        self.workspace_path = Path(workspace_path)

    def _root(self) -> Path:
        return self.workspace_path / "memory" / "knowledge"

    def _collection_dir(self, collection_id: str) -> Path:
        if not _ID_RE.fullmatch(collection_id):
            raise ValueError(f"invalid collection id: {collection_id}")
        root = self._root().resolve()
        path = (root / collection_id).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"invalid collection id: {collection_id}")
        return path

    def list_collections(self) -> list[dict[str, Any]]:
        root = self._root()
        if not root.is_dir():
            return []
        found: list[dict[str, Any]] = []
        for meta_path in sorted(root.glob("*/meta.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(meta, dict) and meta.get("id"):
                found.append(meta)
        self.sync_indexes()
        return found

    def sync_indexes(self) -> None:
        """Drop leftover FAISS dirs and rebuild Tantivy from the collection files."""
        root = self._root()
        if not root.is_dir() or not is_rag_available():
            return
        for meta_path in sorted(root.glob("*/meta.json")):
            collection = meta_path.parent
            self._drop_legacy(collection)
            sources = self._source_files(collection)
            if sources and self._needs_rebuild(collection, sources):
                self._rebuild(collection)

    def _drop_legacy(self, collection: Path) -> None:
        legacy = collection / "index"
        if (legacy / "index.faiss").is_file() or (legacy / "index.pkl").is_file():
            shutil.rmtree(legacy)
        lock = collection / "meta.json.lock"
        if lock.is_file():
            lock.unlink()

    def create_collection(
        self, collection_id: str, name: str, description: str = ""
    ) -> dict[str, Any]:
        path = self._collection_dir(collection_id)
        if (path / "meta.json").exists():
            raise ValueError(f"collection already exists: {collection_id}")
        (path / "docs").mkdir(parents=True, exist_ok=True)
        meta = {
            "id": collection_id,
            "name": name,
            "description": description,
            "files": [],
        }
        (path / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return meta

    def update_collection(
        self, collection_id: str, name: str | None = None, description: str | None = None
    ) -> dict[str, Any]:
        path = self._collection_dir(collection_id)
        meta_path = path / "meta.json"
        if not meta_path.is_file():
            raise ValueError(f"unknown collection: {collection_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if name is not None:
            meta["name"] = name
        if description is not None:
            meta["description"] = description
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return meta

    def delete_collection(self, collection_id: str) -> None:
        path = self._collection_dir(collection_id)
        if not path.is_dir():
            raise ValueError(f"unknown collection: {collection_id}")
        shutil.rmtree(path)

    def add_document(self, collection_id: str, src: Path | str, filename: str) -> None:
        path = self._collection_dir(collection_id)
        if not (path / "meta.json").is_file():
            raise ValueError(f"unknown collection: {collection_id}")
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("invalid filename")
        suffix = Path(safe_name).suffix.lower()
        if suffix not in _TEXT_SUFFIXES:
            raise ValueError("only Markdown and text files can be indexed")
        docs = path / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        dest = docs / safe_name
        try:
            shutil.copyfile(src, dest)
            self._remember_file(path, safe_name)
            self._rebuild(path)
        except Exception:
            dest.unlink(missing_ok=True)
            raise

    def search(self, collection_ids: list[str], query: str, k: int = 5) -> list[Any]:
        if not query or not str(query).strip():
            return []
        hits: list[Any] = []
        for collection_id in collection_ids:
            try:
                path = self._collection_dir(collection_id)
            except ValueError:
                continue
            if not (path / "meta.json").is_file():
                continue
            hits.extend(self._search_one(path, str(query), k))
        hits.sort(key=lambda item: item.metadata["score"], reverse=True)
        return hits[:k]

    def _remember_file(self, collection: Path, filename: str) -> None:
        meta_path = collection / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        files = list(meta.get("files") or [])
        if filename not in files:
            files.append(filename)
        meta["files"] = files
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    def _source_files(self, collection: Path) -> list[Path]:
        docs = (collection / "docs").resolve()
        if not docs.is_dir():
            return []
        found: list[Path] = []
        for path in docs.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            resolved = path.resolve()
            if docs == resolved or docs not in resolved.parents:
                continue
            found.append(path)
        return found

    def _needs_rebuild(self, collection: Path, sources: list[Path]) -> bool:
        index_dir = collection / "tantivy"
        if not (index_dir / "meta.json").is_file():
            return True
        stamp = (index_dir / ".stamp").stat().st_mtime if (index_dir / ".stamp").is_file() else 0
        return any(src.stat().st_mtime > stamp for src in sources)

    def _rebuild(self, collection: Path) -> None:
        import tantivy

        sources = self._source_files(collection)
        index_dir = collection / "tantivy"
        with _INDEX_LOCK:
            if index_dir.exists():
                shutil.rmtree(index_dir)
            index_dir.mkdir(parents=True)
            schema = (
                tantivy.SchemaBuilder()
                .add_text_field("path", stored=True)
                .add_text_field("body", stored=True)
                .build()
            )
            index = tantivy.Index(schema, path=str(index_dir))
            writer = index.writer()
            for src in sources:
                rel = src.relative_to(collection / "docs").as_posix()
                text = src.read_text(encoding="utf-8", errors="replace")
                writer.add_document(tantivy.Document(path=rel, body=text))
            writer.commit()
            (index_dir / ".stamp").write_text("ok", encoding="utf-8")

    def _search_one(self, collection: Path, query: str, k: int) -> list[Any]:
        import tantivy

        sources = self._source_files(collection)
        if not sources:
            return []
        if self._needs_rebuild(collection, sources):
            self._rebuild(collection)
        index = tantivy.Index.open(str(collection / "tantivy"))
        parsed = _parse_query(index, query)
        if parsed is None:
            return []
        searcher = index.searcher()
        hits: list[Any] = []
        for score, address in searcher.search(parsed, k).hits:
            doc = searcher.doc(address)
            body = _field(doc, "body")
            rel = _field(doc, "path") or "unknown"
            # shortcut: whole file is returned, split snippets when a doc exceeds the prompt
            hits.append(
                SimpleNamespace(
                    page_content=body,
                    metadata={"source": f"{collection.name}/{rel}", "score": float(score)},
                )
            )
        return hits


def _field(doc: Any, name: str) -> str:
    value = doc.get_first(name) if hasattr(doc, "get_first") else None
    if value is None:
        try:
            value = doc[name]
        except Exception:
            return ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _parse_query(index: Any, text: str) -> Any:
    try:
        return index.parse_query(text, ["body"])
    except Exception:
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        if not words:
            return None
        return index.parse_query(" OR ".join(words[:12]), ["body"])
