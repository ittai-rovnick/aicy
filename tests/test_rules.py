"""Unit tests for the Rule Engine - validates business logic without LLM calls"""
import pytest
from datetime import datetime
from src.core.models import Customer, Order
from src.rules.rules import (
    MissingDataRule,
    HighValueOrOldOrderRule,
    StandardRefundRule,
    DefaultEscalationRule,
)
from config.config import EVALUATION_DATE


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


@pytest.fixture
def high_value_order():
    """Order with high value ($600) - exceeds $500 threshold"""
    return Order(
        order_id="ORD-99",
        customer_id="C1001",
        amount=600.00,
        date="2026-06-10",  # 6 days before EVALUATION_DATE
        status="delivered",
    )


class TestMissingDataRule:
    """Test MissingDataRule - rejects requests with missing customer or order"""

    def test_missing_customer_returns_reject(self):
        """No customer found should REJECT"""
        rule = MissingDataRule()
        context = {"customer": None, "order": None}
        action, reasoning = rule.evaluate(context)
        assert action == "REJECT"
        assert "No matching customer found in system" in reasoning

    def test_missing_order_by_id_returns_reject(self, customer):
        """Order not found by ID should REJECT"""
        rule = MissingDataRule()
        context = {
            "customer": customer,
            "order": None,
            "extracted_order_id": "ORD-MISSING",
        }
        action, reasoning = rule.evaluate(context)
        assert action == "REJECT"
        assert "No matching order found for order ID: ORD-MISSING" in reasoning

    def test_customer_and_order_present_does_not_match(self, customer, recent_order):
        """Rule should not match if both customer and order are found"""
        rule = MissingDataRule()
        context = {"customer": customer, "order": recent_order}
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_no_order_id_extracted_does_not_reject(self, customer):
        """If no order_id was extracted and no order found, shouldn't match MissingDataRule alone"""
        rule = MissingDataRule()
        context = {
            "customer": customer,
            "order": None,
            "extracted_order_id": None,
        }
        action, reasoning = rule.evaluate(context)
        # MissingDataRule only rejects if extracted_order_id exists but order not found
        assert action is None
        assert reasoning is None


class TestHighValueOrOldOrderRule:
    """Test HighValueOrOldOrderRule - escalates high-value or old orders"""

    def test_high_value_amount_escalates(self, customer, high_value_order):
        """Amount > $500 should ESCALATE"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": high_value_order,
            "extracted_amount": 600.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "High value amount: $600" in reasoning

    def test_old_order_escalates(self, customer, old_order):
        """Order age > 90 days should ESCALATE"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": old_order,
            "extracted_amount": 100.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "Order too old: 121 days (> 90 days)" in reasoning

    def test_high_value_and_old_escalates_both_reasons(self, customer):
        """Both conditions met should mention both reasons"""
        old_high_value_order = Order(
            order_id="ORD-999",
            customer_id="C1001",
            amount=600.00,
            date="2025-12-01",  # 198 days old
            status="delivered",
        )
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": old_high_value_order,
            "extracted_amount": 600.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "High value amount: $600" in reasoning
        assert "Order too old" in reasoning

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
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_no_order_does_not_match(self, customer):
        """No order present should not trigger rule"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": None,
            "extracted_amount": 600.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_boundary_exactly_500_dollars_escalates(self, customer, recent_order):
        """Amount exactly $500 is not > $500, should not escalate on amount alone"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 500.00,
        }
        action, reasoning = rule.evaluate(context)
        # $500 is NOT > $500, so should not escalate on amount
        assert action is None
        assert reasoning is None

    def test_boundary_exactly_500_01_escalates(self, customer, recent_order):
        """Amount $500.01 is > $500, should escalate"""
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 500.01,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "High value amount: $500.01" in reasoning

    def test_boundary_exactly_90_days_old_does_not_escalate(self, customer):
        """Order exactly 90 days old is not > 90, should not escalate on age alone"""
        order_90_days = Order(
            order_id="ORD-90",
            customer_id="C1001",
            amount=100.00,
            date="2026-03-18",  # Exactly 90 days before 2026-06-16
            status="delivered",
        )
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": order_90_days,
            "extracted_amount": 100.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_boundary_exactly_91_days_old_escalates(self, customer):
        """Order 91 days old is > 90, should escalate"""
        order_91_days = Order(
            order_id="ORD-91",
            customer_id="C1001",
            amount=100.00,
            date="2026-03-17",  # 91 days before 2026-06-16
            status="delivered",
        )
        rule = HighValueOrOldOrderRule()
        context = {
            "customer": customer,
            "order": order_91_days,
            "extracted_amount": 100.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "Order too old: 91 days (> 90 days)" in reasoning


class TestStandardRefundRule:
    """Test StandardRefundRule - approves low-value, recent refunds"""

    def test_standard_refund_approves(self, customer, recent_order):
        """Low amount (<$50) and recent order (<=30 days) should APPROVE"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 45.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "APPROVE"
        assert "Standard refund conditions met" in reasoning
        assert "$45" in reasoning
        assert "15 days" in reasoning

    def test_high_amount_does_not_approve(self, customer, recent_order):
        """Amount >= $50 should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 50.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_old_order_does_not_approve(self, customer, medium_age_order):
        """Order > 30 days old should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": medium_age_order,
            "extracted_amount": 30.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_no_order_does_not_approve(self, customer):
        """No order present should not trigger approval"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": None,
            "extracted_amount": 30.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_boundary_exactly_49_99_approves(self, customer, recent_order):
        """Amount $49.99 is < $50, should approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 49.99,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "APPROVE"
        assert "Standard refund conditions met" in reasoning

    def test_boundary_exactly_50_does_not_approve(self, customer, recent_order):
        """Amount exactly $50 is not < $50, should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 50.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_boundary_exactly_30_days_approves(self, customer):
        """Order exactly 30 days old is <=30, should approve"""
        order_30_days = Order(
            order_id="ORD-30",
            customer_id="C1001",
            amount=100.00,
            date="2026-05-17",  # Exactly 30 days before 2026-06-16
            status="delivered",
        )
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": order_30_days,
            "extracted_amount": 30.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "APPROVE"
        assert "30 days" in reasoning

    def test_boundary_exactly_31_days_does_not_approve(self, customer):
        """Order 31 days old is > 30, should not approve"""
        order_31_days = Order(
            order_id="ORD-31",
            customer_id="C1001",
            amount=100.00,
            date="2026-05-16",  # 31 days before 2026-06-16
            status="delivered",
        )
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": order_31_days,
            "extracted_amount": 30.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None

    def test_no_extracted_amount_does_not_approve(self, customer, recent_order):
        """Missing extracted amount should not approve"""
        rule = StandardRefundRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": None,
        }
        action, reasoning = rule.evaluate(context)
        assert action is None
        assert reasoning is None


