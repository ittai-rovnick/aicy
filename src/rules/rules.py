"""Business logic rule implementations"""
from datetime import datetime
from typing import Optional

from src.core.models import Customer, Order
from src.rules.base import Rule
from config.config import EVALUATION_DATE


class MissingDataRule(Rule):
    """Reject only when an explicit identifier was provided but not found.
    Anonymous requests (no identifier at all) fall through to DefaultEscalationRule."""

    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        customer = context.get("customer")
        order = context.get("order")
        extracted_order_id = context.get("extracted_order_id")
        extracted_customer_id = context.get("extracted_customer_id")
        extracted_email = context.get("extracted_email")

        # An explicit order ID was given but does not exist in the DB
        if extracted_order_id and not order:
            return (
                "REJECT",
                f"No matching order found for order ID: {extracted_order_id}",
            )

        # A customer identifier (ID or email) was given but does not exist in the DB
        if (extracted_customer_id or extracted_email) and not customer:
            return "REJECT", "No matching customer or order found in system"

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
