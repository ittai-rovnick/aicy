"""LLM client implementations with Strategy pattern"""
from abc import ABC, abstractmethod
import os
import json

from openai import OpenAI
from src.models import ExtractedRequestInfo
from config.config import OPENAI_MODEL, LLM_TEMPERATURE
from src.tracing import get_tracer


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
