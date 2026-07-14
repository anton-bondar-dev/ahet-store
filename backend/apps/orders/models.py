from django.db import models


# Ordered fulfilment pipeline (keys are canonical; labels shown to users).
STATUS_NEW = "new"
STATUS_PROCESSING = "processing"
STATUS_SHIPPED = "shipped"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"

# The 4 stepper stages, in order.
STATUS_FLOW = [STATUS_NEW, STATUS_PROCESSING, STATUS_SHIPPED, STATUS_DELIVERED]

STATUS_LABELS_UK = {
    STATUS_NEW: "Нове",
    STATUS_PROCESSING: "Обробка",
    STATUS_SHIPPED: "Відправлено",
    STATUS_DELIVERED: "Доставлено",
    STATUS_CANCELLED: "Скасовано",
}


class Order(models.Model):
    STATUS_CHOICES = [(key, STATUS_LABELS_UK[key]) for key in
                      STATUS_FLOW + [STATUS_CANCELLED]]

    # Buyer identity: session id for anonymous checkout, user when authenticated.
    session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, blank=True, null=True, related_name="orders"
    )

    # Customer details.
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    email = models.EmailField()

    # Shipping.
    city = models.CharField(max_length=255)
    address = models.CharField(max_length=255)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Bonus points credited to the buyer's account for this order (0 if anonymous).
    bonus_earned = models.IntegerField(default=0)
    # Bonus points spent on this order (1 bonus = 1 UAH); total_price is net of these.
    applied_bonuses = models.IntegerField(default=0)
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
