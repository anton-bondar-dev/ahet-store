from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models import ExpressionWrapper, F, FloatField
from django.db.models.functions import Extract, Now, Power
from django.utils import timezone

# Trending weights: a purchase is worth far more than a view.
TREND_W_VIEW = 1.0
TREND_W_CART = 3.0
TREND_W_PURCHASE = 10.0
TREND_GRAVITY = 1.5  # older products decay faster


class ProductQuerySet(models.QuerySet):
    def with_trending_score(self):
        """Annotate `trending_score` = (V + 3C + 10P) / (age_days + 1)^1.5,
        computed in-DB so it can be ordered/filtered on."""
        age_days = ExpressionWrapper(
            Extract(Now() - F("created_at"), "epoch") / 86400.0,
            output_field=FloatField(),
        )
        weighted = (
            TREND_W_VIEW * F("views_count")
            + TREND_W_CART * F("cart_adds_count")
            + TREND_W_PURCHASE * F("purchases_count")
        )
        return self.annotate(
            trending_score=ExpressionWrapper(
                weighted / Power(age_days + 1.0, TREND_GRAVITY),
                output_field=FloatField(),
            )
        )


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    discount_end_date = models.DateTimeField(blank=True, null=True)
    image = models.ImageField(upload_to="products/images/", blank=True, null=True)

    # Denormalized review aggregates, recomputed from source on each review write.
    average_rating = models.FloatField(default=0)
    reviews_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    # Admin can suppress the "New" badge even within the 30-day window.
    disable_new_badge = models.BooleanField(default=False)
    # Admin override for the bonus points granted; falls back to 1% of price.
    custom_bonus = models.IntegerField(null=True, blank=True)

    # Trending-engine interaction counters (atomic F() increments at each event).
    views_count = models.PositiveIntegerField(default=0)
    cart_adds_count = models.PositiveIntegerField(default=0)
    purchases_count = models.PositiveIntegerField(default=0)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def is_new(self) -> bool:
        if self.disable_new_badge or not self.created_at:
            return False
        return self.created_at >= timezone.now() - timedelta(days=30)

    @property
    def bonus_amount(self) -> int:
        # Admin override wins; otherwise 1% of the effective (discounted) price.
        if self.custom_bonus is not None:
            return self.custom_bonus
        return int(self.effective_price / 100)

    def recompute_rating(self):
        from django.db.models import Avg, Count

        agg = self.reviews.aggregate(a=Avg("rating"), c=Count("id"))
        self.average_rating = round(agg["a"] or 0, 2)
        self.reviews_count = agg["c"]
        self.save(update_fields=["average_rating", "reviews_count"])

    @property
    def effective_price(self):
        # Price actually charged: the discount price during an active sale,
        # otherwise the regular price.
        if self.discount_price is not None and self.is_active:
            return self.discount_price
        return self.price


class RecentlyViewed(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recently_viewed")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recently viewed"
        verbose_name_plural = "Recently viewed"
        unique_together = ("user", "product")
        ordering = ["-viewed_at"]

    def __str__(self):
        return f"{self.user_id} viewed {self.product_id}"
