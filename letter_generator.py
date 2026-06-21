"""
letter_generator.py
Drafts a polite, factual bill-dispute / clarification letter using Gemini,
based on the flags produced by overcharge_detector.py.
"""

import os
from typing import List, Optional

from google import genai

from bill_extractor import ExtractedBill
from overcharge_detector import Flag


LETTER_PROMPT_TEMPLATE = """Draft a polite but firm letter to a hospital's billing department,
querying specific charges on an itemized bill. Use a professional, factual tone — no
accusations of fraud, just a clear, courteous request for itemized justification or correction.

Hospital: {hospital_name}
Bill number: {bill_number}
Bill date: {bill_date}
Grand total billed: \u20b9{grand_total}

Flagged items requiring clarification:
{flagged_items_text}

Structure the letter as:
1. A brief, polite opening referencing the bill number and date
2. A clearly itemized list of the specific charges being queried, with the billed amount
   and the reason for the query
3. A request for an itemized cost breakdown and, where applicable, a revised bill
4. A polite closing requesting a response within 7 working days

Keep it under 350 words. Do not invent any facts beyond what's given above.
"""


def _get_client(api_key: Optional[str] = None) -> genai.Client:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("No Gemini API key found. Add GEMINI_API_KEY to your .env file.")
    return genai.Client(api_key=key)


def generate_dispute_letter(
    bill: ExtractedBill,
    flags: List[Flag],
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
) -> str:
    client = _get_client(api_key)

    flagged_items_text = "\n".join(
        f"- {f.line_item}: billed \u20b9{f.billed_amount:,.0f} \u2014 {f.reason}"
        for f in flags
    ) or "No specific overcharges flagged \u2014 request a general itemized clarification."

    prompt = LETTER_PROMPT_TEMPLATE.format(
        hospital_name=bill.hospital_name or "[Hospital Name]",
        bill_number=bill.bill_number or "[Bill Number]",
        bill_date=bill.bill_date or "[Bill Date]",
        grand_total=f"{bill.grand_total:,.0f}",
        flagged_items_text=flagged_items_text,
    )

    response = client.models.generate_content(model=model, contents=prompt)
    return response.text
