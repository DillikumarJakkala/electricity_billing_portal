from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def _format_billing_date(bill) -> str:
    dt = getattr(bill, "reading_date", None) or getattr(bill, "updated_at", None)
    if not dt:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_duration(bill) -> str:
    if hasattr(bill, "get_duration_display"):
        return bill.get_duration_display()
    return str(getattr(bill, "duration", "") or "")


def _two_dp(val) -> float:
    dec = Decimal(str(val if val is not None else "0.00")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(dec)


def build_statement_workbook(bills) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Electricity Statement"

    headers = [
        "Sl.No.",
        "Receipt No.",
        "Qtrs No.",
        "RR No.",
        "Billing Period",
        "Duration",
        "Billing Date",
        "Current Reading",
        "Previous Reading",
        "Unit Consumed",
        "Amount in Rs.",
        "Other Charges",
        "Total Amount in Rs.",
        "Status",
    ]

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for bill in bills:
        meter = getattr(bill, "meter", None)
        ws.append(
            [
                getattr(bill, "sl_no", ""),
                getattr(bill, "receipt_no", ""),
                getattr(meter, "qtrs_no", ""),
                getattr(meter, "rr_no", ""),
                getattr(bill, "billing_period", "") or "",
                _format_duration(bill),
                _format_billing_date(bill),
                _two_dp(getattr(bill, "current_reading", Decimal("0.00"))),
                _two_dp(getattr(bill, "previous_reading", Decimal("0.00"))),
                _two_dp(getattr(bill, "units_consumed", Decimal("0.00"))),
                _two_dp(getattr(bill, "energy_charge", Decimal("0.00"))),
                _two_dp(getattr(bill, "other_charges", Decimal("0.00"))),
                _two_dp(getattr(bill, "total_amount", Decimal("0.00"))),
                bill.get_status_display()
                if hasattr(bill, "get_status_display")
                else getattr(bill, "status", ""),
            ]
        )

    for column_cells in ws.columns:
        col_letter = column_cells[0].column_letter
        max_len = max(len(str(c.value or "")) for c in column_cells)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 34)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()