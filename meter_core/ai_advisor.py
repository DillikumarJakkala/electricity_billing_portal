import os
from google import genai


def explain_bill_with_ai(
    customer_type: str,
    billing_period: str,
    units_consumed: float,
    total_amount: float,
    user_question: str = "",
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "AI Advisor is not configured: GEMINI_API_KEY environment variable is missing."

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are an electricity billing and energy-saving assistant for a residential billing portal.
Analyze this billing record:
- Customer / Meter Type: {customer_type}
- Billing Period: {billing_period}
- Units Consumed: {units_consumed} kWh
- Slab Rules: 8.75 per unit for 1-100 units; 10.75 per unit above 100 units
- Calculated Bill Amount: {total_amount}
- Resident Question: {user_question or "Explain my bill breakdown and share practical ways to reduce next month's bill."}

Give a clear, concise response with:
1. Bill and slab breakdown explanation
2. High-usage alert if consumption is elevated
3. 3 practical energy-saving tips tailored to this usage
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text or "No AI response generated."
    except Exception as e:
        return f"AI Advisor error: {str(e)}"
