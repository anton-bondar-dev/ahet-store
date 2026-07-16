from django.contrib.auth.models import User
from django.db import models


class Cart(models.Model):
    # Anonymous carts are keyed by a client session id; authenticated carts by
    # user. Exactly one of the two identifies a cart at a time.
    session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True, related_name="carts"
    )
    # Applied discount coupon, if any (validated when attached; consumed at checkout).
    coupon = models.ForeignKey(
        "coupons.Coupon", on_delete=models.SET_NULL, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart {self.user_id or self.session_id}"


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
