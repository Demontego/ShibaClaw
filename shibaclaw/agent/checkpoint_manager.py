import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

class CheckpointManager:
    """
    Manages checkpoints for long-running multi-step tasks.
    Saves and resumes the state of the agent loop (messages, iteration, etc.).
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.checkpoints_dir = workspace / "memory" / "checkpoints"

    def _get_checkpoint_path(self, session_key: str) -> Path:
        return self.checkpoints_dir / f"{session_key}.json"

    def save_checkpoint(
        self,
        session_key: str,
        messages: List[Dict[str, Any]],
        iteration: int,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        """
        Saves the current state of the agent loop to a checkpoint file.
        """
        if not session_key:
            return False
        try:
            self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_path = self._get_checkpoint_path(session_key)
            
            data = {
                "session_key": session_key,
                "iteration": iteration,
                "messages": messages,
                "metadata": metadata or {},
            }
            
            # Write to temp file first, then atomic rename
            temp_path = checkpoint_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            temp_path.rename(checkpoint_path)
            
            logger.info("CheckpointManager: Saved checkpoint for session %s at iteration %d", session_key, iteration)
            return True
        except Exception as e:
            logger.error("CheckpointManager: Failed to save checkpoint for session %s: %s", session_key, e)
            return False

    def load_checkpoint(self, session_key: str) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]] | None:
        """
        Loads the state of the agent loop from a checkpoint file if it exists.
        """
        if not session_key:
            return None
        checkpoint_path = self._get_checkpoint_path(session_key)
        if not checkpoint_path.is_file():
            return None
        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            logger.info("CheckpointManager: Loaded checkpoint for session %s at iteration %d", session_key, data.get("iteration", 0))
            return data.get("messages", []), data.get("iteration", 0), data.get("metadata", {})
        except Exception as e:
            logger.error("CheckpointManager: Failed to load checkpoint for session %s: %s", session_key, e)
            return None

    def delete_checkpoint(self, session_key: str) -> bool:
        """
        Deletes the checkpoint file for a session.
        """
        if not session_key:
            return False
        checkpoint_path = self._get_checkpoint_path(session_key)
        if checkpoint_path.is_file():
            try:
                checkpoint_path.unlink()
                logger.info("CheckpointManager: Deleted checkpoint for session %s", session_key)
                return True
            except Exception as e:
                logger.error("CheckpointManager: Failed to delete checkpoint for session %s: %s", session_key, e)
        return False
