import json
import logging
from typing import Any, List, Dict
from shibaclaw.agent.memory_guard import MemoryGuard

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
        self.tool_error_history: List[Dict[str, Any]] = []
        self.memory_guard = MemoryGuard(max_history_size=100)

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
        self.response_content_history = self.memory_guard.guard_list(self.response_content_history, "response_content_history")
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
        self.tool_sequence_history = self.memory_guard.guard_list(self.tool_sequence_history, "tool_sequence_history")
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
        self.progress_metrics = self.memory_guard.guard_list(self.progress_metrics, "progress_metrics")
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

    def add_tool_error(self, tool_name: str, error_message: str) -> bool:
        """
        Adds a tool error and checks if the same tool is failing repeatedly.
        """
        self.tool_error_history.append({"tool_name": tool_name, "error_message": error_message})
        self.tool_error_history = self.memory_guard.guard_list(self.tool_error_history, "tool_error_history")
        if len(self.tool_error_history) >= self.max_repeats:
            last_n = self.tool_error_history[-self.max_repeats:]
            # If the same tool failed max_repeats times in a row
            if all(x["tool_name"] == last_n[0]["tool_name"] for x in last_n):
                logger.warning("StuckDetector: Repeating tool error detected for tool: %s", tool_name)
                return True
        return False

    def get_tool_error_pivot_prompt(self, tool_name: str, error_message: str) -> Dict[str, Any]:
        """
        Returns a system message prompting the agent to pivot strategy due to repeated tool errors.
        """
        return {
            "role": "system",
            "content": (
                f"CRITICAL: Tool '{tool_name}' has failed repeatedly with the following error:\n"
                f"\"{error_message}\"\n\n"
                "STRATEGY PIVOT REQUIRED:\n"
                "1. DO NOT call this tool again with the same arguments.\n"
                "2. Pivot your strategy immediately. Use an alternative tool, decompose the task, or fall back to a different approach.\n"
                "3. If you are trying to read/write a file, check if the path is correct or if you need to list the directory first.\n"
                "4. If you are executing a command, check if the command is available or if there is a simpler way to achieve the result."
            )
        }

    async def classify_intent_and_detect_loop_async(
        self,
        response_content: str,
        provider: Any,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Uses a lightweight decision model to classify the agent's intent and detect semantic loops
        in the hot path of StuckDetector.
        """
        if not provider or not response_content:
            return {"intent": "unknown", "is_loop": False, "confidence": 0.0}

        prompt = (
            "You are a high-speed intent classifier and loop detector. "
            "Analyze the following agent response and classify its intent and whether it is stuck in a semantic loop.\n\n"
            f"Agent Response:\n{response_content}\n\n"
            "Respond with a JSON object containing:\n"
            "1. 'intent': string (e.g., 'file_read', 'command_exec', 'web_search', 'conversation', 'error_recovery')\n"
            "2. 'is_loop': boolean (true if the agent is repeating itself, asking the same question, or stuck in a loop)\n"
            "3. 'confidence': float (0.0 to 1.0)\n"
            "4. 'reason': string (brief explanation)\n\n"
            "JSON output only:"
        )

        try:
            active_model = model or "google/gemini-2.5-flash"
            response = await provider.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                model=active_model,
            )
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            logger.info("StuckDetector: High-speed decision model result: {}", result)
            return result
        except Exception as e:
            logger.error("StuckDetector: Failed to classify intent and detect loop: {}", e)
            return {"intent": "unknown", "is_loop": False, "confidence": 0.0, "error": str(e)}

