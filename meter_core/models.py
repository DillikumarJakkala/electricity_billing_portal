from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re

from django.conf import settings
from django.db import models
from django.utils import timezone

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def _to_date(val):
    if not val:
        return None
    if isinstance(val, datetime):
        if timezone.is_aware(val):
            return timezone.localtime(val).date()
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        cleaned = val.strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def parse_billing_period_dates(period_str):
    if not period_str:
        return None, None
    text = str(period_str).strip()
    parts = re.split(
        r"\s+(?:to|–|—)\s+|\s+-\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) == 2:
        start_d = _to_date(parts[0])
        end_d = _to_date(parts[1])
        if start_d and end_d and end_d >= start_d:
            return start_d, end_d
    return None, None

def calculate_days_from_period(period_str) -> int:
    start_d, end_d = parse_billing_period_dates(period_str)
    if start_d and end_d:
        return (end_d - start_d).days + 1
    return 0


class QuarterMeter(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ("RESIDENTIAL", "Residential"),
        ("DOMESTIC", "Domestic"),
        ("COMMERCIAL", "Commercial"),
        ("INDUSTRIAL", "Industrial"),
        ("INSTITUTIONAL", "Institutional"),
    ]

    resident = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meters",
    )
    qtrs_no = models.CharField(max_length=50, unique=True)
    rr_no = models.CharField(max_length=50, unique=True)
    customer_type = models.CharField(
        max_length=30,
        choices=CUSTOMER_TYPE_CHOICES,
        default="RESIDENTIAL",
    )
    address = models.CharField(
        max_length=255,
        default="Manipal Institute of Technology Campus, MAHE",
    )
    meter_constant = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("1.00")
    )

    def __str__(self):
        return f"{self.qtrs_no} ({self.rr_no} - {self.get_customer_type_display()})"


class ElectricityBill(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("APPROVED", "Approved"),
    ]

    meter = models.ForeignKey(
        QuarterMeter, on_delete=models.CASCADE, related_name="bills"
    )
    sl_no = models.PositiveIntegerField()
    receipt_no = models.CharField(max_length=50)
    billing_period = models.CharField(
        max_length=120,
        blank=True,
    )
    no_of_days = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="No. of Days",
    )
    duration = models.CharField(
        max_length=80,
        blank=True,
    )
    reading_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of Billing / Meter Reading",
    )
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2)

    units_consumed = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False
    )
    slab1_units = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    slab1_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    slab2_units = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    slab2_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    energy_charge = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False
    )
    other_charges = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    round_off = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="PENDING"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sl_no", "-id"]

    @staticmethod
    def calculate_slab_breakdown(units: Decimal):
        two_dp = Decimal("0.01")
        if units <= Decimal("0"):
            zero = Decimal("0.00")
            return zero, zero, zero, zero, zero

        s1_units = min(units, Decimal("100")).quantize(two_dp, rounding=ROUND_HALF_UP)
        s2_units = max(units - Decimal("100"), Decimal("0")).quantize(
            two_dp, rounding=ROUND_HALF_UP
        )
        s1_amt = (s1_units * Decimal("8.75")).quantize(two_dp, rounding=ROUND_HALF_UP)
        s2_amt = (s2_units * Decimal("10.75")).quantize(two_dp, rounding=ROUND_HALF_UP)
        total_energy = (s1_amt + s2_amt).quantize(two_dp, rounding=ROUND_HALF_UP)
        return s1_units, s1_amt, s2_units, s2_amt, total_energy

    @staticmethod
    def calculate_energy_charge(units: Decimal) -> Decimal:
        _, _, _, _, total_energy = ElectricityBill.calculate_slab_breakdown(units)
        return total_energy

    def save(self, *args, **kwargs):
        self.no_of_days = calculate_days_from_period(self.billing_period)

        two_dp = Decimal("0.01")
        raw_diff = max(self.current_reading - self.previous_reading, Decimal("0.00"))
        constant = self.meter.meter_constant if self.meter_id else Decimal("1.00")
        self.units_consumed = (raw_diff * constant).quantize(
            two_dp, rounding=ROUND_HALF_UP
        )
        (
            self.slab1_units,
            self.slab1_amount,
            self.slab2_units,
            self.slab2_amount,
            self.energy_charge,
        ) = self.calculate_slab_breakdown(self.units_consumed)

        gross = self.energy_charge + self.other_charges + self.round_off
        self.total_amount = gross.quantize(two_dp, rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)