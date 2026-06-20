"""Unit tests for OpenAI LLM client integration"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.llm.client import OpenAILLMClient, MockLLMClient
from src.core.models import ExtractedRequestInfo


class TestMockLLMClient:
    """Test MockLLMClient (always available, no API key required)"""

    def test_extract_order_id(self):
        """Should extract order ID in ORD-### format"""
        llm = MockLLMClient()
        result = llm.extract_info("I want a refund for order ORD-55")
        assert result.order_id == "ORD-55"

    def test_extract_customer_id(self):
        """Should extract customer ID in C#### format"""
        llm = MockLLMClient()
        result = llm.extract_info("My customer ID is C1001")
        assert result.customer_id == "C1001"

    def test_extract_email(self):
        """Should extract email address"""
        llm = MockLLMClient()
        result = llm.extract_info("Contact me at test@example.com")
        assert result.customer_email == "test@example.com"

    def test_extract_amount(self):
        """Should extract monetary amount"""
        llm = MockLLMClient()
        result = llm.extract_info("I paid $45.99 for this item")
        assert result.amount == 45.99

    def test_extract_request_type_refund(self):
        """Should identify refund request"""
        llm = MockLLMClient()
        result = llm.extract_info("I want a refund for my purchase")
        assert result.request_type == "refund"

    def test_extract_request_type_complaint(self):
        """Should identify complaint request"""
        llm = MockLLMClient()
        result = llm.extract_info("This product is broken and damaged")
        assert result.request_type == "complaint"

    def test_extract_request_type_account(self):
        """Should identify account inquiry"""
        llm = MockLLMClient()
        result = llm.extract_info("I can't access my account")
        assert result.request_type == "account_inquiry"

    def test_extract_request_type_unknown(self):
        """Should default to unknown for unrecognized requests"""
        llm = MockLLMClient()
        result = llm.extract_info("Just checking on my order")
        assert result.request_type == "unknown"

    def test_extract_all_fields_together(self):
        """Should extract all fields from a complete request"""
        llm = MockLLMClient()
        text = (
            "Hi, my customer ID is C1001, email is test@example.com. "
            "I want a refund for order ORD-55 for $30.00."
        )
        result = llm.extract_info(text)
        assert result.customer_id == "C1001"
        assert result.customer_email == "test@example.com"
        assert result.order_id == "ORD-55"
        assert result.amount == 30.00
        assert result.request_type == "refund"

    def test_extract_none_for_missing_fields(self):
        """Should return None for fields not present in text"""
        llm = MockLLMClient()
        result = llm.extract_info("Hello world")
        assert result.customer_id is None
        assert result.customer_email is None
        assert result.order_id is None
        assert result.amount is None


class TestOpenAILLMClient:
    """Test OpenAILLMClient with mocked OpenAI API"""

    def test_init_missing_api_key(self):
        """Should raise ValueError if OPENAI_API_KEY not set"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAILLMClient()

    def test_init_with_api_key(self):
        """Should initialize successfully with API key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.llm.client.OpenAI"):
                client = OpenAILLMClient()
                assert client.client is not None
                assert client.model is not None

    @patch("src.llm.client.OpenAI")
    def test_extract_info_calls_openai_api(self, mock_openai_class):
        """Should call OpenAI API with correct parameters"""
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_parsed = ExtractedRequestInfo(
            customer_id="C1001",
            customer_email="test@example.com",
            order_id="ORD-55",
            request_type="refund",
            amount=45.00,
        )
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_parsed))]
        mock_response.usage = MagicMock(total_tokens=50)

        mock_client.beta.chat.completions.parse.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = OpenAILLMClient()
            result = client.extract_info("I want a refund for order ORD-55")

            # Verify API was called
            mock_client.beta.chat.completions.parse.assert_called_once()
            call_kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs

            assert call_kwargs["model"] is not None
            assert call_kwargs["temperature"] is not None
            assert any("refund" in str(msg).lower() for msg in call_kwargs["messages"])

            # Verify result
            assert result.customer_id == "C1001"
            assert result.order_id == "ORD-55"

    @patch("src.llm.client.OpenAI")
    def test_extract_info_returns_pydantic_model(self, mock_openai_class):
        """Should return valid ExtractedRequestInfo Pydantic model"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_parsed = ExtractedRequestInfo(
            customer_id="C1001",
            customer_email=None,
            order_id="ORD-55",
            request_type="refund",
            amount=100.00,
        )
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_parsed))]
        mock_response.usage = MagicMock(total_tokens=75)

        mock_client.beta.chat.completions.parse.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = OpenAILLMClient()
            result = client.extract_info("Test request")

            # Verify it's a Pydantic model
            assert isinstance(result, ExtractedRequestInfo)
            assert result.customer_id == "C1001"
            assert result.order_id == "ORD-55"
            assert result.amount == 100.00
