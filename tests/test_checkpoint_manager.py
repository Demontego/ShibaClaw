from pathlib import Path
from shibaclaw.agent.checkpoint_manager import CheckpointManager

def test_checkpoint_manager_save_load_delete(tmp_path: Path):
    mgr = CheckpointManager(tmp_path)
    session_key = "test_session_123"
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    iteration = 2
    metadata = {"model": "test-model"}

    # 1. Save checkpoint
    assert mgr.save_checkpoint(session_key, messages, iteration, metadata)

    # Verify file exists
    checkpoint_file = tmp_path / "memory" / "checkpoints" / f"{session_key}.json"
    assert checkpoint_file.is_file()

    # 2. Load checkpoint
    loaded = mgr.load_checkpoint(session_key)
    assert loaded is not None
    loaded_messages, loaded_iteration, loaded_metadata = loaded
    assert loaded_messages == messages
    assert loaded_iteration == iteration
    assert loaded_metadata == metadata

    # 3. Delete checkpoint
    assert mgr.delete_checkpoint(session_key)
    assert not checkpoint_file.is_file()

    # Load after delete should be None
    assert mgr.load_checkpoint(session_key) is None

def test_checkpoint_manager_load_nonexistent(tmp_path: Path):
    mgr = CheckpointManager(tmp_path)
    assert mgr.load_checkpoint("nonexistent") is None

def test_checkpoint_manager_delete_nonexistent(tmp_path: Path):
    mgr = CheckpointManager(tmp_path)
    assert not mgr.delete_checkpoint("nonexistent")
