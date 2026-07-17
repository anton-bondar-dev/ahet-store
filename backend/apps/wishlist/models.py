from django.contrib.auth.models import User
from django.db import models


class Favorite(models.Model):
    """A customer's saved product (wishlist entry). One row per (user, product);
    the `created_at` timestamp drives most-recent-first ordering on the page."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favorites"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"
        unique_together = ("user", "product")  # one favorite per user per product
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} ♥ {self.product_id}"
