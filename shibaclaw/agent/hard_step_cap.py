import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class HardStepCap:
    """
    Hard Step Cap system.
    Enforces a strict, non-bypassable upper limit on the number of steps/iterations
    to prevent infinite loops and runaway execution.
    """
    def __init__(self, workspace: Path, hard_limit: int = 50):
        self.workspace = workspace
        self.hard_limit = hard_limit
        self.learnings_file = workspace / "memory" / "learnings.md"

    def check_step_limit(self, current_step: int) -> bool:
        """
        Checks if the current step exceeds the hard limit.
        If it does, logs the incident and returns False.
        Otherwise, returns True.
        """
        if current_step >= self.hard_limit:
            logger.error(
                "HardStepCap: Hard step limit of %d reached at step %d! Preventing further execution.",
                self.hard_limit,
                current_step
            )
            self.log_cap_exceeded(current_step)
            return False
        return True

    def log_cap_exceeded(self, current_step: int) -> None:
        """
        Logs the hard step cap exceeded incident to memory/learnings.md.
        """
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Hard Step Cap Exceeded] Step: {current_step} | "
                f"Limit: {self.hard_limit} | "
                f"Action: Enforced hard stop to prevent infinite loop and runaway execution.\n"
            )
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("HardStepCap: Logged step cap exceeded incident")
        except Exception as e:
            logger.error("HardStepCap: Failed to log step cap exceeded incident: %s", e)
