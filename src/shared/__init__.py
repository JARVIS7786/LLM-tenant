"""Shared modules for multi-tenant AI platform."""
from src.shared.config import settings, Settings
from src.shared.types import SLATier, QueueMessage, CompletionResult
from src.shared.models import Base, Tenant, APIKey, UsageRecord
from src.shared.database import engine, SessionLocal, get_db, get_db_context, init_db

__all__ = [
    # Config
    "settings",
    "Settings",
    # Types
    "SLATier",
    "QueueMessage",
    "CompletionResult",
    # Models
    "Base",
    "Tenant",
    "APIKey",
    "UsageRecord",
    # Database
    "engine",
    "SessionLocal",
    "get_db",
    "get_db_context",
    "init_db",
]
