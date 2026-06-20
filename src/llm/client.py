"""LLM client implementations with Strategy pattern"""
from abc import ABC, abstractmethod
import os
import json

from openai import OpenAI
from src.core.models import ExtractedRequestInfo
from config.config import OPENAI_MODEL, LLM_TEMPERATURE
from src.observability.tracing import get_tracer


class LLMClientInterface(ABC):
    """Abstract LLM client interface"""

    @abstractmethod
    def extract_info(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract structured info from raw request text"""
        pass


class OpenAILLMClient(LLMClientInterface):
    """OpenAI client with Langfuse integration"""

    SYSTEM_PROMPT = """You are a customer request information extractor.
Extract the following fields from customer messages:
- customer_id: The customer ID (format: C####)
- customer_email: The customer's email address
- order_id: The order ID (format: ORD-###)
- request_type: One of: refund, account_inquiry, complaint, unknown
  * refund: Message asks for refund, return, money back, or reimbursement
  * account_inquiry: Message asks about account, login, password, balance, etc.
  * complaint: Message complains about product, service, or experience (broken, damaged, etc.)
  * unknown: None of the above
- amount: The monetary amount mentioned (numeric value only)

Be precise. Only extract information explicitly mentioned in the message."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = OPENAI_MODEL
        self.tracer = get_tracer()

    def extract_info(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract request info from text using OpenAI structured output"""
        with self.tracer.trace(
            "extract_request_info",
            input_data={"raw_text": raw_text[:500]},  # Truncate for logging
            metadata={"model": self.model, "temperature": LLM_TEMPERATURE},
        ) as span:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                temperature=LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                response_format=ExtractedRequestInfo,
            )

            result = response.choices[0].message.parsed

            # Fallback: if LLM returned "unknown" but text contains refund keywords,
            # reclassify as refund (robustness against LLM unreliability)
            if result.request_type == "unknown":
                lower_text = raw_text.lower()
                if any(kw in lower_text for kw in ('refund', 'return', 'money back', 'reimbursement')):
                    result.request_type = "refund"

            # Log generation details
            self.tracer.log_generation(
                name="extract_request_info",
                input_text=raw_text,
                output_text=result.model_dump_json(),
                model=self.model,
                metadata={
                    "tokens_used": response.usage.total_tokens if response.usage else None,
                },
            )

            return result


class MockLLMClient(LLMClientInterface):
    """Regex-based mock LLM client — no API key required, used for local demos."""

    def extract_info(self, raw_text: str) -> ExtractedRequestInfo:
        import re

        # Order ID: ORD-123
        order_match = re.search(r'\bORD-\d+\b', raw_text, re.IGNORECASE)
        order_id = order_match.group(0).upper() if order_match else None

        # Customer ID: C1001
        customer_match = re.search(r'\bC\d{4}\b', raw_text)
        customer_id = customer_match.group(0) if customer_match else None

        # Email address
        email_match = re.search(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', raw_text)
        customer_email = email_match.group(0) if email_match else None

        # Monetary amount: $30 or $600.00
        amount_match = re.search(r'\$(\d+(?:\.\d{1,2})?)', raw_text)
        amount = float(amount_match.group(1)) if amount_match else None

        # Request type by keyword
        lower = raw_text.lower()
        if any(kw in lower for kw in ('refund', 'return', 'money back')):
            request_type = 'refund'
        elif any(kw in lower for kw in ('account', 'login', 'password', 'access')):
            request_type = 'account_inquiry'
        elif any(kw in lower for kw in ('complaint', 'broken', 'broke', 'damaged', 'terrible')):
            request_type = 'complaint'
        else:
            request_type = 'unknown'

        return ExtractedRequestInfo(
            customer_id=customer_id,
            customer_email=customer_email,
            order_id=order_id,
            request_type=request_type,
            amount=amount,
        )
