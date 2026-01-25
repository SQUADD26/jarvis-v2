"""LLM call logging for analytics and cost tracking."""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any
from uuid import uuid4
from datetime import datetime

from jarvis.db.supabase_client import get_db
from jarvis.utils.pricing import calculate_cost, estimate_tokens
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LLMLogEntry:
    """Log entry for an LLM call."""
    provider: str
    model: str
    user_prompt: str

    # Optional fields
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    full_messages: Optional[list] = None

    # Response (filled after call)
    response: Optional[str] = None
    finish_reason: Optional[str] = None

    # Tokens (filled after call or estimated)
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    # Performance (filled after call)
    latency_ms: int = 0
    total_time_ms: int = 0

    # Config
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_used: Optional[list] = None
    metadata: dict = field(default_factory=dict)

    # Error tracking
    is_error: bool = False
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Internal
    _start_time: float = field(default=0.0, repr=False)
    _request_id: str = field(default_factory=lambda: str(uuid4()))

    def start_timer(self):
        """Start timing the request."""
        self._start_time = time.perf_counter()

    def stop_timer(self):
        """Stop timing and calculate duration."""
        if self._start_time > 0:
            elapsed = time.perf_counter() - self._start_time
            self.total_time_ms = int(elapsed * 1000)
            if self.latency_ms == 0:
                self.latency_ms = self.total_time_ms

    def estimate_tokens_if_missing(self):
        """Estimate tokens if not provided by the API."""
        if self.input_tokens == 0:
            # Estimate from prompts
            system_tokens = estimate_tokens(self.system_prompt) if self.system_prompt else 0
            user_tokens = estimate_tokens(self.user_prompt)
            if self.full_messages:
                user_tokens = sum(estimate_tokens(m.get("content", "")) for m in self.full_messages)
            self.input_tokens = system_tokens + user_tokens

        if self.output_tokens == 0 and self.response:
            self.output_tokens = estimate_tokens(self.response)

    def calculate_costs(self) -> tuple[float, float, float]:
        """Calculate costs based on tokens and model pricing."""
        self.estimate_tokens_if_missing()
        return calculate_cost(
            self.provider,
            self.model,
            self.input_tokens,
            self.output_tokens,
            self.cached_tokens
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        input_cost, output_cost, total_cost = self.calculate_costs()

        return {
            "request_id": self._request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt[:10000] if self.user_prompt else None,  # Truncate if too long
            "full_messages": self.full_messages,
            "response": self.response[:50000] if self.response else None,  # Truncate if too long
            "finish_reason": self.finish_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "latency_ms": self.latency_ms,
            "total_time_ms": self.total_time_ms,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools_used": self.tools_used,
            "metadata": self.metadata,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "error_code": self.error_code,
        }


class LLMLogger:
    """Async logger for LLM calls."""

    def __init__(self, buffer_size: int = 10, flush_interval: float = 5.0):
        self._buffer: list[LLMLogEntry] = []
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._enabled = True

    async def log(self, entry: LLMLogEntry):
        """Add a log entry to the buffer."""
        if not self._enabled:
            return

        async with self._lock:
            self._buffer.append(entry)

            # Start flush task if not running
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._periodic_flush())

            # Flush if buffer is full
            if len(self._buffer) >= self._buffer_size:
                await self._flush()

    async def _periodic_flush(self):
        """Periodically flush the buffer."""
        while self._enabled:
            await asyncio.sleep(self._flush_interval)
            async with self._lock:
                if self._buffer:
                    await self._flush()

    async def _flush(self):
        """Flush buffer to database."""
        if not self._buffer:
            return

        entries = self._buffer.copy()
        self._buffer.clear()

        try:
            db = get_db()
            data = [e.to_dict() for e in entries]
            # Run database operation in thread pool to avoid blocking event loop
            await asyncio.to_thread(
                lambda: db.table("llm_logs").insert(data).execute()
            )
            logger.debug(f"Flushed {len(entries)} LLM log entries")
        except Exception as e:
            logger.error(f"Failed to flush LLM logs: {e}")
            # Re-add to buffer on failure (with limit to prevent memory issues)
            async with self._lock:
                self._buffer = entries[:50] + self._buffer[:50]

    async def flush_now(self):
        """Force flush all pending logs."""
        async with self._lock:
            await self._flush()

    def disable(self):
        """Disable logging."""
        self._enabled = False

    def enable(self):
        """Enable logging."""
        self._enabled = True


# Singleton instance
llm_logger = LLMLogger()


# Convenience function for quick logging
async def log_llm_call(
    provider: str,
    model: str,
    user_prompt: str,
    response: str,
    user_id: str = None,
    system_prompt: str = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    temperature: float = None,
    **kwargs
):
    """Quick function to log an LLM call."""
    entry = LLMLogEntry(
        provider=provider,
        model=model,
        user_prompt=user_prompt,
        response=response,
        user_id=user_id,
        system_prompt=system_prompt,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        temperature=temperature,
        **kwargs
    )
    await llm_logger.log(entry)
