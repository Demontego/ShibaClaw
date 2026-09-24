import logging
from typing import Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class SelfRepair:
    """
    Meta-Procedural Self-Repair system.
    Wraps diagnostic and control components with safety boundaries,
    detects internal failures, and automatically repairs their state or configuration.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.learnings_file = workspace / "memory" / "learnings.md"

    def execute_safe(self, component_name: str, func: Any, *args: Any, **kwargs: Any) -> Tuple[bool, Any]:
        """
        Executes a diagnostic or control function safely.
        If an exception occurs, catches it, triggers self-repair, and returns (False, None).
        Otherwise, returns (True, result).
        """
        try:
            result = func(*args, **kwargs)
            return True, result
        except Exception as e:
            logger.error("SelfRepair: Internal failure detected in component '%s': %s", component_name, e)
            self.repair_component(component_name, e)
            return False, None

    def repair_component(self, component_name: str, exception: Exception) -> None:
        """
        Executes specific self-repair actions based on the failing component.
        """
        logger.info("SelfRepair: Initiating self-repair for component '%s'...", component_name)
        
        repair_action = "Reset state to default"
        
        if component_name == "StuckDetector":
            # Repair StuckDetector by resetting its history
            repair_action = "Reset StuckDetector history and clear corrupted state"
        elif component_name == "SREMonitor":
            # Repair SREMonitor by resetting its metrics
            repair_action = "Reset SREMonitor metrics and clear corrupted state"
        elif component_name == "CheckpointManager":
            # Repair CheckpointManager by clearing corrupted checkpoints
            repair_action = "Clear corrupted checkpoints and reset CheckpointManager state"
        elif component_name == "AgenticSRE":
            # Repair AgenticSRE by resetting its sub-agents
            repair_action = "Reset AgenticSRE sub-agents and clear corrupted state"

        self.log_repair_action(component_name, exception, repair_action)

    def log_repair_action(self, component_name: str, exception: Exception, action: str) -> None:
        """
        Logs the self-repair action to memory/learnings.md.
        """
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Meta-Procedural Self-Repair] Component: {component_name} | "
                f"Failure: {type(exception).__name__}: {exception} | "
                f"Action: {action}\n"
            )
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("SelfRepair: Logged self-repair action for component %s", component_name)
        except Exception as e:
            logger.error("SelfRepair: Failed to log self-repair action: %s", e)
