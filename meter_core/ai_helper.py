from decimal import Decimal, ROUND_HALF_UP
import json
import os
import urllib.error
import urllib.request

from django.conf import settings


def _get_api_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    return str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()


def _get_model_name() -> str:
    return (
        os.environ.get("GEMINI_MODEL", "").strip()
        or str(getattr(settings, "GEMINI_MODEL", "") or "").strip()
        or "gemini-3.5-flash-lite"
    )


def _fallback_score_and_reason(bill) -> tuple[int, str]:
    score = 10
    reasons = []

    units = Decimal(str(getattr(bill, "units_consumed", 0) or 0))
    total = Decimal(str(getattr(bill, "total_amount", 0) or 0))
    other = Decimal(str(getattr(bill, "other_charges", 0) or 0))
    days = int(getattr(bill, "no_of_days", 0) or 0)
    status = str(getattr(bill, "status", "") or "").upper()

    if units >= Decimal("200"):
        score += 35
        reasons.append(f"Very high usage ({units} units)")
    elif units >= Decimal("100"):
        score += 20
        reasons.append(f"Slab-2 usage ({units} units)")

    if days > 0:
        avg_per_day = units / Decimal(days)
        if avg_per_day >= Decimal("8"):
            score += 20
            reasons.append(f"High daily avg ({avg_per_day:.1f} u/day)")

    if other >= Decimal("500"):
        score += 15
        reasons.append(f"High other charges (₹{other})")

    if status == "PENDING" and total >= Decimal("1500"):
        score += 15
        reasons.append(f"Pending high bill (₹{total})")

    score = min(score, 100)
    reason_text = ", ".join(reasons) if reasons else "Normal consumption & charges"
    return score, reason_text


def _gemini_score_and_reason(bill) -> tuple[int, str] | None:
    api_key = _get_api_key()
    if not api_key:
        return None

    model_name = _get_model_name()
    prompt = (
        "Score this electricity bill review priority from 1 (low) to 100 (urgent) "
        "based on high consumption, high daily average, high other charges, or pending status. "
        "Reply ONLY with valid JSON: {\"score\": <int 1-100>, \"reason\": \"<short reason max 8 words>\"}.\n"
        f"Units: {getattr(bill, 'units_consumed', 0)}, "
        f"Days: {getattr(bill, 'no_of_days', 0)}, "
        f"Other charges: {getattr(bill, 'other_charges', 0)}, "
        f"Total: {getattr(bill, 'total_amount', 0)}, "
        f"Status: {getattr(bill, 'status', '')}"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 80},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        cleaned = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        raw_score = int(parsed.get("score", 0))
        reason = str(parsed.get("reason", "")).strip()
        if 1 <= raw_score <= 100 and reason:
            return raw_score, reason[:80]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        return None

    return None


def get_ai_priority(bill) -> tuple[int, str]:
    gemini_result = _gemini_score_and_reason(bill)
    if gemini_result:
        return gemini_result
    return _fallback_score_and_reason(bill)


def check_bill_anomaly(bill) -> dict:
    """Checks meter readings, billing days gap, and consumption spikes."""
    flags = []
    prev_r = Decimal(str(getattr(bill, "previous_reading", 0) or 0))
    curr_r = Decimal(str(getattr(bill, "current_reading", 0) or 0))
    units = Decimal(str(getattr(bill, "units_consumed", 0) or 0))
    days = int(getattr(bill, "no_of_days", 0) or 0)

    if curr_r < prev_r:
        flags.append("Current reading is lower than previous reading (verify meter/rollover)")

    if days > 0 and (days < 15 or days > 45):
        flags.append(f"Unusual billing cycle length ({days} days)")

    if days > 0 and (units / Decimal(days)) >= Decimal("10"):
        flags.append("Sharp daily unit consumption spike — check meter & heavy loads")

    return {
        "has_anomaly": bool(flags),
        "flags": flags,
        "summary": "; ".join(flags) if flags else "No reading or cycle anomaly detected",
    }


def forecast_next_bill(meter) -> dict:
    """Estimates next billing cycle units & slab energy charge from recent bills."""
    two_dp = Decimal("0.01")
    recent_bills = list(meter.bills.order_by("-id")[:3])
    if not recent_bills:
        return {
            "estimated_units": Decimal("0.00"),
            "estimated_energy_charge": Decimal("0.00"),
            "note": "No previous bills available for forecast",
        }

    avg_units = (
        sum(Decimal(str(b.units_consumed or 0)) for b in recent_bills)
        / Decimal(len(recent_bills))
    ).quantize(two_dp, rounding=ROUND_HALF_UP)

    s1_units = min(avg_units, Decimal("100")).quantize(two_dp, rounding=ROUND_HALF_UP)
    s2_units = max(avg_units - Decimal("100"), Decimal("0")).quantize(
        two_dp, rounding=ROUND_HALF_UP
    )
    est_energy = (
        (s1_units * Decimal("8.75")) + (s2_units * Decimal("10.75"))
    ).quantize(two_dp, rounding=ROUND_HALF_UP)

    return {
        "estimated_units": avg_units,
        "estimated_energy_charge": est_energy,
        "note": f"Based on last {len(recent_bills)} bill(s) using 1-100 @ 8.75 & 101+ @ 10.75 slabs",
    }