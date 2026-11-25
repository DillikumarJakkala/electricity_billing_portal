from django import forms
from .models import ElectricityBill, QuarterMeter


class QuarterMeterForm(forms.ModelForm):
    class Meta:
        model = QuarterMeter
        fields = [
            "resident",
            "qtrs_no",
            "rr_no",
            "customer_type",
            "address",
            "meter_constant",
        ]


class ElectricityBillForm(forms.ModelForm):
    class Meta:
        model = ElectricityBill
        fields = [
            "meter",
            "sl_no",
            "receipt_no",
            "billing_period",
            "duration",
            "reading_date",
            "previous_reading",
            "current_reading",
            "other_charges",
            "round_off",
            "status",
        ]
        widgets = {
            "reading_date": forms.DateInput(attrs={"type": "date"}),
            "duration": forms.TextInput(
                attrs={
                    "id": "id_duration",
                    "placeholder": "e.g. 01-10-2026 to 31-10-2026 or Oct 2026 to Nov 2026",
                }
            ),
            "billing_period": forms.TextInput(
                attrs={"placeholder": "e.g. November 2026"}
            ),
        }