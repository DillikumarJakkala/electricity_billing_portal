from io import BytesIO
from django.utils import timezone
from openpyxl import Workbook


def build_statement_workbook(bills) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Electricity Bills"

    headers = [
        "Sl. No",
        "Receipt No",
        "Quarter No",
        "RR No",
        "Customer Type",
        "Address",
        "Meter Constant",
        "Billing Period",
        "Duration Range",
        "Days Used",
        "Reading Date",
        "Previous Reading",
        "Current Reading",
        "Units Consumed",
        "Energy Charge",
        "Other Charges",
        "Round Off",
        "Total Amount",
        "Status",
        "Updated At",
    ]
    ws.append(headers)

    for bill in bills:
        meter = bill.meter
        reading_str = bill.reading_date.strftime("%Y-%m-%d") if bill.reading_date else ""
        updated_str = (
            timezone.localtime(bill.updated_at).strftime("%Y-%m-%d %H:%M")
            if bill.updated_at
            else ""
        )
        ws.append([
            bill.sl_no,
            bill.receipt_no,
            meter.qtrs_no if meter else "",
            meter.rr_no if meter else "",
            meter.get_customer_type_display() if meter else "",
            meter.address if meter else "",
            float(meter.meter_constant) if meter and meter.meter_constant is not None else 1.0,
            bill.billing_period or "",
            bill.duration or "",
            int(bill.usage_days or 0),
            reading_str,
            float(bill.previous_reading),
            float(bill.current_reading),
            float(bill.units_consumed),
            float(bill.energy_charge),
            float(bill.other_charges),
            float(bill.round_off),
            float(bill.total_amount),
            bill.get_status_display(),
            updated_str,
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()