"""
overcharge_detector.py
Compares extracted bill line items against a benchmark price list and flags
items that look overcharged, duplicated, or otherwise worth questioning.

This runs entirely locally (no API calls) so it doesn't cost any free-tier quota.
"""

import json
import difflib
from dataclasses import dataclass
from typing import List, Optional, Dict

from bill_extractor import ExtractedBill


@dataclass
class Flag:
    line_item: str
    billed_amount: float
    benchmark_amount: Optional[float]
    excess_amount: Optional[float]
    reason: str
    severity: str  # "high" | "medium"


def load_benchmark(path: str = "data/benchmark_rates.json") -> List[dict]:
    with open(path, "r") as f:
        return json.load(f)["rates"]


def _match_benchmark(description: str, benchmark: List[dict], cutoff: float = 0.55) -> Optional[dict]:
    """Fuzzy-matches a billed item description against the benchmark name/aliases."""
    description_lower = description.strip().lower()

    # 1. exact match against name or any alias
    for entry in benchmark:
        candidates = [entry["name"].lower()] + [a.lower() for a in entry.get("aliases", [])]
        if description_lower in candidates:
            return entry

    # 2. fuzzy match
    name_to_entry: Dict[str, dict] = {}
    all_names = []
    for entry in benchmark:
        for name in [entry["name"]] + entry.get("aliases", []):
            name_to_entry[name.lower()] = entry
            all_names.append(name.lower())

    matches = difflib.get_close_matches(description_lower, all_names, n=1, cutoff=cutoff)
    if matches:
        return name_to_entry[matches[0]]
    return None


def detect_overcharges(bill: ExtractedBill, benchmark_path: str = "data/benchmark_rates.json") -> List[Flag]:
    benchmark = load_benchmark(benchmark_path)
    flags: List[Flag] = []
    seen: Dict[str, int] = {}

    for item in bill.line_items:
        # --- duplicate-line check ---
        key = item.description.strip().lower()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            flags.append(Flag(
                line_item=item.description,
                billed_amount=item.total_amount,
                benchmark_amount=None,
                excess_amount=item.total_amount,
                reason=f"Appears {seen[key]} times on the bill — check for duplicate billing.",
                severity="high",
            ))

        # --- benchmark price check ---
        match = _match_benchmark(item.description, benchmark)
        if match:
            tolerance = match.get("tolerance_pct", 25) / 100
            ceiling = match["benchmark_rate_inr"] * (1 + tolerance)
            if item.total_amount > ceiling:
                excess = round(item.total_amount - match["benchmark_rate_inr"], 2)
                flags.append(Flag(
                    line_item=item.description,
                    billed_amount=item.total_amount,
                    benchmark_amount=match["benchmark_rate_inr"],
                    excess_amount=excess,
                    reason=(
                        f"Billed \u20b9{item.total_amount:,.0f} vs. a reference rate of "
                        f"\u20b9{match['benchmark_rate_inr']:,.0f} for '{match['name']}' "
                        f"(category: {match['category']})."
                    ),
                    severity="high" if item.total_amount > match["benchmark_rate_inr"] * 2 else "medium",
                ))
        # unmatched items aren't flagged — there's just no benchmark to compare against yet

    return flags


def summarize_flags(flags: List[Flag]) -> dict:
    total_excess = sum(f.excess_amount or 0 for f in flags if f.excess_amount)
    return {
        "total_flags": len(flags),
        "high_severity": sum(1 for f in flags if f.severity == "high"),
        "medium_severity": sum(1 for f in flags if f.severity == "medium"),
        "estimated_excess_inr": round(total_excess, 2),
    }


if __name__ == "__main__":
    # quick local self-test with mock data, no API call needed
    from bill_extractor import BillLineItem

    mock_bill = ExtractedBill(
        hospital_name="Test Hospital",
        bill_date="2026-06-01",
        bill_number="TH-1029",
        grand_total=15400,
        line_items=[
            BillLineItem(description="CBC", category="Diagnostics", quantity=1, unit_price=900, total_amount=900),
            BillLineItem(description="IV Cannula", category="Consumables", quantity=1, unit_price=300, total_amount=300),
            BillLineItem(description="IV Cannula", category="Consumables", quantity=1, unit_price=300, total_amount=300),
            BillLineItem(description="General Ward Room Rent", category="Room Rent", quantity=1, unit_price=2900, total_amount=2900),
        ],
    )
    result = detect_overcharges(mock_bill)
    for f in result:
        print(f"[{f.severity.upper()}] {f.line_item}: {f.reason}")
    print(summarize_flags(result))
