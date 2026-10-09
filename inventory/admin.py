from django.contrib import admin

from .models import Product, Sale


class SaleInline(admin.TabularInline):
    model = Sale
    extra = 0
    fields = ("unit_price", "created_at")
    readonly_fields = ("unit_price", "created_at")
    # View-only: sales are recorded/undone from the dashboard so that the
    # available/sold counters always stay in step with them.
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "quantity", "quantity_sold", "created_at", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("created_at",)
    inlines = [SaleInline]
