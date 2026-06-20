"""Langfuse observability and tracing integration — compatible with Langfuse SDK v4+"""
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

    def __init__(self):
        self.client: Optional[Langfuse] = None
        self.enabled = False
        self._initialize()

    def _initialize(self):
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
        """Context manager that creates a Langfuse span wrapping the block."""
        if not self.enabled or not self.client:
            yield None
            return

        with self.client.start_as_current_observation(
            name=name,
            as_type="span",
            input=input_data,
            metadata=metadata,
        ) as span:
            yield span

    def log_generation(
        self,
        name: str,
        input_text: str,
        output_text: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ):
        """Log an LLM generation as a child generation observation inside the current span."""
        if not self.enabled or not self.client:
            return

        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="generation",
                input=input_text,
                output=output_text,
                model=model,
                metadata=metadata or {},
            ):
                pass
        except Exception as e:
            print(f"[WARN] Generation logging error: {e}")

    def flush(self):
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                print(f"[WARN] Flush error: {e}")


_tracer = None


def get_tracer() -> LangfuseTracer:
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer()
    return _tracer
