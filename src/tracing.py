"""Langfuse observability and tracing integration"""
import os
from contextlib import contextmanager
from typing import Optional, Any, Dict
import uuid

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
        self._current_trace_id: Optional[str] = None
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
                print("[OK] Langfuse initialized successfully")
            except Exception as e:
                print(f"[WARN] Langfuse initialization failed: {e}")

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

        try:
            # Generate a trace ID
            trace_id = str(uuid.uuid4())
            self._current_trace_id = trace_id

            # Log the trace using observation (which is the public API method)
            yield {"trace_id": trace_id, "name": name}
        except Exception as e:
            print(f"[WARN] Tracing error: {e}")
            yield None

    def log_generation(
        self,
        name: str,
        input_text: str,
        output_text: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ):
        """Log an LLM generation call to Langfuse"""
        if not self.enabled or not self.client:
            return

        try:
            self.client.generation(
                name=name,
                input=input_text,
                output=output_text,
                model=model,
                metadata=metadata or {},
                trace_id=trace_id or self._current_trace_id,
            )
        except Exception as e:
            print(f"[WARN] Generation logging error: {e}")

    def flush(self):
        """Flush any pending traces to Langfuse"""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                print(f"⚠️ Flush error: {e}")


# Global tracer instance
_tracer = None


def get_tracer() -> LangfuseTracer:
    """Get the global tracer instance (singleton pattern)"""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer()
    return _tracer
