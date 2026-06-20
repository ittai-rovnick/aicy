"""Rule engine - orchestrates rule evaluation"""
from src.rules.rules import (
    MissingDataRule,
    HighValueOrOldOrderRule,
    StandardRefundRule,
    DefaultEscalationRule,
)


class RuleEngine:
    """Orchestrates rule evaluation - evaluates rules in order until one matches"""

    def __init__(self):
        self.rules = [
            MissingDataRule(),
            HighValueOrOldOrderRule(),
            StandardRefundRule(),
            DefaultEscalationRule(),
        ]

    def run(self, context: dict) -> tuple[str, str]:
        """
        Evaluate rules in order. First matching rule wins.

        Args:
            context: Dictionary with customer, order, extracted_amount, extracted_order_id

        Returns:
            Tuple of (action, reasoning)
        """
        for rule in self.rules:
            action, reasoning = rule.evaluate(context)
            if action is not None:
                return action, reasoning

        return "ESCALATE", "No rule matched (should not happen)"
