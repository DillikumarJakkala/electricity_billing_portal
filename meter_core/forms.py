from django import forms
from .models import ElectricityBill

BILLING_PERIOD_CHOICES = [
    ("", "-- Select billing period --"),
    ("01 Jan 2026 to 31 Jan 2026", "01 Jan 2026 to 31 Jan 2026"),
    ("01 Feb 2026 to 28 Feb 2026", "01 Feb 2026 to 28 Feb 2026"),
    ("01 Mar 2026 to 31 Mar 2026", "01 Mar 2026 to 31 Mar 2026"),
    ("01 Apr 2026 to 30 Apr 2026", "01 Apr 2026 to 30 Apr 2026"),
    ("01 May 2026 to 31 May 2026", "01 May 2026 to 31 May 2026"),
    ("01 Jun 2026 to 30 Jun 2026", "01 Jun 2026 to 30 Jun 2026"),
    ("01 Jul 2026 to 31 Jul 2026", "01 Jul 2026 to 31 Jul 2026"),
    ("01 Aug 2026 to 31 Aug 2026", "01 Aug 2026 to 31 Aug 2026"),
    ("01 Sep 2026 to 30 Sep 2026", "01 Sep 2026 to 30 Sep 2026"),
    ("01 Oct 2026 to 31 Oct 2026", "01 Oct 2026 to 31 Oct 2026"),
    ("01 Nov 2026 to 30 Nov 2026", "01 Nov 2026 to 30 Nov 2026"),
    ("01 Dec 2026 to 31 Dec 2026", "01 Dec 2026 to 31 Dec 2026"),
]


class ElectricityBillForm(forms.ModelForm):
    billing_period = forms.ChoiceField(
        required=False,
        label="Billing Period",
        choices=BILLING_PERIOD_CHOICES,
    )
    receipt_choice = forms.ChoiceField(
        required=False,
        label="Existing Receipt No. (by Quarter/RR)",
        choices=[("", "-- Select existing receipt or type new --")],
    )

    class Meta:
        model = ElectricityBill
        fields = [
            "meter",
            "sl_no",
            "receipt_choice",
            "receipt_no",
            "billing_period",
            "previous_reading",
            "current_reading",
            "other_charges",
            "round_off",
            "status",
        ]
        widgets = {
            "receipt_no": forms.TextInput(attrs={"id": "id_receipt_no"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(BILLING_PERIOD_CHOICES)
        current_period = getattr(self.instance, "billing_period", "")
        if current_period and all(val != current_period for val, _ in choices):
            choices.append((current_period, current_period))
        self.fields["billing_period"].choices = choices

        meter_id = self.data.get("meter") or getattr(self.instance, "meter_id", None)
        rcp_choices = [("", "-- Select existing receipt or type new --")]
        if meter_id:
            existing_receipts = (
                ElectricityBill.objects.filter(meter_id=meter_id)
                .values_list("receipt_no", flat=True)
                .distinct()
            )
            for rcp in existing_receipts:
                if rcp:
                    rcp_choices.append((rcp, rcp))
        self.fields["receipt_choice"].choices = rcp_choices

    def clean(self):
        cleaned = super().clean()
        selected_rcp = cleaned.get("receipt_choice")
        typed_rcp = (cleaned.get("receipt_no") or "").strip()
        if selected_rcp and not typed_rcp:
            cleaned["receipt_no"] = selected_rcp
        return cleaned