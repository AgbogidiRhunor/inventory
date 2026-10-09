import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import ProductCreateForm, ProductEditForm
from .image_storage import ImageValidationError, delete_product_image, upload_product_image
from .models import Product, Sale
from .pdf import generate_summary_pdf


class InventoryLoginView(LoginView):
    template_name = "inventory/login.html"


@login_required
def dashboard(request):
    products = _products_with_revenue()
    return render(request, "inventory/dashboard.html", {"products": products})


@login_required
def new_entry(request):
    if request.method == "POST":
        form = ProductCreateForm(request.POST, request.FILES)
        if form.is_valid():
            image_url = None
            image_pathname = None
            uploaded_image = form.cleaned_data.get("image")

            if uploaded_image:
                try:
                    image_url, image_pathname = upload_product_image(uploaded_image)
                except ImageValidationError as exc:
                    form.add_error("image", exc.message if hasattr(exc, "message") else str(exc))
                    return render(request, "inventory/new_entry.html", {"form": form})
                except RuntimeError as exc:
                    messages.error(request, str(exc))
                    return render(request, "inventory/new_entry.html", {"form": form})

            Product.objects.create(
                name=form.cleaned_data["name"],
                image_url=image_url,
                image_blob_pathname=image_pathname,
                price=form.cleaned_data["price"],
                quantity=form.cleaned_data["initial_quantity"],
                quantity_sold=0,
            )
            messages.success(request, "Item added successfully.")
            return redirect("dashboard")
    else:
        form = ProductCreateForm()

    return render(request, "inventory/new_entry.html", {"form": form})


@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = ProductEditForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_image = form.cleaned_data.get("image")

            if uploaded_image:
                try:
                    new_url, new_pathname = upload_product_image(uploaded_image)
                except ImageValidationError as exc:
                    form.add_error("image", exc.message if hasattr(exc, "message") else str(exc))
                    return render(
                        request, "inventory/edit_product.html", {"form": form, "product": product}
                    )
                except RuntimeError as exc:
                    messages.error(request, str(exc))
                    return render(
                        request, "inventory/edit_product.html", {"form": form, "product": product}
                    )

                old_pathname = product.image_blob_pathname
                product.image_url = new_url
                product.image_blob_pathname = new_pathname
                if old_pathname:
                    delete_product_image(old_pathname)

            product.name = form.cleaned_data["name"]
            product.price = form.cleaned_data["price"]
            product.save()
            messages.success(request, "Item updated successfully.")
            return redirect("dashboard")
    else:
        form = ProductEditForm(initial={"name": product.name, "price": product.price})

    return render(request, "inventory/edit_product.html", {"form": form, "product": product})


@login_required
@require_POST
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    pathname = product.image_blob_pathname
    name = product.name
    product.delete()
    if pathname:
        delete_product_image(pathname)
    messages.success(request, f'"{name}" was deleted.')
    return redirect("dashboard")


ZERO = Decimal("0.00")
MAX_PRICE = Decimal("9999999999.99")  # fits max_digits=12, decimal_places=2


def money(value):
    """Format a Decimal as 1,234.50 (no currency symbol)."""
    return f"{(value or ZERO):,.2f}"


def _products_with_revenue():
    """All products, each annotated with `revenue` = sum of its sales' prices."""
    return Product.objects.annotate(
        revenue=Coalesce(
            Sum("sales__unit_price"),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )


def _parse_price(raw):
    """
    Parse a user-supplied price. Returns a Decimal rounded to 2 places, or
    None if it is missing, malformed, negative, or too large.
    """
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", ""))
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    value = value.quantize(ZERO)
    if value > MAX_PRICE:
        return None
    return value


def _json_state(product):
    revenue = product.sales.aggregate(total=Sum("unit_price"))["total"] or ZERO
    return JsonResponse(
        {
            "quantity": product.quantity,
            "quantity_sold": product.quantity_sold,
            "revenue": money(revenue),
        }
    )


@login_required
@require_POST
def adjust_stock(request, pk):
    """
    Increase or decrease available stock only. Never touches quantity_sold.
    Expects JSON body: {"direction": "increase" | "decrease"}
    """
    direction = _get_direction(request)
    if direction not in ("increase", "decrease"):
        return JsonResponse({"error": "Invalid direction."}, status=400)

    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        if direction == "increase":
            product.quantity += 1
        else:
            if product.quantity <= 0:
                return JsonResponse({"error": "Quantity is already zero."}, status=400)
            product.quantity -= 1
        product.save(update_fields=["quantity", "updated_at"])

    return _json_state(product)


@login_required
@require_POST
def adjust_sold(request, pk):
    """
    Record or undo a sale, atomically.

    Record: {"direction": "increase", "price": "400.00"}
        quantity -= 1, quantity_sold += 1, and a Sale row stores the price
        this unit was actually sold for.
    Undo:   {"direction": "decrease"}
        quantity += 1, quantity_sold -= 1, and the most recent Sale row for
        the product is removed (so revenue goes back down too).
    """
    payload = _get_payload(request)
    direction = payload.get("direction")
    if direction not in ("increase", "decrease"):
        return JsonResponse({"error": "Invalid direction."}, status=400)

    sale_price = None
    if direction == "increase":
        sale_price = _parse_price(payload.get("price"))
        if sale_price is None:
            return JsonResponse(
                {"error": "Please enter a valid selling price (0 or more)."}, status=400
            )

    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        if direction == "increase":
            if product.quantity <= 0:
                return JsonResponse({"error": "Cannot record a sale: no stock available."}, status=400)
            product.quantity -= 1
            product.quantity_sold += 1
            Sale.objects.create(product=product, unit_price=sale_price)
        else:
            if product.quantity_sold <= 0:
                return JsonResponse({"error": "No sales to undo."}, status=400)
            product.quantity_sold -= 1
            product.quantity += 1
            # Units sold before prices were tracked have no Sale row; in that
            # case there is simply no revenue to take back.
            last_sale = product.sales.order_by("-created_at", "-id").first()
            if last_sale:
                last_sale.delete()
        product.save(update_fields=["quantity", "quantity_sold", "updated_at"])

    return _json_state(product)


def _get_payload(request):
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return {
        "direction": body.get("direction") or request.POST.get("direction"),
        "price": body.get("price", request.POST.get("price")),
    }


def _get_direction(request):
    return _get_payload(request)["direction"]


def _summary_data():
    products = list(_products_with_revenue())
    return {
        "products": products,
        "total_products": len(products),
        "total_available": sum(p.quantity for p in products),
        "total_sold": sum(p.quantity_sold for p in products),
        "total_revenue": sum((p.revenue for p in products), ZERO),
    }


@login_required
def summary(request):
    return render(request, "inventory/summary.html", _summary_data())


@login_required
def download_summary_pdf(request):
    pdf_bytes = generate_summary_pdf(_summary_data())
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="inventory_summary.pdf"'
    return response
