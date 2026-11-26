import os
import time

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

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
]


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


def _build_fallback_insight(bill: ElectricityBill) -> dict:
    units = float(bill.units_consumed or 0)
    total = float(bill.total_amount or 0)
    period = bill.billing_period or f"Bill #{bill.pk}"
    if units <= 100:
        slab_note = "Usage is within 100 units (₹8.75/unit lower slab)."
    else:
        slab_note = (
            "Usage crossed 100 units (₹10.75/unit higher slab); "
            "trimming 15–20 units noticeably lowers the bill."
        )
    return {
        "source": "fallback",
        "summary": (
            f"Bill #{bill.pk} ({period}): {units} units consumed, "
            f"total ₹{total:.2f}. {slab_note}"
        ),
        "saving_tips": [
            "Set AC between 24°C–26°C and use timer/eco mode.",
            "Switch off heavy appliances when not in use.",
            "Keep AC/fan filters clean and prefer LED lights.",
        ],
    }


def _generate_bill_insight(client: genai.Client, prompt: str) -> str:
    last_error = None
    for model_name in GEMINI_MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response.text and response.text.strip():
                    return response.text.strip()
                raise RuntimeError("Empty response returned by Gemini model.")
            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                if ("503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str) and attempt == 0:
                    time.sleep(1.5)
                    continue
                break
    raise RuntimeError(f"All Gemini models unavailable; last error: {last_error}")


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
    if isinstance(wb, (bytes, bytearray, memoryview)):
        response.write(bytes(wb))
    else:
        wb.save(response)
    return response


@require_POST
@login_required
def analyze_bill_ai_view(request, bill_id):
    bill = get_object_or_404(ElectricityBill.objects.select_related("meter"), pk=bill_id)
    if not _is_billing_admin(request.user) and bill.meter.resident != request.user:
        raise PermissionDenied("Not authorized to analyze this bill.")

    request.session["ai_bill_id"] = bill.pk
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        request.session["ai_bill_insight"] = _build_fallback_insight(bill)
        messages.warning(request, "GEMINI_API_KEY not set; showing local fallback bill insight.")
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
        text_insight = _generate_bill_insight(client, prompt)
        request.session["ai_bill_insight"] = {
            "source": "gemini",
            "summary": text_insight,
            "saving_tips": [],
        }
    except Exception as exc:
        request.session["ai_bill_insight"] = _build_fallback_insight(bill)
        messages.warning(request, f"Gemini unavailable ({exc}); showing fallback bill insight.")
    return redirect("role_root_redirect")