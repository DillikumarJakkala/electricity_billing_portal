from django.shortcuts import render

# Create your views here.
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ElectricityBillForm
from .models import ElectricityBill
from .utils import build_statement_workbook


def _is_billing_admin(user) -> bool:
    return user.is_staff or user.is_superuser


def _portal_context(extra: dict | None = None) -> dict:
    ctx = {
        "ezpigmy_portal_url": getattr(settings, "EZPIGMY_PORTAL_URL", "https://ezpigmy.in/"),
    }
    if extra:
        ctx.update(extra)
    return ctx


@login_required
def role_root_redirect(request):
    if _is_billing_admin(request.user):
        return redirect("admin_dashboard")
    return redirect("resident_dashboard")


@login_required
def admin_dashboard(request):
    if not _is_billing_admin(request.user):
        raise PermissionDenied("Admin access required.")
    bills = ElectricityBill.objects.select_related("meter").all()
    return render(
        request,
        "meter_core/admin_dashboard.html",
        _portal_context({"bills": bills}),
    )


@login_required
def resident_dashboard(request):
    bills = ElectricityBill.objects.select_related("meter").filter(
        meter__resident=request.user
    )
    return render(
        request,
        "meter_core/resident_dashboard.html",
        _portal_context({"bills": bills}),
    )


@login_required
def edit_bill_view(request, bill_id):
    if not _is_billing_admin(request.user):
        raise PermissionDenied("Only admins can edit bills or Other Charges.")
    bill = get_object_or_404(ElectricityBill, pk=bill_id)
    if request.method == "POST":
        form = ElectricityBillForm(request.POST, instance=bill)
        if form.is_valid():
            form.save()
            return redirect("admin_dashboard")
    else:
        form = ElectricityBillForm(instance=bill)
    return render(
        request,
        "meter_core/edit_bill.html",
        _portal_context({"form": form, "bill": bill}),
    )


@require_POST
@login_required
def approve_bill_view(request, bill_id):
    if not _is_billing_admin(request.user):
        raise PermissionDenied("Only admins can approve bills.")
    bill = get_object_or_404(ElectricityBill, pk=bill_id)
    bill.status = "APPROVED"
    bill.save(update_fields=["status", "updated_at"])
    return redirect("admin_dashboard")


@login_required
def export_statement_xlsx(request):
    if _is_billing_admin(request.user):
        bills = ElectricityBill.objects.select_related("meter").all()
    else:
        bills = ElectricityBill.objects.select_related("meter").filter(
            meter__resident=request.user
        )

    wb = build_statement_workbook(bills)
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        'attachment; filename="electricity_bill_statement.xlsx"'
    )
    wb.save(response)
    return response