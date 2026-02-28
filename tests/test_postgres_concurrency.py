"""
PostgreSQL advisory lock integration tests.

These tests validate real concurrency behavior (not mocks):
- The same lock key must block concurrent access (timeout expected).
- Different lock keys must not block each other.

They require a reachable PostgreSQL instance via DATABASE_URL.
CI provides PostgreSQL automatically; locally you can use docker compose.
"""

import os
import threading
import time
from urllib.parse import urlparse

import pytest

from concurrency_safe import LockAcquireTimeout, lock


def _configure_django_if_needed() -> None:
    """Configure a minimal Django DB setup from DATABASE_URL (once per test run)."""
    from django.conf import settings

    if settings.configured:
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not set; skipping PostgreSQL concurrency tests.")

    u = urlparse(database_url)
    if u.scheme not in {"postgres", "postgresql"}:
        pytest.skip(f"Unsupported DATABASE_URL scheme: {u.scheme!r}")

    settings.configure(
        SECRET_KEY="test",
        INSTALLED_APPS=[],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": (u.path or "").lstrip("/"),
                "USER": u.username or "",
                "PASSWORD": u.password or "",
                "HOST": u.hostname or "localhost",
                "PORT": str(u.port or 5432),
                "CONN_MAX_AGE": 0,
            }
        },
        TIME_ZONE="UTC",
        USE_TZ=True,
    )

    import django

    django.setup()


@pytest.fixture(autouse=True)
def _django_setup() -> None:
    _configure_django_if_needed()


def _ensure_thread_connection() -> None:
    """Open a thread-local DB connection early to avoid first-connect races."""
    from django.db import connections

    connections["default"].ensure_connection()


def _close_thread_connection() -> None:
    """Close the thread-local DB connection to avoid leaks between tests."""
    from django.db import connections

    connections["default"].close()


def test_same_key_blocks_and_times_out():
    """The same key must block concurrent acquisition; contender should time out."""
    key = "test:concurrency:same-key"

    started = threading.Event()
    release = threading.Event()
    results: dict[str, object] = {}

    def holder() -> None:
        try:
            _ensure_thread_connection()
            with lock(key, timeout=2.0):
                results["holder_acquired"] = True
                started.set()
                # Hold the lock until the other thread has attempted acquisition.
                release.wait(timeout=2.0)
        finally:
            _close_thread_connection()

    def contender() -> None:
        try:
            _ensure_thread_connection()
            assert started.wait(timeout=2.0)
            t0 = time.monotonic()
            with pytest.raises(LockAcquireTimeout):
                with lock(key, timeout=0.2):
                    pass
            results["contender_elapsed"] = time.monotonic() - t0
        finally:
            _close_thread_connection()

    t1 = threading.Thread(target=holder, name="lock-holder")
    t2 = threading.Thread(target=contender, name="lock-contender")

    t1.start()
    t2.start()
    t2.join(timeout=5.0)
    release.set()
    t1.join(timeout=5.0)

    assert results.get("holder_acquired") is True
    # Sanity: contender should have waited at least some time (not instant pass-through).
    assert results.get("contender_elapsed", 0) >= 0.15


def test_different_keys_do_not_block():
    """Different keys should allow parallel execution (no blocking)."""
    key_a = "test:concurrency:key-a"
    key_b = "test:concurrency:key-b"

    started = threading.Event()
    results: list[str] = []

    def a() -> None:
        try:
            _ensure_thread_connection()
            with lock(key_a, timeout=2.0):
                results.append("a_acquired")
                started.set()
                time.sleep(0.3)
        finally:
            _close_thread_connection()

    def b() -> None:
        try:
            _ensure_thread_connection()
            assert started.wait(timeout=2.0)
            with lock(key_b, timeout=0.5):
                results.append("b_acquired")
        finally:
            _close_thread_connection()

    t1 = threading.Thread(target=a, name="lock-a")
    t2 = threading.Thread(target=b, name="lock-b")

    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert "a_acquired" in results
    assert "b_acquired" in results
