from django.core.exceptions import ValidationError
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
