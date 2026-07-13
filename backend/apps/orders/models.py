from django.db import models


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("cancelled", "Cancelled"),
    ]

    # Anonymous buyer, linked by the same session id the cart uses.
    session_id = models.CharField(max_length=64, db_index=True)

    # Customer details.
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    email = models.EmailField()

    # Shipping.
    city = models.CharField(max_length=255)
    address = models.CharField(max_length=255)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    # Snapshot fields locked at purchase time (immune to later product edits).
    product_title = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Order item"
        verbose_name_plural = "Order items"

    def __str__(self):
        return f"{self.quantity} × {self.product_title} (order #{self.order_id})"
