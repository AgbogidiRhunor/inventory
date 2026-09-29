import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import ProductCreateForm, ProductEditForm
from .image_storage import ImageValidationError, delete_product_image, upload_product_image
from .models import Product
from .pdf import generate_summary_pdf


class InventoryLoginView(LoginView):
    template_name = "inventory/login.html"


@login_required
def dashboard(request):
    products = Product.objects.all()
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
            product.save()
            messages.success(request, "Item updated successfully.")
            return redirect("dashboard")
    else:
        form = ProductEditForm(initial={"name": product.name})

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


def _json_state(product):
    return JsonResponse({"quantity": product.quantity, "quantity_sold": product.quantity_sold})


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
    Record or undo a sale. A sale moves one unit from quantity to
    quantity_sold (or back again), atomically.
    Expects JSON body: {"direction": "increase" | "decrease"}
    """
    direction = _get_direction(request)
    if direction not in ("increase", "decrease"):
        return JsonResponse({"error": "Invalid direction."}, status=400)

    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        if direction == "increase":
            if product.quantity <= 0:
                return JsonResponse({"error": "Cannot record a sale: no stock available."}, status=400)
            product.quantity -= 1
            product.quantity_sold += 1
        else:
            if product.quantity_sold <= 0:
                return JsonResponse({"error": "No sales to undo."}, status=400)
            product.quantity_sold -= 1
            product.quantity += 1
        product.save(update_fields=["quantity", "quantity_sold", "updated_at"])

    return _json_state(product)


def _get_direction(request):
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        body = {}
    return body.get("direction") or request.POST.get("direction")


@login_required
def summary(request):
    products = Product.objects.all()
    total_products = products.count()
    total_available = sum(p.quantity for p in products)
    total_sold = sum(p.quantity_sold for p in products)
    return render(
        request,
        "inventory/summary.html",
        {
            "products": products,
            "total_products": total_products,
            "total_available": total_available,
            "total_sold": total_sold,
        },
    )


@login_required
def download_summary_pdf(request):
    products = Product.objects.all()
    pdf_bytes = generate_summary_pdf(products)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="inventory_summary.pdf"'
    return response
