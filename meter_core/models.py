from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models


class QuarterMeter(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ("DOMESTIC", "Domestic"),
        ("COMMERCIAL", "Commercial"),
        ("RESIDENTIAL", "Residential"),
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
        default="DOMESTIC",
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
    billing_period = models.CharField(max_length=80, blank=True)
    billing_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2)

    units_consumed = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False
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
    def calculate_energy_charge(units: Decimal) -> Decimal:
        if units <= Decimal("0"):
            return Decimal("0.00")
        slab1_units = min(units, Decimal("100"))
        slab2_units = max(units - Decimal("100"), Decimal("0"))
        charge = (slab1_units * Decimal("8.75")) + (
            slab2_units * Decimal("10.75")
        )
        return charge.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if self.period_start and self.period_end and not self.billing_period:
            self.billing_period = (
                f"{self.period_start.strftime('%d %b %Y')} to "
                f"{self.period_end.strftime('%d %b %Y')}"
            )

        raw_diff = max(self.current_reading - self.previous_reading, Decimal("0.00"))
        constant = self.meter.meter_constant if self.meter_id else Decimal("1.00")
        self.units_consumed = (raw_diff * constant).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.energy_charge = self.calculate_energy_charge(self.units_consumed)
        gross = self.energy_charge + self.other_charges + self.round_off
        self.total_amount = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)