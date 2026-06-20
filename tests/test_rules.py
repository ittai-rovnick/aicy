"""Unit tests for the Rule Engine - validates business logic without LLM calls"""
import pytest
from datetime import datetime
from src.core.models import Customer, Order, Action, RuleResult
from src.rules.rules import (
    MissingDataRule,
    IncompleteRequestRule,
    OrderStatusRule,
    RefundAmountVsOrderRule,
    CustomerStatusRule,
    HighValueOrOldOrderRule,
    StandardRefundRule,
    DefaultEscalationRule,
)
from src.engine.decision_engine import decide
from src.rules.engine import RuleEngine
from config.config import (
    EVALUATION_DATE,
    APPROVE_MAX_AMOUNT,
    ESCALATE_MIN_AMOUNT,
    APPROVE_MAX_AGE_DAYS,
    ESCALATE_MIN_AGE_DAYS,
)


# Test fixtures
@pytest.fixture
def customer():
    """Mock customer record"""
    return Customer(
        id="C1001",
        name="Test Customer",
        email="test@example.com",
        tier="standard",
        status="active",
    )


@pytest.fixture
def recent_order():
    """Order placed 15 days ago - within 30-day window"""
    return Order(
        order_id="ORD-55",
        customer_id="C1001",
        amount=45.00,
        date="2026-06-01",  # 15 days before EVALUATION_DATE (2026-06-16)
        status="delivered",
    )


@pytest.fixture
def medium_age_order():
    """Order placed 60 days ago - outside 30-day window but within 90-day window"""
    return Order(
        order_id="ORD-75",
        customer_id="C1001",
        amount=75.00,
        date="2026-04-17",  # 60 days before EVALUATION_DATE
        status="delivered",
    )


@pytest.fixture
def old_order():
    """Order placed 121 days ago - exceeds 90-day threshold"""
    return Order(
        order_id="ORD-100",
        customer_id="C1001",
        amount=250.00,
        date="2026-02-15",  # 121 days before EVALUATION_DATE
        status="delivered",
    )


class TestMissingDataRule:
    """Test MissingDataRule - rejects requests with missing customer/order when identifier provided"""

    def test_missing_customer_with_id_returns_reject(self):
        """Customer ID provided but not found should REJECT"""
        rule = MissingDataRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_customer_id": "C-MISSING",
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "No matching customer or order found in system" in result.reason

    def test_missing_order_by_id_returns_reject(self):
        """Order ID provided but not found should REJECT"""
        rule = MissingDataRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_order_id": "ORD-MISSING",
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "No matching order found for order ID: ORD-MISSING" in result.reason

    def test_customer_found_but_no_order_returns_reject(self, customer):
        """Customer found via identifier but no order exists should REJECT"""
        rule = MissingDataRule()
        context = {
            "customer": customer,
            "order": None,
            "extracted_customer_id": customer.id,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "No matching order found for customer" in result.reason

    def test_customer_and_order_present_does_not_match(self, customer, recent_order):
        """Both customer and order found should not match"""
        rule = MissingDataRule()
        context = {"customer": customer, "order": recent_order}
        result = rule.evaluate(context)
        assert result is None

    def test_refund_request_no_identifier_returns_reject(self):
        """Refund request with no customer_id, email, or order_id should REJECT"""
        rule = MissingDataRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_customer_id": None,
            "extracted_email": None,
            "extracted_order_id": None,
            "extracted_amount": 60.0,
            "request_type": "refund",
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "No matching customer or order found" in result.reason

    def test_non_refund_request_no_identifier_passes(self):
        """Non-refund request with no identifier should pass (not impossible)"""
        rule = MissingDataRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_customer_id": None,
            "extracted_email": None,
            "extracted_order_id": None,
            "extracted_amount": None,
            "request_type": "account_inquiry",
        }
        result = rule.evaluate(context)
        assert result is None

    def test_refund_request_case_insensitive(self):
        """request_type comparison should be case-insensitive"""
        rule = MissingDataRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_customer_id": None,
            "extracted_email": None,
            "extracted_order_id": None,
            "extracted_amount": 60.0,
            "request_type": "REFUND",  # uppercase
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT


