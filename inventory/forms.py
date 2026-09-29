from django import forms

from .models import Product


class ProductCreateForm(forms.Form):
    name = forms.CharField(max_length=200)
    image = forms.ImageField(required=False)
    initial_quantity = forms.IntegerField(min_value=0, initial=0)


class ProductEditForm(forms.Form):
    name = forms.CharField(max_length=200)
    image = forms.ImageField(required=False)
