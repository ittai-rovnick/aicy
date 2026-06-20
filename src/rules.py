"""Business logic rules engine"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.models import Customer, Order
from config.config import EVALUATION_DATE


class Rule(ABC):
    """Abstract base rule"""

    @abstractmethod
    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Evaluate rule and return (action, reasoning) or (None, None) if rule doesn't apply
        """
        pass


class MissingDataRule(Rule):
    """Reject if customer or order not found"""

    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        customer = context.get("customer")
        order = context.get("order")
        extracted_order_id = context.get("extracted_order_id")

        if extracted_order_id and not order:
            return (
                "REJECT",
                f"No matching order found for order ID: {extracted_order_id}",
            )

        if not customer:
            return "REJECT", "No matching customer found in system"

        return None, None


class HighValueOrOldOrderRule(Rule):
    """Escalate if amount > $500 OR order > 90 days old"""

    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        order: Optional[Order] = context.get("order")
        extracted_amount: Optional[float] = context.get("extracted_amount")

        if not order:
            return None, None

        reasons = []

        if extracted_amount and extracted_amount > 500:
            reasons.append(f"High value amount: ${extracted_amount}")

        order_date = datetime.strptime(order.date, "%Y-%m-%d")
        days_old = (EVALUATION_DATE - order_date).days

        if days_old > 90:
            reasons.append(f"Order too old: {days_old} days (> 90 days)")

        if reasons:
            return "ESCALATE", " | ".join(reasons)

        return None, None


class StandardRefundRule(Rule):
    """Approve if amount < $50 AND order <= 30 days old"""

    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        order: Optional[Order] = context.get("order")
        extracted_amount: Optional[float] = context.get("extracted_amount")

        if not order:
            return None, None

        order_date = datetime.strptime(order.date, "%Y-%m-%d")
        days_old = (EVALUATION_DATE - order_date).days

        if extracted_amount and extracted_amount < 50 and days_old <= 30:
            return (
                "APPROVE",
                f"Standard refund conditions met. Amount: ${extracted_amount} (<$50) and age: {days_old} days (<=30 days).",
            )

        return None, None


class DefaultEscalationRule(Rule):
    """Escalate everything else - gray areas need human review"""

    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        return "ESCALATE", "Falls into gray area, requires human review"


class RuleEngine:
    """Orchestrates rule evaluation"""

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
        Returns (action, reasoning)
        """
        for rule in self.rules:
            action, reasoning = rule.evaluate(context)
            if action is not None:
                return action, reasoning

        return "ESCALATE", "No rule matched (should not happen)"
