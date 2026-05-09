"""Shared type definitions."""
from enum import Enum
from typing import TypedDict
from datetime import datetime


class SLATier(str, Enum):
    """SLA tier enumeration."""
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class QueueMessage(TypedDict):
    """Message format for Redis Streams."""
    request_id: str
    tenant_id: str
    api_key: str
    prompt: str
    max_tokens: int
    temperature: float
    enqueued_at: str


class CompletionResult(TypedDict):
    """LLM completion result."""
    request_id: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
