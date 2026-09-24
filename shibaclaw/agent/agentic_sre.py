import logging
from typing import Any, Dict, Tuple
from pathlib import Path
from shibaclaw.agent.sre_monitor import SREMonitor
from shibaclaw.agent.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)

class SREMonitorAgent:
    """
    Specialized SRE Agent responsible for monitoring the main agent loop.
    Analyzes liveness, progress, and quality metrics.
    """
    def __init__(self, monitor: SREMonitor):
        self.monitor = monitor

    def analyze_health(self) -> Tuple[bool, str]:
        """
        Analyzes the health of the agent loop.
        Returns (is_healthy, reason_if_unhealthy).
        """
        status = self.monitor.get_status()
        if not status["healthy"]:
            reasons = []
            if status["liveness"] == "FAIL":
                reasons.append("Liveness failure (looping or repeating content)")
            if status["progress"] == "FAIL":
                reasons.append("Progress failure (stalled progress metric)")
            if status["quality"] == "FAIL":
                reasons.append("Quality failure (malformed or error-dense responses)")
            return False, "; ".join(reasons)
        return True, "Healthy"

class SRERecoveryAgent:
    """
    Specialized SRE Agent responsible for executing recovery actions.
    Can inject reassessment prompts, rollback to checkpoints, or trigger model fallbacks.
    """
    def __init__(self, checkpoint_mgr: CheckpointManager):
        self.checkpoint_mgr = checkpoint_mgr

    def get_recovery_action(self, reason: str, session_key: str) -> Dict[str, Any]:
        """
        Determines and returns the appropriate recovery action based on the failure reason.
        """
        logger.info("SRERecoveryAgent: Determining recovery action for reason: %s", reason)
        
        if "Liveness" in reason or "Progress" in reason:
            # For loops or stalls, inject a goal reassessment prompt
            return {
                "type": "inject_prompt",
                "prompt": (
                    "\n\n[SRE Recovery Agent] WARNING: I detected a potential loop or progress stall. "
                    "Let's pause, re-evaluate our current goal, and determine if we need to adjust our approach "
                    "or use different tools to make progress."
                )
            }
        elif "Quality" in reason:
            # For quality degradation, recommend rolling back to the last checkpoint if available
            checkpoint = self.checkpoint_mgr.load_checkpoint(session_key) if session_key else None
            if checkpoint:
                return {
                    "type": "rollback",
                    "session_key": session_key,
                    "message": "[SRE Recovery Agent] Quality degradation detected. Rolling back to the last healthy checkpoint."
                }
        
        return {"type": "none"}

class SREAuditAgent:
    """
    Specialized SRE Agent responsible for auditing execution history and logging learnings.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.learnings_file = workspace / "memory" / "learnings.md"

    def log_learning(self, session_key: str, issue: str, resolution: str) -> None:
        """
        Logs a learning entry to memory/learnings.md to prevent future failures.
        """
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = f"\n- [SRE Audit] Session {session_key}: Detected {issue}. Resolved via {resolution}.\n"
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("SREAuditAgent: Logged learning for session %s", session_key)
        except Exception as e:
            logger.error("SREAuditAgent: Failed to log learning: %s", e)

class AgenticSRE:
    """
    Coordinates the specialized SRE agents (Monitor, Recovery, Audit)
    to provide autonomous self-healing capabilities for the main agent loop.
    """
    def __init__(self, workspace: Path, monitor: SREMonitor, checkpoint_mgr: CheckpointManager):
        self.workspace = workspace
        self.monitor_agent = SREMonitorAgent(monitor)
        self.recovery_agent = SRERecoveryAgent(checkpoint_mgr)
        self.audit_agent = SREAuditAgent(workspace)

    def run_sre_cycle(self, session_key: str) -> Dict[str, Any]:
        """
        Runs a full SRE cycle: monitors health, determines recovery if needed, and logs audits.
        """
        is_healthy, reason = self.monitor_agent.analyze_health()
        if not is_healthy:
            action = self.recovery_agent.get_recovery_action(reason, session_key)
            self.audit_agent.log_learning(session_key, reason, action["type"])
            return {
                "healthy": False,
                "reason": reason,
                "action": action
            }
        return {"healthy": True, "reason": "Healthy", "action": {"type": "none"}}
