from django import forms
from django.contrib import admin
from django.db.models import Case, When
from .ai_helper import get_ai_priority
from .models import (
    ElectricityBill,
    QuarterMeter,
    calculate_days_from_period,
    parse_billing_period_dates,
)


class ElectricityBillAdminForm(forms.ModelForm):
    period_from = forms.DateField(
        required=False,
        label="From Date",
        widget=forms.DateInput(
            attrs={"type": "date", "id": "id_period_from", "class": "js-period-date"}
        ),
    )
    period_to = forms.DateField(
        required=False,
        label="To Date",
        widget=forms.DateInput(
            attrs={"type": "date", "id": "id_period_to", "class": "js-period-date"}
        ),
    )
    no_of_days_display = forms.IntegerField(
        required=False,
        label="No. of Days",
        widget=forms.NumberInput(
            attrs={
                "id": "id_no_of_days",
                "readonly": "readonly",
                "style": "background:#f4f6f9;font-weight:600;",
            }
        ),
    )

    class Meta:
        model = ElectricityBill
        fields = [
            "meter",
            "sl_no",
            "receipt_no",
            "period_from",
            "period_to",
            "no_of_days_display",
            "reading_date",
            "previous_reading",
            "current_reading",
            "other_charges",
            "round_off",
            "status",
        ]
        widgets = {
            "reading_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        start_d, end_d = parse_billing_period_dates(
            self.initial.get("billing_period")
            or getattr(self.instance, "billing_period", "")
        )
        if start_d and not self.initial.get("period_from"):
            self.fields["period_from"].initial = start_d
        if end_d and not self.initial.get("period_to"):
            self.fields["period_to"].initial = end_d

        initial_days = getattr(self.instance, "no_of_days", 0)
        if start_d and end_d and end_d >= start_d:
            initial_days = (end_d - start_d).days + 1
        self.fields["no_of_days_display"].initial = initial_days

    def clean(self):
        cleaned_data = super().clean()
        p_from = cleaned_data.get("period_from")
        p_to = cleaned_data.get("period_to")

        if p_from and p_to:
            if p_to < p_from:
                self.add_error("period_to", "To Date cannot be earlier than From Date.")
            else:
                days = (p_to - p_from).days + 1
                cleaned_data["billing_period"] = (
                    f"{p_from.isoformat()} to {p_to.isoformat()}"
                )
                cleaned_data["no_of_days"] = days
                cleaned_data["no_of_days_display"] = days
        else:
            days = calculate_days_from_period(
                getattr(self.instance, "billing_period", "")
            )
            cleaned_data["no_of_days"] = days
            cleaned_data["no_of_days_display"] = days
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "billing_period" in self.cleaned_data:
            instance.billing_period = self.cleaned_data["billing_period"]
        instance.no_of_days = self.cleaned_data.get("no_of_days", 0)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(QuarterMeter)
class QuarterMeterAdmin(admin.ModelAdmin):
    list_display = (
        "qtrs_no",
        "rr_no",
        "customer_type",
        "meter_constant",
        "resident",
    )
    search_fields = ("qtrs_no", "rr_no")
    list_filter = ("customer_type",)


@admin.register(ElectricityBill)
class ElectricityBillAdmin(admin.ModelAdmin):
    form = ElectricityBillAdminForm
    list_display = (
        "sl_no",
        "receipt_no",
        "meter",
        "billing_period",
        "no_of_days",
        "reading_date",
        "units_consumed",
        "total_amount",
        "ai_priority_badge",
        "status",
    )
    list_filter = ("status", "meter__customer_type")
    search_fields = ("receipt_no", "meter__qtrs_no", "meter__rr_no", "billing_period")

    def _get_cached_ai(self, obj):
        if not hasattr(obj, "_ai_cache"):
            obj._ai_cache = get_ai_priority(obj)
        return obj._ai_cache

    @admin.display(description="AI Priority")
    def ai_priority_badge(self, obj):
        score, reason = self._get_cached_ai(obj)
        if score >= 60:
            tag = "HIGH"
        elif score >= 35:
            tag = "MED"
        else:
            tag = "LOW"
        return f"{tag} ({score}) — {reason}"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get("ai_sort") == "1":
            bills = list(qs)
            for b in bills:
                b._ai_cache = get_ai_priority(b)
            bills.sort(key=lambda b: b._ai_cache[0], reverse=True)
            ordered_ids = [b.pk for b in bills]
            if ordered_ids:
                preserved = Case(
                    *[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
                )
                return qs.filter(pk__in=ordered_ids).order_by(preserved)
        return qs

    class Media:
        js = ("meter_core/js/auto_days.js",)