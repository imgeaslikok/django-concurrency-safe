from django.db import models


class Stock(models.Model):
    """
    Minimal stock model used to demonstrate race conditions and locking.

    This is intentionally simple: a SKU and an available quantity.
    """

    sku = models.CharField(max_length=64, unique=True)
    quantity = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.sku} ({self.quantity})"
