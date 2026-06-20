"""Unit tests for Langfuse observability integration"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.observability.tracing import LangfuseTracer, get_tracer, LANGFUSE_AVAILABLE


class TestLangfuseTracer:
    """Test LangfuseTracer initialization and behavior"""

    def test_tracer_initializes_without_langfuse_installed(self):
        """Should gracefully handle missing langfuse library"""
        tracer = LangfuseTracer()
        # Should not raise, just disable itself
        assert tracer.client is None or isinstance(tracer.client, type(None))

    def test_tracer_disabled_without_api_keys(self):
        """Should disable tracing if API keys not set"""
        with patch.dict(os.environ, {}, clear=True):
            tracer = LangfuseTracer()
            assert tracer.enabled is False

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_tracer_initializes_with_api_keys(self, mock_langfuse_class):
        """Should initialize Langfuse client when API keys are available"""
        mock_client = MagicMock()
        mock_langfuse_class.return_value = mock_client

        with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
            tracer = LangfuseTracer()
            # Verify Langfuse was instantiated with correct keys
            mock_langfuse_class.assert_called_once()
            call_kwargs = mock_langfuse_class.call_args.kwargs
            assert call_kwargs["secret_key"] == "test-secret"
            assert call_kwargs["public_key"] == "test-public"

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://custom.langfuse.com",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_tracer_uses_custom_host(self, mock_langfuse_class):
        """Should use custom LANGFUSE_HOST if provided"""
        mock_client = MagicMock()
        mock_langfuse_class.return_value = mock_client

        with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
            tracer = LangfuseTracer()
            call_kwargs = mock_langfuse_class.call_args.kwargs
            assert call_kwargs["host"] == "https://custom.langfuse.com"

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_tracer_uses_default_host(self, mock_langfuse_class):
        """Should use default cloud.langfuse.com if no custom host"""
        mock_client = MagicMock()
        mock_langfuse_class.return_value = mock_client

        with patch.dict(os.environ, {"LANGFUSE_HOST": ""}, clear=False):
            os.environ.pop("LANGFUSE_HOST", None)
            with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
                tracer = LangfuseTracer()
                call_kwargs = mock_langfuse_class.call_args.kwargs
                assert call_kwargs["host"] == "https://cloud.langfuse.com"

    def test_trace_context_manager_disabled(self):
        """Should gracefully no-op when tracing disabled"""
        tracer = LangfuseTracer()
        tracer.enabled = False

        # Should not raise, just yield None
        with tracer.trace("test_operation", input_data={"test": "data"}) as span:
            assert span is None

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_trace_context_manager_enabled(self, mock_langfuse_class):
        """Should create span when tracing enabled"""
        mock_client = MagicMock()
        mock_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=None
        )
        mock_langfuse_class.return_value = mock_client

        with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
            tracer = LangfuseTracer()
            tracer.enabled = True
            tracer.client = mock_client

            with tracer.trace(
                "test_operation", input_data={"test": "data"}
            ) as span:
                assert span is not None

            # Verify span was created
            mock_client.start_as_current_observation.assert_called_once()
            call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
            assert call_kwargs["name"] == "test_operation"
            assert call_kwargs["as_type"] == "span"
            assert call_kwargs["input"] == {"test": "data"}

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_log_generation_disabled(self, mock_langfuse_class):
        """Should gracefully no-op when tracing disabled"""
        tracer = LangfuseTracer()
        tracer.enabled = False

        # Should not raise
        tracer.log_generation(
            name="test_gen",
            input_text="test input",
            output_text="test output",
            model="gpt-4",
        )

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_log_generation_enabled(self, mock_langfuse_class):
        """Should log generation when enabled"""
        mock_client = MagicMock()
        mock_gen = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock(
            return_value=mock_gen
        )
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=None
        )
        mock_langfuse_class.return_value = mock_client

        with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
            tracer = LangfuseTracer()
            tracer.enabled = True
            tracer.client = mock_client

            tracer.log_generation(
                name="extract_info",
                input_text="Customer request text",
                output_text='{"customer_id": "C1001"}',
                model="gpt-4",
                metadata={"tokens": 100},
            )

            # Verify generation was logged
            mock_client.start_as_current_observation.assert_called_once()
            call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
            assert call_kwargs["name"] == "extract_info"
            assert call_kwargs["as_type"] == "generation"
            assert call_kwargs["input"] == "Customer request text"
            assert call_kwargs["model"] == "gpt-4"

    def test_flush_disabled(self):
        """Should gracefully handle flush when disabled"""
        tracer = LangfuseTracer()
        tracer.enabled = False

        # Should not raise
        tracer.flush()

    @patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_PUBLIC_KEY": "test-public",
        },
    )
    @patch("src.observability.tracing.Langfuse")
    def test_flush_enabled(self, mock_langfuse_class):
        """Should flush when enabled"""
        mock_client = MagicMock()
        mock_langfuse_class.return_value = mock_client

        with patch("src.observability.tracing.LANGFUSE_AVAILABLE", True):
            tracer = LangfuseTracer()
            tracer.enabled = True
            tracer.client = mock_client

            tracer.flush()

            # Verify flush was called
            mock_client.flush.assert_called_once()

    def test_get_tracer_singleton(self):
        """Should return same tracer instance on multiple calls"""
        # Reset global tracer
        import src.observability.tracing as tracing_module

        tracing_module._tracer = None

        tracer1 = get_tracer()
        tracer2 = get_tracer()

        assert tracer1 is tracer2
