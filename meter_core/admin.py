from django.contrib import admin
from . import models


def _existing_fields(model, candidates):
    valid = {f.name for f in model._meta.get_fields()}
    fields = [name for name in candidates if name in valid]
    return fields or ("__str__",)


if hasattr(models, "QuarterMeter"):
    @admin.register(models.QuarterMeter)
    class QuarterMeterAdmin(admin.ModelAdmin):
        list_display = _existing_fields(
            models.QuarterMeter,
            ["id", "qtrs_no", "rr_no", "resident", "meter_constant"],
        )
        search_fields = _existing_fields(
            models.QuarterMeter,
            ["qtrs_no", "rr_no"],
        )


if hasattr(models, "ElectricityBill"):
    @admin.register(models.ElectricityBill)
    class ElectricityBillAdmin(admin.ModelAdmin):
        list_display = _existing_fields(
            models.ElectricityBill,
            [
                "id",
                "sl_no",
                "receipt_no",
                "meter",
                "billing_date",
                "units_consumed",
                "energy_charge",
                "other_charges",
                "total_amount",
                "status",
            ],
        )
        list_filter = _existing_fields(
            models.ElectricityBill,
            ["status", "billing_date"],
        )
        search_fields = _existing_fields(
            models.ElectricityBill,
            ["receipt_no", "meter__qtrs_no", "meter__rr_no"],
        )