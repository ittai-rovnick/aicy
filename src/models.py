"""Pydantic models for data validation"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


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
    """Final decision output from agent"""
    action: Literal["APPROVE", "REJECT", "ESCALATE"]
    reasoning_trace: str
