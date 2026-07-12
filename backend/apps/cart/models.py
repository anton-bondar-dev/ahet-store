from django.db import models


class Cart(models.Model):
    # Anonymous cart keyed by a client-generated session id (UUID string).
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart {self.session_id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Cart item"
        verbose_name_plural = "Cart items"
        # One row per product per cart; re-adding increments quantity.
        unique_together = ("cart", "product")

    def __str__(self):
        return f"{self.quantity} × {self.product_id} in cart {self.cart_id}"
