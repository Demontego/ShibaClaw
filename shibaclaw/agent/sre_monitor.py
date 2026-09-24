import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class SREMonitor:
    """
    SRE Monitor for AI Agent loops.
    Tracks Liveness, Progress, and Quality metrics to detect hangs, loops, and quality degradation.
    """
    def __init__(self, max_consecutive_repeats: int = 3, progress_threshold: float = 0.01):
        self.max_consecutive_repeats = max_consecutive_repeats
        self.progress_threshold = progress_threshold
        
        # History tracking
        self.response_history: List[str] = []
        self.tool_sequence_history: List[List[str]] = []
        self.progress_metrics: List[float] = []

    def add_response(self, content: str) -> None:
        """Adds a response content to the history."""
        if content:
            self.response_history.append(content.strip())

    def add_tool_sequence(self, tools: List[str]) -> None:
        """Adds a sequence of executed tools to the history."""
        self.tool_sequence_history.append(tools)

    def add_progress_metric(self, metric: float) -> None:
        """Adds a progress metric value to the history."""
        self.progress_metrics.append(metric)

    def check_liveness(self) -> bool:
        """
        Checks if the agent is still live (not stuck in a loop or repeating content).
        Returns True if healthy, False if a liveness failure is detected.
        """
        # 1. Check for repeating response content
        if len(self.response_history) >= self.max_consecutive_repeats:
            last_n = self.response_history[-self.max_consecutive_repeats:]
            if len(set(last_n)) == 1:
                logger.warning("SREMonitor: Liveness failure detected - repeating response content.")
                return False

        # 2. Check for repeating tool sequences (infinite loops)
        if len(self.tool_sequence_history) >= 3:
            last_three = self.tool_sequence_history[-3:]
            if last_three[0] == last_three[1] == last_three[2] and len(last_three[0]) > 0:
                logger.warning("SREMonitor: Liveness failure detected - repeating tool sequence loop.")
                return False

        return True

    def check_progress(self) -> bool:
        """
        Checks if the agent is making progress towards the goal.
        Returns True if healthy, False if a progress failure is detected.
        """
        if len(self.progress_metrics) < 2:
            return True

        # Check if the progress metric has improved (increased or decreased depending on the metric,
        # but here we assume an increasing metric where higher is better).
        # If the metric remains completely flat for too long, progress has stalled.
        if len(self.progress_metrics) >= 3:
            last_three = self.progress_metrics[-3:]
            if abs(last_three[-1] - last_three[0]) < self.progress_threshold:
                logger.warning("SREMonitor: Progress failure detected - progress metric has stalled.")
                return False

        return True

    def check_quality(self) -> bool:
        """
        Checks the quality of the agent's responses.
        Returns True if healthy, False if a quality failure is detected.
        """
        if not self.response_history:
            return True

        last_response = self.response_history[-1]
        
        # 1. Check for extremely short or empty responses
        if len(last_response) < 5:
            logger.warning("SREMonitor: Quality failure detected - response is extremely short or empty.")
            return False

        # 2. Check for obvious hallucination or error patterns in the response
        error_patterns = ["error:", "failed to", "exception occurred", "internal error"]
        for pattern in error_patterns:
            if pattern in last_response.lower() and last_response.lower().count(pattern) > 3:
                logger.warning("SREMonitor: Quality failure detected - high density of error patterns.")
                return False

        return True

    def get_status(self) -> Dict[str, Any]:
        """Returns the current status of all three SRE dimensions."""
        liveness_ok = self.check_liveness()
        progress_ok = self.check_progress()
        quality_ok = self.check_quality()
        
        healthy = liveness_ok and progress_ok and quality_ok
        
        return {
            "healthy": healthy,
            "liveness": "OK" if liveness_ok else "FAIL",
            "progress": "OK" if progress_ok else "FAIL",
            "quality": "OK" if quality_ok else "FAIL",
        }
