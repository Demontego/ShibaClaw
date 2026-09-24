import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
from shibaclaw.agent.stuck_detector import StuckDetector
from shibaclaw.agent.sre_monitor import SREMonitor
from shibaclaw.agent.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)

class LayeredDefense:
    """
    Coordinates all reliability and safety mechanisms (StuckDetector, SREMonitor, CheckpointManager)
    into a single, cohesive, layered defense system.
    """
    def __init__(self, workspace: Path, session_key: str | None = None):
        self.workspace = workspace
        self.session_key = session_key
        
        # Initialize defense layers
        self.stuck_detector = StuckDetector()
        self.sre_monitor = SREMonitor()
        self.checkpoint_mgr = CheckpointManager(workspace)

    def record_iteration(
        self,
        iteration: int,
        response_content: str | None,
        tool_names: List[str] | None,
        progress_metric: float | None,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any] | None = None,
    ) -> Tuple[bool, str | None]:
        """
        Records the results of an iteration across all defense layers.
        Returns (should_continue, recovery_prompt).
        """
        # 1. Update SRE Monitor
        if response_content:
            self.sre_monitor.add_response(response_content)
        if tool_names:
            self.sre_monitor.add_tool_sequence(tool_names)
        if progress_metric is not None:
            self.sre_monitor.add_progress_metric(progress_metric)

        # 2. Update Stuck Detector and check for loops/stalls
        if response_content and self.stuck_detector.add_response(response_content):
            logger.warning("LayeredDefense: StuckDetector triggered on repeating response content.")
            return True, self.stuck_detector.get_goal_reassessment_prompt("repeating response content")

        if tool_names and self.stuck_detector.add_tool_sequence(tool_names):
            logger.warning("LayeredDefense: StuckDetector triggered on repeating tool sequence.")
            return True, self.stuck_detector.get_goal_reassessment_prompt("repeating tool sequence")

        if progress_metric is not None and self.stuck_detector.add_progress_metric(progress_metric):
            logger.warning("LayeredDefense: StuckDetector triggered on flat progress metric.")
            return True, self.stuck_detector.get_goal_reassessment_prompt("lack of progress / flat progress metric")

        # 3. Save checkpoint
        if self.session_key:
            self.checkpoint_mgr.save_checkpoint(self.session_key, messages, iteration, metadata)

        # 4. Check SRE Monitor health status
        sre_status = self.sre_monitor.get_status()
        if not sre_status["healthy"]:
            logger.warning("LayeredDefense: SRE Monitor detected unhealthy state: %s", sre_status)
            # If quality is failing, we can inject a quality recovery prompt
            if sre_status["quality"] == "FAIL":
                return True, "Warning: The quality of your recent responses has degraded (extremely short or high error density). Please reassess your approach and provide a high-quality, detailed response."

        return True, None

    def cleanup(self) -> None:
        """Cleans up checkpoints and other resources when the task is completed."""
        if self.session_key:
            self.checkpoint_mgr.delete_checkpoint(self.session_key)
