from django.contrib import admin
from .models import ElectricityBill, QuarterMeter


@admin.register(QuarterMeter)
class QuarterMeterAdmin(admin.ModelAdmin):
    list_display = ("qtrs_no", "rr_no", "customer_type", "meter_constant", "resident")
    search_fields = ("qtrs_no", "rr_no")


@admin.register(ElectricityBill)
class ElectricityBillAdmin(admin.ModelAdmin):
    list_display = (
        "sl_no",
        "receipt_no",
        "meter",
        "billing_period",
        "billing_date",
        "units_consumed",
        "energy_charge",
        "other_charges",
        "total_amount",
        "status",
    )
    list_filter = ("status", "billing_period")
    search_fields = ("receipt_no", "meter__qtrs_no", "meter__rr_no")