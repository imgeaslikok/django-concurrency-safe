import concurrency_safe.decorators as dec
from concurrency_safe.api import lock
from concurrency_safe.exceptions import LockAcquireTimeout

# Context manager tests

class DummyBackend:
    def __init__(self):
        self.acquired = []
        self.released = []

    def acquire(self, key: str, timeout: float | None) -> bool:
        self.acquired.append((key, timeout))
        return True

    def release(self, key: str) -> None:
        self.released.append(key)


def test_lock_context_manager_acquires_and_releases():
    be = DummyBackend()

    with lock("test-key", timeout=1.0, backend=be):
        pass

    assert be.acquired == [("test-key", 1.0)]
    assert be.released == ["test-key"]


class NeverBackend:
    def acquire(self, key: str, timeout: float | None) -> bool:
        return False

    def release(self, key: str) -> None:
        raise AssertionError("release should not be called")


def test_lock_raises_timeout_when_not_acquired():
    be = NeverBackend()

    try:
        with lock("test-key", timeout=0.1, backend=be):
            pass
    except LockAcquireTimeout:
        pass
    else:
        raise AssertionError("Expected LockAcquireTimeout")


# Decorator tests (DB-free)

class DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def test_decorator_returns_function_result_without_db(monkeypatch):
    monkeypatch.setattr(dec, "lock", lambda *a, **k: DummyLock())

    @dec.concurrency_safe(key="test:{x}")
    def f(x):
        return x + 1

    assert f(41) == 42