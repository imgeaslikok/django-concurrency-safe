from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol

from .exceptions import LockAcquireTimeout
from .backends.postgres import PostgresAdvisoryLockBackend


class LockBackend(Protocol):
    """
    Protocol describing the minimal backend interface.

    This allows alternative implementations (e.g. Redis) without changing
    the public API.
    """
    def acquire(self, key: str, timeout: float | None) -> bool: ...
    def release(self, key: str) -> None: ...


# Default backend used when none is explicitly provided.
# Users may override this globally in future versions.
_default_backend: LockBackend = PostgresAdvisoryLockBackend()


@contextmanager
def lock(
    key: str,
    timeout: float | None = 3.0,
    backend: LockBackend | None = None,
) -> Iterator[None]:
    """
    Acquire a concurrency lock for the given key.

    This context manager ensures that only one execution across all workers
    holding the same key may enter the protected block at a time.

    Parameters
    ----------
    key : str
        Unique lock identifier. Typically derived from business context,
        e.g. "stock:ABC", "withdraw:user:42".

    timeout : float | None, default=3.0
        Maximum time (in seconds) to wait for lock acquisition.

        - None: block indefinitely.
        - float: raise LockAcquireTimeout if exceeded.

    backend : LockBackend | None
        Optional backend override. Defaults to the globally configured backend.

    Raises
    ------
    LockAcquireTimeout
        If the lock cannot be acquired within the timeout.

    Example
    -------
    >>> with lock("stock:ABC"):
    ...     process_order()

    Notes
    -----
    Always releases the lock in a finally block, even if the protected code
    raises an exception.
    """
    be = backend or _default_backend

    acquired = be.acquire(key, timeout)

    if not acquired:
        raise LockAcquireTimeout(
            f"Failed to acquire lock for key='{key}' within timeout={timeout}s"
        )

    try:
        yield
    finally:
        # Always release the lock to prevent deadlocks.
        be.release(key)