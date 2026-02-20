"""
Exception hierarchy for concurrency_safe.

This module defines all public exceptions raised by the library.

Users are encouraged to catch `ConcurrencySafeError` when they want to handle
all library-related failures, or more specific subclasses such as
`LockAcquireTimeout` when they need fine-grained control.
"""


class ConcurrencySafeError(Exception):
    """
    Base exception for all concurrency_safe errors.

    Catch this exception to handle any failure raised by the library.

    Example
    -------
    >>> try:
    ...     with lock("stock:ABC"):
    ...         ...
    ... except ConcurrencySafeError:
    ...     handle_failure()
    """

    #: Optional error code for programmatic handling in future versions.
    code: str = "concurrency_safe_error"

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = "An unspecified concurrency_safe error occurred."
        super().__init__(message)


class LockAcquireTimeout(ConcurrencySafeError):
    """
    Raised when a lock cannot be acquired within the specified timeout.

    This typically indicates that another worker currently holds the lock.

    Common causes
    -------------
    - A concurrent request is executing the same protected operation
    - The timeout value is too low
    - A long-running operation is holding the lock

    Example
    -------
    >>> try:
    ...     with lock("withdraw:user:42", timeout=1):
    ...         withdraw()
    ... except LockAcquireTimeout:
    ...     retry_later()
    """

    code: str = "lock_acquire_timeout"