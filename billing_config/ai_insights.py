import json
import os
import urllib.request


def _fallback_insight(units: float, amount: float, billing_period: str) -> dict:
    tips = [
        "Set AC temperature around 24°C–26°C and use timer/eco mode.",
        "Avoid running heavy loads unnecessarily and turn off idle appliances.",
        "Keep fans/AC filters clean and use LED lighting to reduce steady consumption.",
    ]
    if units <= 100:
        slab_note = "Consumption stayed within the lower slab (up to 100 units at ₹8.75/unit)."
    else:
        slab_note = (
            "Consumption crossed into the higher slab (above 100 units at ₹10.75/unit); "
            "trimming even 15–20 units noticeably lowers the bill."
        )

    return {
        "source": "fallback",
        "summary": (
            f"For {billing_period}, total usage is {units} units with a bill amount of ₹{amount:.2f}. "
            f"{slab_note}"
        ),
        "saving_tips": tips,
    }


def generate_bill_insight(
    units: float,
    amount: float,
    billing_period: str,
    timeout: int = 8,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _fallback_insight(units, amount, billing_period)

    prompt = (
        f"Billing Period: {billing_period}\n"
        f"Units Consumed: {units}\n"
        f"Total Amount (INR): {amount:.2f}\n"
        "Provide a clear 2-line explanation of this electricity bill and 3 short, practical "
        "electricity-saving tips. Keep it concise."
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not text:
                return _fallback_insight(units, amount, billing_period)
            return {
                "source": "gemini",
                "summary": text,
                "saving_tips": [],
            }
    except Exception:
        return _fallback_insight(units, amount, billing_period)