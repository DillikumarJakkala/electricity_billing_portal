import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from google import genai

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


def _build_bill_summary_text(bill: ElectricityBill) -> str:
    details = [f"Bill ID: {bill.pk}", f"Meter: {bill.meter}"]
    for field in bill._meta.fields:
        if field.name not in ("id", "meter"):
            details.append(f"{field.verbose_name}: {getattr(bill, field.name)}")
    return "\n".join(details)


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
        _portal_context({
            "bills": bills,
            "ai_insight": request.session.pop("ai_bill_insight", None),
            "ai_bill_id": request.session.pop("ai_bill_id", None),
        }),
    )


@login_required
def resident_dashboard(request):
    bills = ElectricityBill.objects.select_related("meter").filter(
        meter__resident=request.user
    )
    return render(
        request,
        "meter_core/resident_dashboard.html",
        _portal_context({
            "bills": bills,
            "ai_insight": request.session.pop("ai_bill_insight", None),
            "ai_bill_id": request.session.pop("ai_bill_id", None),
        }),
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


@require_POST
@login_required
def analyze_bill_ai_view(request, bill_id):
    bill = get_object_or_404(ElectricityBill.objects.select_related("meter"), pk=bill_id)
    if not _is_billing_admin(request.user) and bill.meter.resident != request.user:
        raise PermissionDenied("Not authorized to analyze this bill.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        messages.error(request, "GEMINI_API_KEY is missing in environment variables.")
        return redirect("role_root_redirect")

    client = genai.Client(api_key=api_key)
    bill_data = _build_bill_summary_text(bill)
    prompt = (
        "You are an electricity billing and energy audit assistant. "
        "Analyze this residential quarter electricity bill:\n\n"
        f"{bill_data}\n\n"
        "Give a clear, concise response with:\n"
        "1. Bill & Slab Summary (2 sentences)\n"
        "2. Consumption & Anomaly Check (normal vs. high usage)\n"
        "3. Two practical energy-saving tips for the resident."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        request.session["ai_bill_insight"] = response.text
        request.session["ai_bill_id"] = bill.pk
    except Exception as exc:
        messages.error(request, f"AI analysis failed: {exc}")
    return redirect("role_root_redirect")