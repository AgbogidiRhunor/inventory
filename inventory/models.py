from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    """
    A single inventory item. Images are stored in Vercel Blob; only the
    resulting public URL (and blob pathname, for later deletion) is kept
    here — the database never stores the actual image file.
    """

    name = models.CharField(max_length=200)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    # Vercel Blob's own path/key for the current image, kept so we can
    # delete the blob later (on replace or product deletion).
    image_blob_pathname = models.CharField(max_length=500, blank=True, null=True)

    # The item's initial/list price. It is only the *default* offered when a
    # sale is recorded; the real price of each sale is stored on Sale.
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    quantity = models.PositiveIntegerField(default=0)
    quantity_sold = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError("Available quantity cannot be negative.")
        if self.quantity_sold is not None and self.quantity_sold < 0:
            raise ValidationError("Sold quantity cannot be negative.")


class Sale(models.Model):
    """
    One unit sold, at the price it was actually sold for (which may differ
    from Product.price). Product.quantity_sold is the count of these rows
    (plus any units recorded before prices were tracked).
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.product.name} @ {self.unit_price}"
