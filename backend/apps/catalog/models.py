from django.contrib.auth.models import User
from django.db import models


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

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["title"]

    def __str__(self):
        return self.title

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
