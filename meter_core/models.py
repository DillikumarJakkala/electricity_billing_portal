from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from django.conf import settings
from django.db import models

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
SLAB_LIMIT = Decimal("100.00")
FIRST_SLAB_RATE = Decimal("8.75")
SECOND_SLAB_RATE = Decimal("10.75")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _parse_single_date(token: str):
    token = token.strip().rstrip(".,;")
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _parse_month_year(token: str):
    token = token.strip().rstrip(".,;")
    formats = [
        "%b %Y",
        "%B %Y",
        "%m/%Y",
        "%m-%Y",
        "%Y-%m",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(token, fmt)
            return dt.year, dt.month
        except ValueError:
            continue
    return None


def _month_days(year: int, month: int) -> int:
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    this_first = date(year, month, 1)
    return (next_first - this_first).days


def calculate_duration_days(duration_text: str, reading_date=None) -> int:
    """
    Calculates days from a manual duration range string such as:
    - '2026-10-01 to 2026-10-31' or '01-10-2026 - 31-10-2026'
    - 'Oct 2026 to Nov 2026' or 'October 2026 - December 2026'
    - '30 days' or '45'
    Falls back to reading_date's month days or 30 if only a single month/label is entered.
    """
    text = (duration_text or "").strip()
    if not text:
        if isinstance(reading_date, date):
            return _month_days(reading_date.year, reading_date.month)
        return 30

    # Check explicit "N days"
    days_match = re.search(r"(\d+)\s*days?", text, re.IGNORECASE)
    if days_match:
        return max(int(days_match.group(1)), 1)

    # Split range on 'to', '-', '–', '—', or 'through'
    parts = re.split(r"\s*(?:\bto\b|\bthrough\b|[-–—]{1,2})\s*", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        start_str, end_str = parts[0].strip(), parts[1].strip()

        # Case A: Full dates on both sides
        d1, d2 = _parse_single_date(start_str), _parse_single_date(end_str)
        if d1 and d2:
            diff = abs((d2 - d1).days)
            return max(diff, 1)

        # Case B: Month + Year on both sides (e.g. "Oct 2026 to Nov 2026")
        m1, m2 = _parse_month_year(start_str), _parse_month_year(end_str)
        if m1 and m2:
            y1, mo1 = m1
            y2, mo2 = m2
            if (y2, mo2) < (y1, mo1):
                y1, mo1, y2, mo2 = y2, mo2, y1, mo1

            total_days = 0
            cur_y, cur_m = y1, mo1
            while (cur_y, cur_m) <= (y2, mo2):
                total_days += _month_days(cur_y, cur_m)
                if cur_m == 12:
                    cur_y += 1
                    cur_m = 1
                else:
                    cur_m += 1
            return max(total_days, 1)

    # Case C: Single Month + Year (e.g. "November 2026")
    single_m = _parse_month_year(text)
    if single_m:
        return _month_days(single_m[0], single_m[1])

    if isinstance(reading_date, date):
        return _month_days(reading_date.year, reading_date.month)

    return 30


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
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES,
        default="DOMESTIC",
    )
    address = models.CharField(
        max_length=255,
        default="Manipal Institute of Technology Campus, MAHE",
    )
    meter_constant = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    class Meta:
        ordering = ["qtrs_no"]

    def __str__(self) -> str:
        return f"{self.qtrs_no} ({self.rr_no} - {self.get_customer_type_display()})"


class ElectricityBill(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("APPROVED", "Approved"),
    ]

    meter = models.ForeignKey(
        QuarterMeter,
        on_delete=models.CASCADE,
        related_name="bills",
    )
    sl_no = models.PositiveIntegerField()
    receipt_no = models.CharField(max_length=50)
    billing_period = models.CharField(max_length=80, blank=True)
    duration = models.CharField(
        max_length=120,
        blank=True,
        help_text="Enter manual range e.g. '01-10-2026 to 31-10-2026' or 'Oct 2026 to Nov 2026'",
    )
    usage_days = models.PositiveIntegerField(
        default=30,
        editable=False,
        help_text="Auto-calculated number of days based on duration",
    )
    reading_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the meter reading was taken",
    )
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2)
    units_consumed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=ZERO,
    )
    energy_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=ZERO,
    )
    other_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO,
    )
    round_off = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=ZERO,
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=ZERO,
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sl_no", "-id"]

    def __str__(self) -> str:
        period_label = self.duration or self.billing_period or f"{self.usage_days} days"
        return f"Bill #{self.sl_no} - {self.meter.qtrs_no} ({period_label})"

    @staticmethod
    def calculate_energy_charge(units: Decimal) -> Decimal:
        units_dec = Decimal(str(units or ZERO))
        if units_dec <= ZERO:
            return quantize_money(ZERO)
        if units_dec <= SLAB_LIMIT:
            charge = units_dec * FIRST_SLAB_RATE
        else:
            first_slab = SLAB_LIMIT * FIRST_SLAB_RATE
            remaining_units = units_dec - SLAB_LIMIT
            charge = first_slab + (remaining_units * SECOND_SLAB_RATE)
        return quantize_money(charge)

    def save(self, *args, **kwargs):
        self.usage_days = calculate_duration_days(self.duration, self.reading_date)

        prev_val = Decimal(str(self.previous_reading if self.previous_reading is not None else ZERO))
        curr_val = Decimal(str(self.current_reading if self.current_reading is not None else ZERO))
        constant_val = Decimal(
            str(
                self.meter.meter_constant
                if self.meter_id and self.meter and self.meter.meter_constant is not None
                else Decimal("1.00")
            )
        )
        other_val = Decimal(str(self.other_charges if self.other_charges is not None else ZERO))
        round_val = Decimal(str(self.round_off if self.round_off is not None else ZERO))

        raw_diff = max(curr_val - prev_val, ZERO)
        self.units_consumed = quantize_money(raw_diff * constant_val)
        self.energy_charge = self.calculate_energy_charge(self.units_consumed)
        self.total_amount = quantize_money(self.energy_charge + other_val + round_val)

        super().save(*args, **kwargs)