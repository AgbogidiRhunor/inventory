import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Product, Sale


class InventoryPriceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff", password="pw12345!")
        self.client.login(username="staff", password="pw12345!")

    def _post(self, name, **payload):
        pk = payload.pop("pk")
        return self.client.post(
            reverse(name, args=[pk]), data=json.dumps(payload), content_type="application/json"
        )

    def _product(self, quantity=4, price="400.00"):
        return Product.objects.create(name="Laptop", quantity=quantity, price=Decimal(price))

    # --- creating / showing the initial price -------------------------
    def test_new_entry_saves_initial_price(self):
        resp = self.client.post(
            reverse("new_entry"), {"name": "Laptop", "price": "400", "initial_quantity": "4"}
        )
        self.assertRedirects(resp, reverse("dashboard"))
        p = Product.objects.get()
        self.assertEqual((p.price, p.quantity, p.quantity_sold), (Decimal("400.00"), 4, 0))

    def test_new_entry_requires_valid_price(self):
        for bad in ("", "-5", "abc"):
            resp = self.client.post(
                reverse("new_entry"), {"name": "X", "price": bad, "initial_quantity": "1"}
            )
            self.assertEqual(resp.status_code, 200, bad)
        self.assertEqual(Product.objects.count(), 0)

    def test_dashboard_shows_price(self):
        self._product(price="1234.5")
        self.assertContains(self.client.get(reverse("dashboard")), "1,234.50")

    def test_edit_changes_price_without_touching_past_sales(self):
        p = self._product()
        self._post("adjust_sold", pk=p.pk, direction="increase", price="380")
        self.client.post(reverse("edit_product", args=[p.pk]), {"name": "Laptop", "price": "500"})
        p.refresh_from_db()
        self.assertEqual(p.price, Decimal("500.00"))
        self.assertEqual(Sale.objects.get().unit_price, Decimal("380.00"))

    # --- selling at a custom price ------------------------------------
    def test_sale_records_price_actually_sold_for(self):
        p = self._product()  # 4 units, listed at 400
        resp = self._post("adjust_sold", pk=p.pk, direction="increase", price="350.50")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual((data["quantity"], data["quantity_sold"], data["revenue"]), (3, 1, "350.50"))
        self.assertEqual(Sale.objects.get().unit_price, Decimal("350.50"))

    def test_each_sale_can_have_a_different_price(self):
        p = self._product()
        self._post("adjust_sold", pk=p.pk, direction="increase", price="400")
        data = self._post("adjust_sold", pk=p.pk, direction="increase", price="300").json()
        self.assertEqual(data["revenue"], "700.00")
        self.assertEqual(data["quantity_sold"], 2)

    def test_sale_requires_valid_price_and_changes_nothing_otherwise(self):
        p = self._product()
        for bad in (None, "", "abc", "-1", "NaN", "Infinity", "99999999999999"):
            payload = {"pk": p.pk, "direction": "increase"}
            if bad is not None:
                payload["price"] = bad
            self.assertEqual(self._post("adjust_sold", **payload).status_code, 400, bad)
        p.refresh_from_db()
        self.assertEqual((p.quantity, p.quantity_sold, Sale.objects.count()), (4, 0, 0))

    def test_zero_price_sale_allowed(self):
        p = self._product()
        self.assertEqual(self._post("adjust_sold", pk=p.pk, direction="increase", price="0").status_code, 200)

    def test_cannot_sell_when_out_of_stock(self):
        p = self._product(quantity=0)
        resp = self._post("adjust_sold", pk=p.pk, direction="increase", price="100")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    # --- undoing -------------------------------------------------------
    def test_undo_removes_most_recent_sale_and_restores_stock(self):
        p = self._product()
        self._post("adjust_sold", pk=p.pk, direction="increase", price="400")
        self._post("adjust_sold", pk=p.pk, direction="increase", price="300")
        data = self._post("adjust_sold", pk=p.pk, direction="decrease").json()
        self.assertEqual((data["quantity"], data["quantity_sold"], data["revenue"]), (3, 1, "400.00"))
        self.assertEqual(Sale.objects.count(), 1)

    def test_undo_with_nothing_sold_fails(self):
        p = self._product()
        self.assertEqual(self._post("adjust_sold", pk=p.pk, direction="decrease").status_code, 400)

    def test_undo_of_legacy_sale_without_price_record(self):
        # Units sold before prices were tracked have no Sale row.
        p = Product.objects.create(name="Old", quantity=5, quantity_sold=2)
        data = self._post("adjust_sold", pk=p.pk, direction="decrease").json()
        self.assertEqual((data["quantity"], data["quantity_sold"], data["revenue"]), (6, 1, "0.00"))

    # --- stock controls unaffected ------------------------------------
    def test_stock_adjust_does_not_touch_sales(self):
        p = self._product()
        self._post("adjust_sold", pk=p.pk, direction="increase", price="400")
        data = self._post("adjust_stock", pk=p.pk, direction="increase").json()
        self.assertEqual((data["quantity"], data["quantity_sold"], data["revenue"]), (4, 1, "400.00"))

    # --- summary / pdf -------------------------------------------------
    def test_summary_totals_and_per_item_revenue(self):
        a = self._product()
        b = Product.objects.create(name="Mouse", quantity=10, price=Decimal("20"))
        self._post("adjust_sold", pk=a.pk, direction="increase", price="400")
        self._post("adjust_sold", pk=a.pk, direction="increase", price="350")
        self._post("adjust_sold", pk=b.pk, direction="increase", price="25")
        resp = self.client.get(reverse("summary"))
        self.assertEqual(resp.context["total_revenue"], Decimal("775.00"))
        self.assertEqual(resp.context["total_sold"], 3)
        self.assertEqual(resp.context["total_available"], 2 + 9)
        revenue = {p.name: p.revenue for p in resp.context["products"]}
        self.assertEqual(revenue, {"Laptop": Decimal("750.00"), "Mouse": Decimal("25.00")})
        self.assertContains(resp, "775.00")

    def test_summary_with_no_products(self):
        resp = self.client.get(reverse("summary"))
        self.assertEqual(resp.context["total_revenue"], Decimal("0"))

    def test_pdf_generates_with_revenue(self):
        p = self._product()
        self._post("adjust_sold", pk=p.pk, direction="increase", price="400")
        resp = self.client.get(reverse("summary_pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_pdf_handles_special_characters_in_names(self):
        Product.objects.create(name="Tom & <Jerry> Mug", quantity=1, price=Decimal("5"))
        self.assertEqual(self.client.get(reverse("summary_pdf")).status_code, 200)

    # --- auth ----------------------------------------------------------
    def test_sale_endpoint_requires_login(self):
        p = self._product()
        self.client.logout()
        resp = self._post("adjust_sold", pk=p.pk, direction="increase", price="1")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)
