from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from meter_core.models import ElectricityBill, QuarterMeter, calculate_days_from_period
from meter_core.views import admin_dashboard, analyze_bill_ai_view

User = get_user_model()


class BillingModelAndSlabTests(TestCase):
    def setUp(self):
        self.resident = User.objects.create_user(
            username="resident1",
            password="password123",
        )
        self.admin = User.objects.create_user(
            username="admin1",
            password="password123",
            is_staff=True,
        )
        self.meter = QuarterMeter.objects.create(
            resident=self.resident,
            qtrs_no="QTR-101",
            rr_no="RR-9001",
            customer_type="RESIDENTIAL",
            meter_constant=Decimal("1.00"),
        )

    def test_slab_breakdown_within_100_units(self):
        s1_u, s1_amt, s2_u, s2_amt, total = ElectricityBill.calculate_slab_breakdown(
            Decimal("80.00")
        )
        self.assertEqual(s1_u, Decimal("80.00"))
        self.assertEqual(s1_amt, Decimal("700.00"))
        self.assertEqual(s2_u, Decimal("0.00"))
        self.assertEqual(s2_amt, Decimal("0.00"))
        self.assertEqual(total, Decimal("700.00"))

    def test_slab_breakdown_above_100_units(self):
        s1_u, s1_amt, s2_u, s2_amt, total = ElectricityBill.calculate_slab_breakdown(
            Decimal("140.00")
        )
        self.assertEqual(s1_u, Decimal("100.00"))
        self.assertEqual(s1_amt, Decimal("875.00"))
        self.assertEqual(s2_u, Decimal("40.00"))
        self.assertEqual(s2_amt, Decimal("430.00"))
        self.assertEqual(total, Decimal("1305.00"))

    def test_calculate_days_from_period(self):
        days = calculate_days_from_period("2026-11-01 to 2026-11-30")
        self.assertEqual(days, 30)

    def test_bill_save_computes_units_slabs_and_total(self):
        bill = ElectricityBill.objects.create(
            meter=self.meter,
            sl_no=1,
            receipt_no="RCP-001",
            billing_period="2026-11-01 to 2026-11-30",
            previous_reading=Decimal("100.00"),
            current_reading=Decimal("220.00"),
            other_charges=Decimal("25.00"),
            round_off=Decimal("0.00"),
        )
        self.assertEqual(bill.no_of_days, 30)
        self.assertEqual(bill.units_consumed, Decimal("120.00"))
        self.assertEqual(bill.energy_charge, Decimal("1090.00"))
        self.assertEqual(bill.total_amount, Decimal("1115.00"))
        self.assertEqual(bill.status, "PENDING")

    def test_meter_constant_scaling(self):
        scaled_meter = QuarterMeter.objects.create(
            resident=self.resident,
            qtrs_no="QTR-102",
            rr_no="RR-9002",
            meter_constant=Decimal("2.00"),
        )
        bill = ElectricityBill.objects.create(
            meter=scaled_meter,
            sl_no=2,
            receipt_no="RCP-002",
            previous_reading=Decimal("10.00"),
            current_reading=Decimal("70.00"),
        )
        self.assertEqual(bill.units_consumed, Decimal("120.00"))
        self.assertEqual(bill.energy_charge, Decimal("1090.00"))


class ViewAndAIFallbackTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.resident = User.objects.create_user(
            username="res_user",
            password="password123",
        )
        self.admin = User.objects.create_user(
            username="adm_user",
            password="password123",
            is_staff=True,
        )
        self.meter = QuarterMeter.objects.create(
            resident=self.resident,
            qtrs_no="QTR-201",
            rr_no="RR-9201",
        )
        self.bill = ElectricityBill.objects.create(
            meter=self.meter,
            sl_no=1,
            receipt_no="RCP-201",
            billing_period="2026-10-01 to 2026-10-31",
            previous_reading=Decimal("50.00"),
            current_reading=Decimal("160.00"),
        )

    def test_resident_cannot_access_admin_dashboard(self):
        req = self.factory.get("/dashboard/admin/")
        req.user = self.resident
        with self.assertRaises(PermissionDenied):
            admin_dashboard(req)

    def test_analyze_bill_ai_view_falls_back_without_api_key(self):
        req = self.factory.post(f"/bills/{self.bill.pk}/ai-analyze/")
        req.user = self.resident
        req.session = {}
        setattr(req, "_messages", FallbackStorage(req))
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
            response = analyze_bill_ai_view(req, self.bill.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn("ai_bill_insight", req.session)
        self.assertIn("fallback", req.session["ai_bill_insight"]["source"].lower())
        self.assertEqual(req.session["ai_bill_id"], self.bill.pk)