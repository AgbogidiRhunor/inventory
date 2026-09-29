from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.InventoryLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("new/", views.new_entry, name="new_entry"),
    path("product/<int:pk>/edit/", views.edit_product, name="edit_product"),
    path("product/<int:pk>/delete/", views.delete_product, name="delete_product"),
    path("product/<int:pk>/stock/", views.adjust_stock, name="adjust_stock"),
    path("product/<int:pk>/sold/", views.adjust_sold, name="adjust_sold"),
    path("summary/", views.summary, name="summary"),
    path("summary/pdf/", views.download_summary_pdf, name="summary_pdf"),
]
