from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import Any, Callable, Literal, Mapping, Protocol

from .api import lock
from .exceptions import LockAcquireTimeout

Mode = Literal["raise", "return_none", "callable"]


class ConflictHandler(Protocol):
    """
    Called when the lock cannot be acquired within the timeout.
    """
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ConflictPolicy:
    """
    Defines what to do when lock acquisition times out.

    - "raise": raise LockAcquireTimeout (default, explicit and safe)
    - "return_none": return None (useful for best-effort operations)
    - "callable": call user-provided handler and return its result
    """
    mode: Mode = "raise"
    handler: ConflictHandler | None = None


def _resolve_key(
    key: str | Callable[..., str],
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """
    Resolve a lock key from either:
    - a format string: "stock:{sku}"
    - a callable: lambda request, sku: f"stock:{sku}"

    We bind (args, kwargs) against the function signature so format strings can
    use both positional and keyword arguments reliably.
    """
    if callable(key):
        return key(*args, **kwargs)

    bound = signature(fn).bind_partial(*args, **kwargs)
    bound.apply_defaults()
    values: Mapping[str, Any] = bound.arguments

    try:
        return key.format(**values)
    except KeyError as e:
        missing = e.args[0]
        raise KeyError(
            f"concurrency_safe: key template references '{missing}', "
            f"but it is not present in the function arguments. "
            f"Available: {sorted(values.keys())}"
        ) from e


def concurrency_safe(
    *,
    key: str | Callable[..., str],
    timeout: float | None = 3.0,
    on_conflict: Mode | ConflictHandler = "raise",
):
    """
    Decorator that ensures only one concurrent execution per key.

    Examples
    --------
    @concurrency_safe(key="stock:{sku}", timeout=2)
    def buy(request, sku):
        ...

    @concurrency_safe(key=lambda request, sku: f"stock:{sku}")
    def buy(request, sku):
        ...

    Conflict behavior
    -----------------
    - on_conflict="raise" (default): raise LockAcquireTimeout
    - on_conflict="return_none": return None
    - on_conflict=<callable>: call it and return its result
    """
    policy = (
        ConflictPolicy(mode=on_conflict) if isinstance(on_conflict, str)
        else ConflictPolicy(mode="callable", handler=on_conflict)
    )

    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            resolved_key = _resolve_key(key, fn, args, kwargs)

            try:
                with lock(resolved_key, timeout=timeout):
                    return fn(*args, **kwargs)
            except LockAcquireTimeout:
                if policy.mode == "return_none":
                    return None
                if policy.mode == "callable" and policy.handler is not None:
                    return policy.handler(*args, **kwargs)
                raise

        return wrapper

    return decorator