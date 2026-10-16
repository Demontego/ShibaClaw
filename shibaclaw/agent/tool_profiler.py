import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ToolProfiler:
    """
    Automatic tool execution profiler.
    Tracks execution times of tool calls and logs slow calls (> 2.0s) to memory/learnings.md.
    """
    def __init__(self, workspace: Path, slow_threshold_seconds: float = 2.0):
        self.workspace = workspace
        self.slow_threshold_seconds = slow_threshold_seconds
        self.learnings_file = workspace / "memory" / "learnings.md"
        self.execution_times = {}  # tool_name -> list of float times

    def record_execution(self, tool_name: str, duration: float) -> None:
        """Records a tool execution duration and logs if it is slow."""
        if tool_name not in self.execution_times:
            self.execution_times[tool_name] = []
        self.execution_times[tool_name].append(duration)

        avg_duration = sum(self.execution_times[tool_name]) / len(self.execution_times[tool_name])
        logger.info(
            "ToolProfiler: Tool '%s' executed in %.2fs (avg: %.2fs)",
            tool_name,
            duration,
            avg_duration
        )

        if duration >= self.slow_threshold_seconds:
            logger.warning(
                "ToolProfiler: Slow tool execution detected for '%s' (%.2fs >= %.2fs)",
                tool_name,
                duration,
                self.slow_threshold_seconds
            )
            self.log_slow_execution(tool_name, duration, avg_duration)

    def log_slow_execution(self, tool_name: str, duration: float, avg_duration: float) -> None:
        """Logs the slow tool execution incident to memory/learnings.md."""
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Slow Tool Execution] Tool: {tool_name} | "
                f"Duration: {duration:.2f}s (avg: {avg_duration:.2f}s) | "
                f"Action: Profiled and flagged for performance optimization.\n"
            )
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("ToolProfiler: Logged slow tool execution incident")
        except Exception as e:
            logger.error("ToolProfiler: Failed to log slow tool execution incident: %s", e)
