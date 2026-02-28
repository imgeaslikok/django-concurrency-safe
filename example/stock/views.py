from __future__ import annotations

import time

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from concurrency_safe import concurrency_safe

from .models import Stock


def _json(
    ok: bool, *, sku: str, qty: int, detail: str | None = None, status: int = 200
) -> JsonResponse:
    """
    Small helper to keep responses consistent across endpoints.
    """
    payload = {"ok": ok, "sku": sku, "qty": qty}
    if detail:
        payload["detail"] = detail
    return JsonResponse(payload, status=status)


def busy_409(*args, **kwargs) -> JsonResponse:
    """
    Conflict handler for concurrency_safe.

    In real APIs you might return 409 (Conflict) or 429 (Too Many Requests),
    depending on your semantics.
    """
    return JsonResponse({"ok": False, "detail": "busy, try again"}, status=409)


@csrf_exempt  # demo-only: curl-friendly
@require_POST
def buy_bad(request: HttpRequest, sku: str) -> HttpResponse:
    """
    Intentionally unsafe endpoint to demonstrate a race condition.

    Two concurrent requests can both read quantity > 0 and both "sell" an item.
    """
    stock = Stock.objects.get(sku=sku)

    if stock.quantity <= 0:
        return _json(
            False, sku=sku, qty=stock.quantity, detail="out of stock", status=409
        )

    # Artificial delay to make the race condition easy to reproduce.
    time.sleep(0.8)

    stock.quantity -= 1
    stock.save(update_fields=["quantity"])

    return _json(True, sku=sku, qty=stock.quantity)


@csrf_exempt  # demo-only: curl-friendly
@require_POST
def buy_safe_db_lock(request: HttpRequest, sku: str) -> HttpResponse:
    """
    Safe endpoint using row-level locks (SELECT ... FOR UPDATE).

    This approach works well when you *have a row to lock* (e.g. Stock record).
    It is database-dependent and not always applicable for business-key locking.
    """
    with transaction.atomic():
        stock = Stock.objects.select_for_update().get(sku=sku)

        if stock.quantity <= 0:
            return _json(
                False, sku=sku, qty=stock.quantity, detail="out of stock", status=409
            )

        time.sleep(0.8)  # keep the same delay for a fair comparison

        stock.quantity -= 1
        stock.save(update_fields=["quantity"])

        return _json(True, sku=sku, qty=stock.quantity)


@csrf_exempt  # demo-only: curl-friendly
@require_POST
@concurrency_safe(key="stock:{sku}", timeout=2.0, on_conflict=busy_409)
def buy_safe_lock(request: HttpRequest, sku: str) -> HttpResponse:
    """
    Safe endpoint using business-key locking (PostgreSQL advisory locks).

    Here we do not rely on row-level locking. Instead, we guard the critical
    section with a lock key derived from business context: "stock:{sku}".

    This pattern generalizes to operations where there is no single row to lock,
    e.g. "withdraw:user:{id}" or "booking:slot:{timestamp}".
    """
    stock = Stock.objects.get(sku=sku)

    if stock.quantity <= 0:
        return _json(
            False, sku=sku, qty=stock.quantity, detail="out of stock", status=409
        )

    time.sleep(0.8)

    stock.quantity -= 1
    stock.save(update_fields=["quantity"])

    return _json(True, sku=sku, qty=stock.quantity)
