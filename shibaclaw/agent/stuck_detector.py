import logging
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

class StuckDetector:
    """
    Tracks agent progress and detects loops or lack of progress.
    If a loop or lack of progress is detected, it triggers a goal reassessment prompt.
    """
    def __init__(self, max_repeats: int = 3):
        self.max_repeats = max_repeats
        self.response_content_history: List[str] = []
        self.tool_sequence_history: List[List[str]] = []
        self.progress_metrics: List[Any] = []

    def add_response(self, content: str | None) -> bool:
        """
        Adds response content and checks if the agent is stuck repeating the same response.
        """
        if not content:
            return False
        clean_content = content.strip()
        if not clean_content:
            return False
        
        self.response_content_history.append(clean_content)
        if len(self.response_content_history) >= self.max_repeats:
            last_n = self.response_content_history[-self.max_repeats:]
            if all(x == last_n[0] for x in last_n):
                logger.warning("StuckDetector: Repeating response content detected.")
                return True
        return False

    def add_tool_sequence(self, tool_names: List[str]) -> bool:
        """
        Adds a tool sequence and checks if the agent is stuck repeating the same tool sequence.
        """
        if not tool_names:
            return False
        
        self.tool_sequence_history.append(tool_names)
        if len(self.tool_sequence_history) >= self.max_repeats:
            last_n = self.tool_sequence_history[-self.max_repeats:]
            if all(x == last_n[0] for x in last_n):
                logger.warning("StuckDetector: Repeating tool sequence detected: %s", tool_names)
                return True
        return False

    def add_progress_metric(self, metric: Any) -> bool:
        """
        Adds a progress metric (e.g., length of files, number of files, or any custom metric)
        and checks if progress has been flat/stagnant for too long.
        """
        self.progress_metrics.append(metric)
        if len(self.progress_metrics) >= self.max_repeats + 1:
            last_n = self.progress_metrics[-(self.max_repeats + 1):]
            # If the metric hasn't changed at all across max_repeats + 1 steps, we are flat
            if all(x == last_n[0] for x in last_n):
                logger.warning("StuckDetector: Progress metric has been flat for %d steps.", self.max_repeats + 1)
                return True
        return False

    def get_goal_reassessment_prompt(self, reason: str) -> Dict[str, Any]:
        """
        Returns a system message prompting the agent to reassess its current goal.
        """
        return {
            "role": "system",
            "content": (
                f"WARNING: Stuck loop detected ({reason}).\n\n"
                "GOAL REASSESSMENT REQUIRED:\n"
                "1. Stop repeating the same actions or responses.\n"
                "2. Reassess your current goal and the strategy you are using.\n"
                "3. Identify what is blocking progress (e.g., tool errors, incorrect assumptions, or missing information).\n"
                "4. Formulate a completely different approach or strategy to achieve the goal."
            )
        }
