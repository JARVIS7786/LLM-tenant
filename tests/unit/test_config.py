"""Tests for configuration management."""
import pytest
from src.shared.config import Settings


def test_settings_defaults():
    """Test that settings load with default values."""
    settings = Settings()
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.redis_host == "localhost"
    assert settings.postgres_db == "mtai_platform"


def test_database_url_construction():
    """Test PostgreSQL URL construction."""
    settings = Settings(
        postgres_user="testuser",
        postgres_password="testpass",
        postgres_host="db.example.com",
        postgres_port=5433,
        postgres_db="testdb"
    )
    expected = "postgresql+psycopg://testuser:testpass@db.example.com:5433/testdb"
    assert settings.database_url == expected


def test_redis_url_construction():
    """Test Redis URL construction."""
    settings = Settings(
        redis_host="redis.example.com",
        redis_port=6380,
        redis_db=1
    )
    expected = "redis://redis.example.com:6380/1"
    assert settings.redis_url == expected
