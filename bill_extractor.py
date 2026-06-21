"""
bill_extractor.py
Extracts structured line-item data from a hospital bill (image or PDF)
using Google's Gemini API (free tier, no credit card required).
"""

import os
import json
from typing import List, Optional

from pydantic import BaseModel
from google import genai
from google.genai import types


class BillLineItem(BaseModel):
    description: str
    category: str  # "Consultation" | "Diagnostics" | "Room Rent" | "Surgery/Procedure" |
    #                "Pharmacy" | "Consumables" | "Nursing/ICU" | "Other"
    quantity: float
    unit_price: float
    total_amount: float


class ExtractedBill(BaseModel):
    hospital_name: Optional[str] = None
    bill_date: Optional[str] = None
    bill_number: Optional[str] = None
    line_items: List[BillLineItem]
    grand_total: float


EXTRACTION_PROMPT = """You are a medical billing data-extraction assistant.

Read the attached hospital bill carefully and extract EVERY individual line item exactly
as billed. Do not skip small consumable charges, do not merge separate line items into
one, and do not invent items that aren't actually on the bill.

For each line item provide:
- description: the item/service exactly as written on the bill
- category: one of "Consultation", "Diagnostics", "Room Rent", "Surgery/Procedure",
  "Pharmacy", "Consumables", "Nursing/ICU", "Other"
- quantity: numeric quantity (use 1 if not specified)
- unit_price: price per unit in INR
- total_amount: total amount charged for that line in INR

Also extract the hospital name, bill date, bill number (if present), and the grand total.
If a field genuinely isn't on the bill, leave it null — do not guess or invent it.
"""


def _get_client(api_key: Optional[str] = None) -> genai.Client:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "No Gemini API key found. Add GEMINI_API_KEY to your .env file "
            "(get a free key at https://aistudio.google.com/apikey)."
        )
    return genai.Client(api_key=key)


def extract_bill_items(
    file_path: str,
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
) -> ExtractedBill:
    """
    Extracts structured line items from a bill image or PDF.

    Args:
        file_path: path to a .jpg / .jpeg / .png / .webp / .pdf bill
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var)
        model: Gemini model name. Free tier defaults:
               gemini-2.5-flash      -> 10 RPM / 250 req per day  (best quality/speed balance)
               gemini-2.5-flash-lite -> 15 RPM / 1000 req per day (use if you hit rate limits)

    Returns:
        ExtractedBill with structured, itemized line items.
    """
    client = _get_client(api_key)
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        uploaded = client.files.upload(file=file_path)
        contents = [uploaded, EXTRACTION_PROMPT]
    elif ext in (".jpg", ".jpeg", ".png", ".webp"):
        from PIL import Image
        image = Image.open(file_path)
        contents = [image, EXTRACTION_PROMPT]
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, JPG, PNG, or WEBP.")

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedBill,
            temperature=0.1,
        ),
    )

    return ExtractedBill.model_validate_json(response.text)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python bill_extractor.py <path_to_bill>")
        sys.exit(1)

    result = extract_bill_items(sys.argv[1])
    print(json.dumps(result.model_dump(), indent=2))
