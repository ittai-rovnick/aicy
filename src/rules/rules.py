"""Business logic rule implementations"""
from datetime import datetime
from typing import Optional

from src.core.models import Customer, Order, Action, RuleResult
from src.rules.base import Rule
from config.config import (
    EVALUATION_DATE,
    APPROVE_MAX_AMOUNT,
    ESCALATE_MIN_AMOUNT,
    APPROVE_MAX_AGE_DAYS,
    ESCALATE_MIN_AGE_DAYS,
)


class MissingDataRule(Rule):
    """Reject when customer/order cannot be found or identified for a refund.

    Four cases:
    1. Explicit order ID provided but not found → REJECT
    2. Explicit customer ID or email provided but not found → REJECT
    3. Customer found but no order to refund against → REJECT
    4. Refund request with no customer/order AND no way to identify either → REJECT
    """

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        customer = context.get("customer")
        order = context.get("order")
        extracted_order_id = context.get("extracted_order_id")
        extracted_customer_id = context.get("extracted_customer_id")
        extracted_email = context.get("extracted_email")
        request_type = context.get("request_type", "").lower()

        # CASE 1: Explicit order ID provided but not found
        if extracted_order_id and not order:
            return RuleResult(
                rule="MissingDataRule",
                action=Action.REJECT,
                reason=f"No matching order found for order ID: {extracted_order_id}",
            )

        # CASE 2: Explicit customer identifier provided but not found
        if (extracted_customer_id or extracted_email) and not customer:
            return RuleResult(
                rule="MissingDataRule",
                action=Action.REJECT,
                reason="No matching customer or order found in system",
            )

        # CASE 3: Customer found but no order to refund against
        if (extracted_customer_id or extracted_email) and not order:
            return RuleResult(
                rule="MissingDataRule",
                action=Action.REJECT,
                reason="No matching order found for customer",
            )

        # CASE 4: Refund request with no identifiable customer or order
        if request_type == "refund" and not customer and not order:
            has_identifier = extracted_order_id or extracted_customer_id or extracted_email
            if not has_identifier:
                return RuleResult(
                    rule="MissingDataRule",
                    action=Action.REJECT,
                    reason="No matching customer or order found - cannot process refund without customer/order identification",
                )

        return None


class IncompleteRequestRule(Rule):
    """Escalate requests missing information required to decide a refund."""

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        order = context.get("order")
        extracted_amount = context.get("extracted_amount")

        if not order:
            return RuleResult(
                rule="IncompleteRequestRule",
                action=Action.ESCALATE,
                reason="Ambiguous request: no order ID, customer ID, or email provided",
            )

        if extracted_amount is None:
            return RuleResult(
                rule="IncompleteRequestRule",
                action=Action.ESCALATE,
                reason="Incomplete request: refund amount not specified",
            )

        return None


class OrderStatusRule(Rule):
    """Reject non-refundable order statuses (refunded, cancelled, not_shipped)."""

    NON_REFUNDABLE_STATUSES = {"refunded", "cancelled", "not_shipped"}

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        order: Optional[Order] = context.get("order")

        if not order:
            return None

        status = order.status.lower()

        if status in self.NON_REFUNDABLE_STATUSES:
            if status == "refunded":
                reason = f"Order {order.order_id} has already been refunded"
            elif status == "cancelled":
                reason = f"Order {order.order_id} was cancelled - no refund applicable"
            else:  # not_shipped
                reason = f"Order {order.order_id} was never shipped - no refund applicable"

            return RuleResult(
                rule="OrderStatusRule",
                action=Action.REJECT,
                reason=reason,
            )

        return None


class RefundAmountVsOrderRule(Rule):
    """Escalate if refund amount exceeds order amount or is invalid."""

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        order: Optional[Order] = context.get("order")
        extracted_amount: Optional[float] = context.get("extracted_amount")

        if not order or extracted_amount is None:
            return None

        if extracted_amount < 0:
            return RuleResult(
                rule="RefundAmountVsOrderRule",
                action=Action.ESCALATE,
                reason=f"Invalid refund amount: ${extracted_amount} is negative",
            )

        if extracted_amount > order.amount:
            return RuleResult(
                rule="RefundAmountVsOrderRule",
                action=Action.ESCALATE,
                reason=f"Refund amount (${extracted_amount}) exceeds order total (${order.amount})",
            )

        return None


class CustomerStatusRule(Rule):
    """Escalate for problematic customer statuses (banned, inactive)."""

    NON_REFUNDABLE_STATUSES = {"banned", "inactive"}

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        customer: Optional[Customer] = context.get("customer")

        if not customer:
            return None

        status = customer.status.lower()

        if status in self.NON_REFUNDABLE_STATUSES:
            return RuleResult(
                rule="CustomerStatusRule",
                action=Action.ESCALATE,
                reason=f"Customer {customer.id} has status '{status}' - requires human review",
            )

        return None


class HighValueOrOldOrderRule(Rule):
    """Escalate if refund > threshold or order > age threshold."""

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        order: Optional[Order] = context.get("order")
        extracted_amount: Optional[float] = context.get("extracted_amount")

        if not order:
            return None

        reasons = []

        if extracted_amount is not None and extracted_amount >= ESCALATE_MIN_AMOUNT:
            reasons.append(f"Refund ${extracted_amount} exceeds threshold ${ESCALATE_MIN_AMOUNT}")

        try:
            order_date = datetime.strptime(order.date, "%Y-%m-%d")
            days_old = (EVALUATION_DATE - order_date).days

            if days_old > ESCALATE_MIN_AGE_DAYS:
                reasons.append(f"Order {days_old} days old (> {ESCALATE_MIN_AGE_DAYS})")
        except ValueError as e:
            return RuleResult(
                rule="HighValueOrOldOrderRule",
                action=Action.ESCALATE,
                reason=f"Malformed order date '{order.date}': {e}",
            )

        if reasons:
            return RuleResult(
                rule="HighValueOrOldOrderRule",
                action=Action.ESCALATE,
                reason=" | ".join(reasons),
            )

        return None


class StandardRefundRule(Rule):
    """Approve if refund < threshold AND order <= age threshold."""

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        order: Optional[Order] = context.get("order")
        extracted_amount: Optional[float] = context.get("extracted_amount")

        if not order or extracted_amount is None:
            return None

        try:
            order_date = datetime.strptime(order.date, "%Y-%m-%d")
            days_old = (EVALUATION_DATE - order_date).days
        except ValueError as e:
            return RuleResult(
                rule="StandardRefundRule",
                action=Action.ESCALATE,
                reason=f"Malformed order date '{order.date}': {e}",
            )

        if extracted_amount < APPROVE_MAX_AMOUNT and days_old <= APPROVE_MAX_AGE_DAYS:
            return RuleResult(
                rule="StandardRefundRule",
                action=Action.APPROVE,
                reason=f"Standard refund approved. Amount: ${extracted_amount} (< ${APPROVE_MAX_AMOUNT}) and age: {days_old} days (<= {APPROVE_MAX_AGE_DAYS}).",
            )

        return None


class DefaultEscalationRule(Rule):
    """Catch-all: escalate any request that reached here."""

    def evaluate(self, context: dict) -> Optional[RuleResult]:
        return RuleResult(
            rule="DefaultEscalationRule",
            action=Action.ESCALATE,
            reason="Valid request, no rule matched (gray area - requires human review)",
        )
