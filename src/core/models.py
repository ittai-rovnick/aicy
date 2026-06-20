"""Pydantic models for data validation"""
from enum import IntEnum
from pydantic import BaseModel, Field
from typing import Optional, Literal


class Action(IntEnum):
    """Decision action precedence. Higher value = more decisive.
    REJECT (3) > ESCALATE (2) > APPROVE (1). Use max() to pick the winner."""
    APPROVE = 1
    ESCALATE = 2
    REJECT = 3


class RuleResult(BaseModel):
    """A single rule's evaluation result."""
    rule: str           # Rule class name
    action: Action      # APPROVE, ESCALATE, or REJECT
    reason: str         # Why this rule fired


class Decision(BaseModel):
    """Final decision with full audit trace."""
    action: Action
    primary_reason: str
    trace: list[RuleResult]


class ExtractedRequestInfo(BaseModel):
    """LLM extraction output - strictly enforced schema"""
    customer_id: Optional[str] = Field(None, description="Customer ID if mentioned")
    customer_email: Optional[str] = Field(None, description="Customer email if mentioned")
    order_id: Optional[str] = Field(None, description="Order ID if mentioned")
    request_type: Literal["refund", "account_inquiry", "complaint", "unknown"] = Field(
        default="unknown", description="Type of customer request"
    )
    amount: Optional[float] = Field(None, description="Monetary amount if mentioned")


class Customer(BaseModel):
    """Customer record from database"""
    id: str
    name: str
    email: str
    tier: str
    status: str


class Order(BaseModel):
    """Order record from database"""
    order_id: str
    customer_id: str
    amount: float
    date: str
    status: str


class AgentDecision(BaseModel):
    """Final decision output from agent (JSON-serializable version)"""
    action: str          # "APPROVE", "REJECT", "ESCALATE"
    primary_reason: str
    trace: list[dict]    # [{rule, action, reason}, ...]