class TestIncompleteRequestRule:
    """Test IncompleteRequestRule - escalates ambiguous/incomplete requests"""

    def test_no_order_escalates(self):
        """No order present should ESCALATE"""
        rule = IncompleteRequestRule()
        context = {
            "customer": None,
            "order": None,
            "extracted_order_id": None,
            "extracted_customer_id": None,
            "extracted_email": None,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "Ambiguous request" in result.reason

    def test_no_amount_escalates(self, customer, recent_order):
        """Missing refund amount should ESCALATE"""
        rule = IncompleteRequestRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": None,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "refund amount not specified" in result.reason

    def test_zero_amount_does_not_escalate(self, customer, recent_order):
        """Zero amount is specified (not missing), should not escalate"""
        rule = IncompleteRequestRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 0.0,
        }
        result = rule.evaluate(context)
        assert result is None


class TestOrderStatusRule:
    """Test OrderStatusRule - rejects non-refundable order statuses"""

    def test_refunded_order_rejects(self, customer):
        """Order already refunded should REJECT"""
        order = Order(
            order_id="ORD-REF",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="refunded",
        )
        rule = OrderStatusRule()
        context = {"customer": customer, "order": order, "extracted_amount": 50.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "already been refunded" in result.reason

    def test_cancelled_order_rejects(self, customer):
        """Cancelled order should REJECT"""
        order = Order(
            order_id="ORD-CAN",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="cancelled",
        )
        rule = OrderStatusRule()
        context = {"customer": customer, "order": order, "extracted_amount": 50.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "was cancelled" in result.reason

    def test_not_shipped_order_rejects(self, customer):
        """Never shipped order should REJECT"""
        order = Order(
            order_id="ORD-NS",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="not_shipped",
        )
        rule = OrderStatusRule()
        context = {"customer": customer, "order": order, "extracted_amount": 50.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.REJECT
        assert "never shipped" in result.reason

    def test_delivered_order_passes(self, customer, recent_order):
        """Delivered order should not trigger rule"""
        rule = OrderStatusRule()
        context = {"customer": customer, "order": recent_order, "extracted_amount": 50.00}
        result = rule.evaluate(context)
        assert result is None


class TestRefundAmountVsOrderRule:
    """Test RefundAmountVsOrderRule - validates refund amount vs order amount"""

    def test_refund_exceeds_order_escalates(self, customer):
        """Refund amount > order amount should ESCALATE"""
        order = Order(
            order_id="ORD-OVER",
            customer_id="C1001",
            amount=50.00,
            date="2026-06-10",
            status="delivered",
        )
        rule = RefundAmountVsOrderRule()
        context = {"customer": customer, "order": order, "extracted_amount": 75.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "exceeds order total" in result.reason

    def test_refund_equals_order_passes(self, customer):
        """Refund amount = order amount should not trigger rule"""
        order = Order(
            order_id="ORD-EQ",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="delivered",
        )
        rule = RefundAmountVsOrderRule()
        context = {"customer": customer, "order": order, "extracted_amount": 100.00}
        result = rule.evaluate(context)
        assert result is None

    def test_negative_refund_escalates(self, customer, recent_order):
        """Negative refund amount should ESCALATE"""
        rule = RefundAmountVsOrderRule()
        context = {"customer": customer, "order": recent_order, "extracted_amount": -10.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "negative" in result.reason


class TestCustomerStatusRule:
    """Test CustomerStatusRule - validates customer status"""

    def test_banned_customer_escalates(self):
        """Banned customer should ESCALATE"""
        customer = Customer(
            id="C-BAN",
            name="Banned Customer",
            email="banned@example.com",
            tier="standard",
            status="banned",
        )
        order = Order(
            order_id="ORD-1",
            customer_id="C-BAN",
            amount=50.00,
            date="2026-06-10",
            status="delivered",
        )
        rule = CustomerStatusRule()
        context = {"customer": customer, "order": order, "extracted_amount": 30.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "banned" in result.reason

    def test_inactive_customer_escalates(self):
        """Inactive customer should ESCALATE"""
        customer = Customer(
            id="C-INACT",
            name="Inactive Customer",
            email="inactive@example.com",
            tier="standard",
            status="inactive",
        )
        order = Order(
            order_id="ORD-1",
            customer_id="C-INACT",
            amount=50.00,
            date="2026-06-10",
            status="delivered",
        )
        rule = CustomerStatusRule()
        context = {"customer": customer, "order": order, "extracted_amount": 30.00}
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "inactive" in result.reason

    def test_active_customer_passes(self, customer, recent_order):
        """Active customer should not trigger rule"""
        rule = CustomerStatusRule()
        context = {"customer": customer, "order": recent_order, "extracted_amount": 30.00}
        result = rule.evaluate(context)
        assert result is None


class TestHighValueOrOldOrderRule:
    """Test HighValueOrOldOrderRule - escalates high-value or old refund requests"""

    def test_high_value_refund_escalates(self, customer, recent_order):
        """Refund amount >= threshold should ESCALATE"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": ESCALATE_MIN_AMOUNT,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert f"${ESCALATE_MIN_AMOUNT}" in result.reason

    def test_old_order_escalates(self, customer, old_order):
        """Order age > threshold should ESCALATE"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": old_order,
            "extracted_amount": 100.00,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE
        assert "days old" in result.reason

    def test_standard_amount_and_recent_order_does_not_match(
        self, customer, recent_order
    ):
        """Low amount and recent order should not match this rule"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 45.00,
        }
        result = rule.evaluate(context)
        assert result is None

    def test_boundary_just_under_escalate_amount(self, customer, recent_order):
        """Amount just under threshold should not escalate"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": ESCALATE_MIN_AMOUNT - 0.01,
        }
        result = rule.evaluate(context)
        assert result is None

    def test_boundary_exactly_at_escalate_amount(self, customer, recent_order):
        """Amount exactly at threshold should escalate"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": ESCALATE_MIN_AMOUNT,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.ESCALATE


class TestStandardRefundRule:
    """Test StandardRefundRule - approves low-value, recent refunds"""

    def test_standard_refund_approves(self, customer, recent_order):
        """Low amount and recent order should APPROVE"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 45.00,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.APPROVE
        assert "Standard refund approved" in result.reason

    def test_boundary_just_under_approve_amount(self, customer, recent_order):
        """Amount just under threshold should approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": APPROVE_MAX_AMOUNT - 0.01,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.APPROVE

    def test_boundary_exactly_at_approve_amount(self, customer, recent_order):
        """Amount exactly at threshold should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": APPROVE_MAX_AMOUNT,
        }
        result = rule.evaluate(context)
        assert result is None

    def test_old_order_does_not_approve(self, customer, medium_age_order):
        """Order > max age should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": medium_age_order,
            "extracted_amount": 30.00,
        }
        result = rule.evaluate(context)
        assert result is None

    def test_boundary_exactly_at_max_age(self, customer):
        """Order exactly at max age should approve"""
        order = Order(
            order_id="ORD-AGE",
            customer_id="C1001",
            amount=100.00,
            date="2026-05-17",  # Exactly APPROVE_MAX_AGE_DAYS before EVALUATION_DATE
            status="delivered",
        )
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 30.00,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.APPROVE

    def test_zero_amount_approves(self, customer, recent_order):
        """Zero amount should be treated as valid and approve if within age"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 0.0,
        }
        result = rule.evaluate(context)
        assert result is not None
        assert result.action == Action.APPROVE


class TestDecisionEngineIntegration:
    """Integration tests of the full decision engine"""

    def test_reject_beats_escalate(self, customer):
        """REJECT precedence: order status takes priority over amount"""
        order = Order(
            order_id="ORD-REF",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="refunded",  # REJECT
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": ESCALATE_MIN_AMOUNT,  # Also ESCALATE
        }
        decision = decide(context)
        assert decision.action == Action.REJECT
        # Trace should show both matched, but REJECT is returned
        assert any(r.action == Action.REJECT for r in decision.trace)

    def test_escalate_beats_approve(self, customer, old_order):
        """ESCALATE precedence: old order blocks approval"""
        context = {
            "customer": customer,
            "order": old_order,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        assert decision.action == Action.ESCALATE

    def test_complete_valid_request_approves(self, customer, recent_order):
        """All conditions met should APPROVE"""
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_customer_id": customer.id,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        assert decision.action == Action.APPROVE
        assert decision.primary_reason is not None
        assert len(decision.trace) > 0

    def test_trace_includes_all_evaluated_rules(self, customer, recent_order):
        """Full trace should show every rule that ran"""
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        # At minimum, should include the matching rule
        assert len(decision.trace) > 0
        # Last rule in trace should be the one that matched
        assert decision.trace[-1].action == decision.action

    def test_malformed_date_escalates(self, customer):
        """Bad date should escalate, not crash"""
        order = Order(
            order_id="ORD-BAD",
            customer_id="C1001",
            amount=100.00,
            date="invalid-date",
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 45.00,
        }
        decision = decide(context)
        # Should escalate due to malformed date, not crash
        assert decision.action == Action.ESCALATE
        assert "Malformed" in decision.primary_reason or "invalid" in decision.primary_reason.lower()

    def test_rule_order_does_not_matter(self, customer):
        """Swapping rule order produces identical decision — order is not load-bearing."""
        order = Order(
            order_id="ORD-REF",
            customer_id="C1001",
            amount=100.00,
            date="2026-06-10",
            status="refunded",  # OrderStatusRule → REJECT
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": ESCALATE_MIN_AMOUNT,  # HighValueOrOldOrderRule → ESCALATE
        }

        engine = RuleEngine()
        decision1 = engine.run(context)

        # Swap OrderStatusRule (index 1) and HighValueOrOldOrderRule (index 5)
        engine.rules[1], engine.rules[5] = engine.rules[5], engine.rules[1]
        decision2 = engine.run(context)

        assert decision1.action == decision2.action
        assert decision1.primary_reason == decision2.primary_reason

    def test_refund_exceeds_order_amount_escalates(self, customer):
        """Refund > order amount should escalate"""
        order = Order(
            order_id="ORD-OVER",
            customer_id="C1001",
            amount=50.00,
            date="2026-06-10",
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 75.00,
        }
        decision = decide(context)
        assert decision.action == Action.ESCALATE
        assert "exceeds order total" in decision.primary_reason

    def test_banned_customer_escalates(self):
        """Banned customer should escalate even for valid order"""
        customer = Customer(
            id="C-BAN",
            name="Banned",
            email="banned@example.com",
            tier="standard",
            status="banned",
        )
        order = Order(
            order_id="ORD-1",
            customer_id="C-BAN",
            amount=100.00,
            date="2026-06-10",
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        assert decision.action == Action.ESCALATE
        assert "banned" in decision.primary_reason

    def test_refund_request_no_identification_rejects(self):
        """Refund request with no customer/order identification should REJECT"""
        context = {
            "customer": None,
            "order": None,
            "extracted_customer_id": None,
            "extracted_email": None,
            "extracted_order_id": None,
            "extracted_amount": 60.0,
            "request_type": "refund",
        }
        decision = decide(context)
        assert decision.action == Action.REJECT
        assert "No matching customer or order found" in decision.primary_reason
        assert decision.trace[0].rule == "MissingDataRule"


class TestThresholdConfiguration:
    """Test that thresholds from config are being used correctly"""

    def test_approve_max_amount_is_respected(self, customer):
        """APPROVE_MAX_AMOUNT from config should be the threshold"""
        # Order amount must exceed the refund amount to avoid triggering RefundAmountVsOrderRule
        order = Order(
            order_id="ORD-THRESH",
            customer_id="C1001",
            amount=APPROVE_MAX_AMOUNT * 2,
            date="2026-06-01",
            status="delivered",
        )

        # Just under threshold should approve
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": APPROVE_MAX_AMOUNT - 0.01,
        }
        decision = decide(context)
        assert decision.action == Action.APPROVE

        # At threshold should not approve
        context["extracted_amount"] = APPROVE_MAX_AMOUNT
        decision = decide(context)
        assert decision.action != Action.APPROVE

    def test_escalate_min_amount_is_respected(self, customer, recent_order):
        """ESCALATE_MIN_AMOUNT from config should trigger escalation"""
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": ESCALATE_MIN_AMOUNT,
        }
        decision = decide(context)
        assert decision.action == Action.ESCALATE

    def test_approve_max_age_is_respected(self, customer):
        """APPROVE_MAX_AGE_DAYS from config should be the threshold"""
        # Order at max age should approve
        order = Order(
            order_id="ORD-AT-MAX",
            customer_id="C1001",
            amount=100.00,
            date="2026-05-17",  # Exactly APPROVE_MAX_AGE_DAYS before EVALUATION_DATE
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        assert decision.action == Action.APPROVE

        # Order past max age should not approve (escalate on high value or pass through)
        order.date = "2026-05-16"  # 31 days old
        decision = decide(context)
        assert decision.action != Action.APPROVE

    def test_escalate_min_age_is_respected(self, customer):
        """ESCALATE_MIN_AGE_DAYS from config should trigger escalation"""
        order = Order(
            order_id="ORD-OLD",
            customer_id="C1001",
            amount=100.00,
            date="2026-03-17",  # More than ESCALATE_MIN_AGE_DAYS old
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 30.00,
        }
        decision = decide(context)
        assert decision.action == Action.ESCALATE
