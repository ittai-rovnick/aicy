"""Main agent orchestrator"""
from typing import Optional

import tiktoken

from src.database.interface import DatabaseInterface
from src.llm.client import LLMClientInterface
from src.rules.engine import RuleEngine
from src.observability.logger import log_agent_decision
from src.core.models import AgentDecision, Customer, ExtractedRequestInfo, Order
from config.config import MAX_TOKEN_COUNT, CUSTOMER_LOOKUP_ORDER, OPENAI_MODEL
from src.observability.tracing import get_tracer

_tokenizer = tiktoken.encoding_for_model(OPENAI_MODEL)


class CustomerRequestAgent:
    """Main agent that orchestrates the request processing"""

    def __init__(self, llm_client: LLMClientInterface, db: DatabaseInterface):
        self.llm = llm_client
        self.db = db
        self.rule_engine = RuleEngine()
        self.tracer = get_tracer()

    def process_request(self, request_id: str, raw_text: str) -> AgentDecision:
        with self.tracer.trace(
            "process_customer_request",
            input_data={"request_id": request_id, "text_length": len(raw_text)},
            metadata={"request_id": request_id},
        ):
            if decision := self._check_word_limit(request_id, raw_text):
                return decision

            try:
                extracted = self.llm.extract_info(raw_text)
            except Exception as e:
                return self._escalate(request_id, f"LLM extraction failed: {e}")

            context = self._build_context(extracted)
            action, reasoning = self.rule_engine.run(context)
            log_agent_decision(request_id, action, reasoning)
            return AgentDecision(action=action, reasoning_trace=reasoning)

    def _check_word_limit(self, request_id: str, raw_text: str) -> Optional[AgentDecision]:
        token_count = len(_tokenizer.encode(raw_text))
        if token_count > MAX_TOKEN_COUNT:
            return self._escalate(
                request_id,
                f"Safety violation: {token_count} tokens exceeds {MAX_TOKEN_COUNT} token limit",
            )
        return None

    def _build_context(self, extracted: ExtractedRequestInfo) -> dict:
        customer = self._lookup_customer(extracted)
        return {
            "customer": customer,
            "order": self._lookup_order(extracted, customer),
            "extracted_amount": extracted.amount,
            "extracted_order_id": extracted.order_id,
        }

    def _lookup_customer(self, extracted: ExtractedRequestInfo) -> Optional[Customer]:
        for lookup_param in CUSTOMER_LOOKUP_ORDER:
            if lookup_param == "customer_id" and extracted.customer_id:
                customer = self.db.get_customer(customer_id=extracted.customer_id)
                if customer:
                    return customer
            elif lookup_param == "email" and extracted.customer_email:
                customer = self.db.get_customer(email=extracted.customer_email)
                if customer:
                    return customer
        return None

    def _lookup_order(self, extracted: ExtractedRequestInfo, customer: Optional[Customer]) -> Optional[Order]:
        if extracted.order_id:
            return self.db.get_order(extracted.order_id)
        if customer:
            orders = self.db.get_customer_orders(customer.id)
            if orders:
                return orders[-1]
        return None

    def _escalate(self, request_id: str, reason: str) -> AgentDecision:
        decision = AgentDecision(action="ESCALATE", reasoning_trace=reason)
        log_agent_decision(request_id, decision.action, decision.reasoning_trace)
        return decision
