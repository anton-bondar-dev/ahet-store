from decimal import Decimal

from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    DISCOUNT_TYPES = [(PERCENTAGE, "Percentage"), (FIXED, "Fixed amount")]

    code = models.CharField(max_length=32, unique=True, db_index=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default=PERCENTAGE)
    # Percentage 0–100 for PERCENTAGE, UAH amount for FIXED.
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)  # null = no expiry
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.IntegerField(null=True, blank=True)  # null = unlimited
    used_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def is_valid(self, subtotal: Decimal) -> bool:
        if not self.is_active:
            return False
        if self.valid_until is not None and self.valid_until < timezone.now():
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        if subtotal < self.min_order_amount:
            return False
        return True

    def discount_for(self, subtotal) -> Decimal:
        """The discount amount for a given subtotal (never exceeds the subtotal)."""
        subtotal = Decimal(str(subtotal))
        value = Decimal(str(self.discount_value))
        if self.discount_type == self.PERCENTAGE:
            raw = subtotal * value / Decimal("100")
        else:
            raw = value
        raw = min(raw, subtotal)
        if raw < 0:
            raw = Decimal("0")
        return raw.quantize(Decimal("0.01"))
