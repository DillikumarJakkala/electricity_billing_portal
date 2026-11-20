from openpyxl import Workbook


def build_statement_workbook(bills):
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly Statement"

    headers = [
        "Sl.No.",
        "Receipt No.",
        "Qtrs No.",
        "RR No.",
        "Billing Date",
        "Current Reading",
        "Previous Reading",
        "Unit Consumed",
        "Amount in Rs.",
        "Other Charges",
        "Total Amount in Rs.",
        "Status",
    ]
    ws.append(headers)

    for bill in bills:
        ws.append([
            bill.sl_no,
            bill.receipt_no,
            bill.meter.qtrs_no,
            bill.meter.rr_no,
            bill.billing_date.isoformat(),
            float(bill.current_reading),
            float(bill.previous_reading),
            float(bill.units_consumed),
            float(bill.energy_charge),
            float(bill.other_charges),
            float(bill.total_amount),
            bill.get_status_display(),
        ])

    return wb