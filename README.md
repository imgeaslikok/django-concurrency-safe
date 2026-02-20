# django-concurrency-safe

[![PyPI version](https://badge.fury.io/py/django-concurrency-safe.svg)](https://pypi.org/project/django-concurrency-safe/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-concurrency-safe.svg)](https://pypi.org/project/django-concurrency-safe/)

Concurrency guard for Django using PostgreSQL advisory locks.

Prevent race conditions in critical sections using simple, expressive decorators or context managers.

---

## Why?

Race conditions are easy to introduce and hard to detect.

Example:

```python
def withdraw(user, amount):
    if user.balance >= amount:
        user.balance -= amount
        user.save()
```

Two concurrent requests can both pass the balance check and withdraw twice.

This library prevents that.

---

## Features

- PostgreSQL advisory lock backend
- Simple decorator API
- Context manager support
- Business-key locking (not limited to database rows)
- Timeout and conflict handling

---

## Installation
```bash
pip install django-concurrency-safe
```
---

## Quickstart
Import:
```python
from concurrency_safe import concurrency_safe, lock, LockAcquireTimeout
```
### Using the decorator
```python
@concurrency_safe(key="withdraw:user:{user_id}")
def withdraw(user_id, amount):
    ...
```
Only one execution per key runs at a time.
### Using the context manager
```python
with lock("stock:ABC"):
    process_order()
```
### Conflict handling
When the lock cannot be acquired:
```python
@concurrency_safe(key="stock:{sku}")
```
Raises `LockAcquireTimeout` by default.

Custom handler:
```python
from django.http import JsonResponse

def busy(*args, **kwargs):
    return JsonResponse({"detail": "busy"}, status=409)

@concurrency_safe(
    key="stock:{sku}",
    on_conflict=busy,
)
```

---

## Example project

`example/` contains a runnable Django demo showcasing the race condition, row-level locks, and advisory locks (PostgreSQL).


---
## Why advisory locks?
Unlike row-level locking, advisory locks:
- Work without locking a specific database row
- Support arbitrary business keys
- Are fast and lightweight
- Automatically release on connection close
---
## Requirements
- Python 3.10+
- Django 4.2+
- PostgreSQL
---
## Roadmap
- Redis backend
- Async support
- Metrics hooks
---
## License
MIT