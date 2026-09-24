import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CostCircuitBreaker:
    """
    Cost Circuit Breaker system.
    Tracks the cumulative dollar cost of the session based on the model used
    and the prompt/completion tokens, and trips when the cost exceeds a threshold.
    """
    # Pricing per 1M tokens as of early 2026
    PRICING = {
        "google/gemini-3.5-flash": {"input": 0.075, "output": 0.30},
        "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "google/gemini-2.0-flash-lite": {"input": 0.08, "output": 0.30},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "default": {"input": 0.15, "output": 0.60},  # Fallback pricing
    }

    def __init__(self, workspace: Path, max_cost_usd: float = 1.0):
        self.workspace = workspace
        self.max_cost_usd = max_cost_usd
        self.cumulative_cost_usd = 0.0
        self.learnings_file = workspace / "memory" / "learnings.md"

    def record_usage(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculates the cost of the current turn and adds it to the cumulative cost.
        Returns the cost of the current turn in USD.
        """
        pricing = self.PRICING.get(model_name, self.PRICING["default"])
        
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        turn_cost = input_cost + output_cost
        
        self.cumulative_cost_usd += turn_cost
        logger.info(
            "CostCircuitBreaker: Turn cost: $%.6f | Cumulative cost: $%.6f / $%.2f",
            turn_cost,
            self.cumulative_cost_usd,
            self.max_cost_usd
        )
        return turn_cost

    def is_tripped(self) -> bool:
        """
        Checks if the cumulative cost exceeds the maximum allowed cost.
        If it does, logs the incident and returns True.
        Otherwise, returns False.
        """
        if self.cumulative_cost_usd >= self.max_cost_usd:
            logger.error(
                "CostCircuitBreaker: Cost limit of $%.2f exceeded! Current spend: $%.6f. Tripping circuit breaker.",
                self.max_cost_usd,
                self.cumulative_cost_usd
            )
            self.log_breaker_tripped()
            return True
        return False

    def log_breaker_tripped(self) -> None:
        """
        Logs the cost circuit breaker tripped incident to memory/learnings.md.
        """
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Cost Circuit Breaker Tripped] Spend: ${self.cumulative_cost_usd:.6f} | "
                f"Limit: ${self.max_cost_usd:.2f} | "
                f"Action: Tripped circuit breaker to prevent runaway API costs.\n"
            )
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("CostCircuitBreaker: Logged circuit breaker tripped incident")
        except Exception as e:
            logger.error("CostCircuitBreaker: Failed to log circuit breaker tripped incident: %s", e)
