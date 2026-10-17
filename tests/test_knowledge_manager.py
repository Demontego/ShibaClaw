from shibaclaw.agent.knowledge_manager import KnowledgeManager


def test_path_traversal_filename(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.create_collection("test", "test col")
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello")

    km.add_document("test", dummy_file, "../../../hacked.txt")

    docs_dir = km._collection_dir("test") / "docs"
    assert (docs_dir / "hacked.txt").exists()
    assert "hacked.txt" in km.search(["test"], "hello")[0].metadata["source"]


def test_non_text_upload_leaves_no_file(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.create_collection("test", "test col")
    dummy_file = tmp_path / "dummy.pdf"
    dummy_file.write_text("hello")

    try:
        km.add_document("test", dummy_file, "dummy.pdf")
        raise AssertionError("pdf upload should fail")
    except ValueError as exc:
        assert "Markdown" in str(exc)

    assert not (km._collection_dir("test") / "docs" / "dummy.pdf").exists()


def test_sync_drops_faiss_and_builds_tantivy(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.create_collection("test", "test col")
    docs = km._collection_dir("test") / "docs"
    (docs / "a.md").write_text("alpha funder")
    legacy = km._collection_dir("test") / "index"
    legacy.mkdir()
    (legacy / "index.faiss").write_bytes(b"old")
    (legacy / "index.pkl").write_bytes(b"old")
    (km._collection_dir("test") / "meta.json.lock").write_text("x")

    assert km.list_collections()[0]["id"] == "test"
    assert not legacy.exists()
    assert not (km._collection_dir("test") / "meta.json.lock").exists()
    assert (km._collection_dir("test") / "tantivy" / "meta.json").is_file()
    assert "alpha" in km.search(["test"], "funder")[0].page_content


def test_search_finds_markdown_after_rebuild(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.create_collection("test", "test col")
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("proxy wallet funder")
    km.add_document("test", dummy_file, "dummy.txt")

    hit = km.search(["test"], "funder")[0]
    assert "proxy wallet" in hit.page_content
    km.delete_collection("test")
    assert km.search(["test"], "funder") == []
