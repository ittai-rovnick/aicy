"""Langfuse observability and tracing integration"""
import os
from contextlib import contextmanager
from typing import Optional, Any, Dict

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None


class LangfuseTracer:
    """Langfuse tracing manager following best practices"""

    def __init__(self):
        self.client: Optional[Langfuse] = None
        self.enabled = False
        self._initialize()

    def _initialize(self):
        """Initialize Langfuse if credentials are available"""
        if not LANGFUSE_AVAILABLE:
            return

        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if secret_key and public_key:
            try:
                self.client = Langfuse(
                    secret_key=secret_key,
                    public_key=public_key,
                    host=host,
                )
                self.enabled = True
            except Exception as e:
                print(f"Warning: Failed to initialize Langfuse: {e}")

    @contextmanager
    def trace(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for tracing function execution

        Usage:
            with tracer.trace("extract_info", input_data={"text": raw_text}):
                # code to trace
        """
        if not self.enabled or not self.client:
            yield None
            return

        trace = self.client.trace(name=name, input=input_data, metadata=metadata)
        span = trace.span(name=name)

        try:
            yield span
            span.end(output={"success": True})
        except Exception as e:
            span.end(output={"error": str(e)})
            raise

    def log_generation(
        self,
        name: str,
        input_text: str,
        output_text: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an LLM generation call"""
        if not self.enabled or not self.client:
            return

        self.client.generation(
            name=name,
            input=input_text,
            output=output_text,
            model=model,
            metadata=metadata or {},
        )

    def flush(self):
        """Flush any pending traces to Langfuse"""
        if self.enabled and self.client:
            self.client.flush()


# Global tracer instance
_tracer = None


def get_tracer() -> LangfuseTracer:
    """Get the global tracer instance (singleton pattern)"""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer()
    return _tracer
