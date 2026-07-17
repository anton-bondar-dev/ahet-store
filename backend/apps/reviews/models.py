from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Support tagging: the author can flag a review as needing a help-desk reply
    # (e.g. a defect report). Flagged + pending reviews form the admin queue.
    SUPPORT_PENDING = "pending"
    SUPPORT_RESOLVED = "resolved"
    SUPPORT_STATUS_CHOICES = [
        (SUPPORT_PENDING, "Pending"),
        (SUPPORT_RESOLVED, "Resolved"),
    ]
    needs_support = models.BooleanField(default=False)
    support_status = models.CharField(
        max_length=10, choices=SUPPORT_STATUS_CHOICES, default=SUPPORT_PENDING
    )
    support_resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resolved_reviews",
    )
    support_resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        unique_together = ("user", "product")  # one review per user per product
        ordering = ["-created_at"]
        indexes = [
            # Support-moderation queue filters on the flag + its status.
            models.Index(fields=["needs_support", "support_status"]),
        ]

    def __str__(self):
        return f"{self.rating}★ by {self.user_id} on {self.product_id}"


class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="review_replies")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review reply"
        verbose_name_plural = "Review replies"
        ordering = ["created_at"]  # oldest first (conversation order)

    def __str__(self):
        return f"Reply by {self.user_id} on review {self.review_id}"
