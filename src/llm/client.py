"""LLM client implementations with Strategy pattern"""
from abc import ABC, abstractmethod
import os

from openai import OpenAI
from src.models import ExtractedRequestInfo
from config.config import OPENAI_MODEL, LLM_TEMPERATURE


class LLMClientInterface(ABC):
    """Abstract LLM client interface"""

    @abstractmethod
    def extract_info(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract structured info from raw request text"""
        pass


class OpenAILLMClient(LLMClientInterface):
    """OpenAI client with Langfuse integration"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = OPENAI_MODEL

        try:
            from langfuse.decorators import observe

            self.observe = observe
            self.langfuse_enabled = True
        except ImportError:
            self.observe = None
            self.langfuse_enabled = False

    def extract_info(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract request info from text using OpenAI structured output"""

        if self.langfuse_enabled and self.observe:
            return self._extract_with_langfuse(raw_text)
        else:
            return self._extract_without_langfuse(raw_text)

    def _extract_with_langfuse(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract with Langfuse observability"""

        @self.observe(name="extract_request_info", as_type="generation")
        def _extract():
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                temperature=LLM_TEMPERATURE,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a customer request information extractor.
Extract the following fields from customer messages:
- customer_id: The customer ID (format: C####)
- customer_email: The customer's email address
- order_id: The order ID (format: ORD-###)
- request_type: One of: refund, account_inquiry, complaint, unknown
- amount: The monetary amount mentioned (numeric value only)

Be precise. Only extract information explicitly mentioned in the message.""",
                    },
                    {"role": "user", "content": raw_text},
                ],
                response_format=ExtractedRequestInfo,
            )

            return response.choices[0].message.parsed

        return _extract()

    def _extract_without_langfuse(self, raw_text: str) -> ExtractedRequestInfo:
        """Extract without Langfuse observability"""
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            temperature=LLM_TEMPERATURE,
            messages=[
                {
                    "role": "system",
                    "content": """You are a customer request information extractor.
Extract the following fields from customer messages:
- customer_id: The customer ID (format: C####)
- customer_email: The customer's email address
- order_id: The order ID (format: ORD-###)
- request_type: One of: refund, account_inquiry, complaint, unknown
- amount: The monetary amount mentioned (numeric value only)

Be precise. Only extract information explicitly mentioned in the message.""",
                },
                {"role": "user", "content": raw_text},
            ],
            response_format=ExtractedRequestInfo,
        )

        return response.choices[0].message.parsed