class TestDefaultEscalationRule:
    """Test DefaultEscalationRule - catch-all for ambiguous cases"""

    def test_always_escalates(self):
        """Default rule should always escalate (catch-all)"""
        rule = DefaultEscalationRule()
        context = {}
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "Falls into gray area" in reasoning

    def test_escalates_with_any_context(self, customer, recent_order):
        """Default rule should escalate even with complete context (as fallback)"""
        rule = DefaultEscalationRule()
        context = {
            "customer": customer,
            "order": recent_order,
            "extracted_amount": 100.00,
        }
        action, reasoning = rule.evaluate(context)
        assert action == "ESCALATE"
        assert "Falls into gray area" in reasoning


class TestRuleEvaluationOrder:
    """Integration tests showing rule evaluation order matters"""

    def test_missing_data_takes_precedence(self, recent_order):
        """Missing data should be caught before other rules"""
        # Scenario: no customer, but order exists
        context = {
            "customer": None,
            "order": recent_order,
            "extracted_order_id": "ORD-55",
            "extracted_amount": 45.00,
        }

        # If MissingDataRule runs first, it should REJECT
        missing_rule = MissingDataRule()
        action, reasoning = missing_rule.evaluate(context)
        assert action == "REJECT"

        # StandardRefundRule only checks order data (not customer), so it would match
        # This shows why MissingDataRule must run first in the engine to catch missing customer
        standard_rule = StandardRefundRule()
        action2, reasoning2 = standard_rule.evaluate(context)
        assert action2 == "APPROVE"  # StandardRefundRule matches because order meets criteria

    def test_high_value_takes_precedence_over_approval(self, customer):
        """High value should escalate even if other conditions met"""
        order = Order(
            order_id="ORD-TEST",
            customer_id="C1001",
            amount=600.00,
            date="2026-06-10",  # Recent
            status="delivered",
        )
        context = {
            "customer": customer,
            "order": order,
            "extracted_amount": 600.00,
        }

        # HighValueOrOldOrderRule should escalate
        high_value_rule = HighValueOrOldOrderRule()
        action, reasoning = high_value_rule.evaluate(context)
        assert action == "ESCALATE"

        # StandardRefundRule wouldn't match (amount too high)
        standard_rule = StandardRefundRule()
        action2, reasoning2 = standard_rule.evaluate(context)
        assert action2 is None
