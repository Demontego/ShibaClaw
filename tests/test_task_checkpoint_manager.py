from shibaclaw.agent.checkpoint_manager import TaskCheckpointManager

def test_task_checkpoint_manager_save_and_load(tmp_path):
    mgr = TaskCheckpointManager(tmp_path)
    
    task_id = "test_task_123"
    current_step = "step_2"
    state = {"processed_items": [1, 2, 3], "status": "in_progress"}
    
    # Save checkpoint
    assert mgr.save_task_checkpoint(task_id, current_step, state) is True
    
    # Load checkpoint
    loaded = mgr.load_task_checkpoint(task_id)
    assert loaded is not None
    assert loaded["task_id"] == task_id
    assert loaded["current_step"] == current_step
    assert loaded["state"] == state

def test_task_checkpoint_manager_load_nonexistent(tmp_path):
    mgr = TaskCheckpointManager(tmp_path)
    assert mgr.load_task_checkpoint("nonexistent_task") is None
