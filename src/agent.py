"""Main agent orchestrator"""
from src.database.interface import DatabaseInterface
from src.llm.client import LLMClientInterface
from src.rules.engine import RuleEngine
from src.logging.logger import log_agent_decision
from src.models import AgentDecision
from config.config import MAX_WORD_COUNT, CUSTOMER_LOOKUP_ORDER
from src.tracing import get_tracer


class CustomerRequestAgent:
    """Main agent that orchestrates the request processing"""

    def __init__(self, llm_client: LLMClientInterface, db: DatabaseInterface):
        self.llm = llm_client
        self.db = db
        self.rule_engine = RuleEngine()
        self.tracer = get_tracer()

    def process_request(self, request_id: str, raw_text: str) -> AgentDecision:
        """
        Process a customer request and return a decision.

        Flow:
        1. Word count check (security gate)
        2. LLM extraction
        3. Database lookup
        4. Rule evaluation
        5. Logging
        6. Return decision
        """
        with self.tracer.trace(
            "process_customer_request",
            input_data={"request_id": request_id, "text_length": len(raw_text)},
            metadata={"request_id": request_id},
        ) as span:
            # SECURITY GATE 1: Word count check (prevents token flooding)
            word_count = len(raw_text.split())
            if word_count > MAX_WORD_COUNT:
                decision = AgentDecision(
                    action="ESCALATE",
                    reasoning_trace=f"Safety violation: {word_count} words exceeds {MAX_WORD_COUNT} word limit",
                )
                log_agent_decision(request_id, decision.action, decision.reasoning_trace)
                return decision

            # STEP 1: Extract data using LLM
            try:
                extracted = self.llm.extract_info(raw_text)
            except Exception as e:
                decision = AgentDecision(
                    action="ESCALATE",
                    reasoning_trace=f"LLM extraction failed: {str(e)}",
                )
                log_agent_decision(request_id, decision.action, decision.reasoning_trace)
                return decision

            # STEP 2: Fetch background data using repository pattern
            customer = None
            for lookup_param in CUSTOMER_LOOKUP_ORDER:
                if lookup_param == "customer_id" and extracted.customer_id:
                    customer = self.db.get_customer(customer_id=extracted.customer_id)
                    if customer:
                        break
                elif lookup_param == "email" and extracted.customer_email:
                    customer = self.db.get_customer(email=extracted.customer_email)
                    if customer:
                        break

            order = None
            if extracted.order_id:
                order = self.db.get_order(extracted.order_id)

            # STEP 3: Run business rules (deterministic Python logic)
            context = {
                "customer": customer,
                "order": order,
                "extracted_amount": extracted.amount,
                "extracted_order_id": extracted.order_id,
            }
            action, reasoning = self.rule_engine.run(context)

            # STEP 4: Log the decision
            log_agent_decision(request_id, action, reasoning)

            # STEP 5: Return structured output
            decision = AgentDecision(action=action, reasoning_trace=reasoning)
            return decision
