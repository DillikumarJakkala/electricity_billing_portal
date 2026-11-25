from django import forms
from .models import (
    ElectricityBill,
    QuarterMeter,
    calculate_days_from_period,
    parse_billing_period_dates,
)


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
    period_from = forms.DateField(
        required=False,
        label="Billing Period From",
        widget=forms.DateInput(attrs={"type": "date", "id": "id_period_from"}),
    )
    period_to = forms.DateField(
        required=False,
        label="Billing Period To",
        widget=forms.DateInput(attrs={"type": "date", "id": "id_period_to"}),
    )

    class Meta:
        model = ElectricityBill
        fields = [
            "meter",
            "sl_no",
            "receipt_no",
            "period_from",
            "period_to",
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
            "billing_period": forms.TextInput(
                attrs={
                    "id": "id_billing_period",
                    "placeholder": "Auto-filled from From & To dates",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        start_d, end_d = parse_billing_period_dates(
            self.initial.get("billing_period") or getattr(self.instance, "billing_period", "")
        )
        if start_d and not self.initial.get("period_from"):
            self.fields["period_from"].initial = start_d
        if end_d and not self.initial.get("period_to"):
            self.fields["period_to"].initial = end_d

    def clean(self):
        cleaned_data = super().clean()
        p_from = cleaned_data.get("period_from")
        p_to = cleaned_data.get("period_to")

        if p_from and p_to:
            if p_to < p_from:
                self.add_error("period_to", "To Date cannot be earlier than From Date.")
            else:
                cleaned_data["billing_period"] = f"{p_from.isoformat()} to {p_to.isoformat()}"
                cleaned_data["no_of_days"] = (p_to - p_from).days + 1
        else:
            cleaned_data["no_of_days"] = calculate_days_from_period(
                cleaned_data.get("billing_period")
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("billing_period"):
            instance.billing_period = self.cleaned_data["billing_period"]
        instance.no_of_days = self.cleaned_data.get(
            "no_of_days", calculate_days_from_period(instance.billing_period)
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance