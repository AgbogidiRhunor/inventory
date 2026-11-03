from decimal import Decimal

from django import forms


def _price_field(label):
    return forms.DecimalField(
        label=label,
        min_value=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
    )


# Largest value a PostgreSQL integer column can hold.
MAX_QUANTITY = 2147483647


class ProductCreateForm(forms.Form):
    name = forms.CharField(max_length=200)
    image = forms.ImageField(required=False)
    price = _price_field("Initial Price")
    initial_quantity = forms.IntegerField(min_value=0, max_value=MAX_QUANTITY, initial=0)


class ProductEditForm(forms.Form):
    name = forms.CharField(max_length=200)
    image = forms.ImageField(required=False)
    price = _price_field("Initial Price")
    quantity = forms.IntegerField(
        label="Available Quantity",
        min_value=0,
        max_value=MAX_QUANTITY,
        widget=forms.NumberInput(attrs={"step": "1", "min": "0", "inputmode": "numeric"}),
    )