"""
app.py
Streamlit front-end for the Medical Bill Auditor agent.

Run with:  streamlit run app.py
"""

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from bill_extractor import extract_bill_items
from overcharge_detector import detect_overcharges, summarize_flags
from letter_generator import generate_dispute_letter

load_dotenv()

st.set_page_config(page_title="Medical Bill Auditor", page_icon="🧾", layout="wide")
st.title("🧾 Medical Bill Auditor")
st.caption(
    "Upload a hospital bill. The agent extracts every line item, checks it against "
    "reference pricing, and flags possible overcharges or duplicate charges."
)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.warning(
        "No GEMINI_API_KEY found. Create a `.env` file with your free key "
        "(see README) before uploading a bill."
    )

uploaded_file = st.file_uploader("Upload bill (PDF, JPG, or PNG)", type=["pdf", "jpg", "jpeg", "png"])

if uploaded_file and api_key:
    if st.button("Analyze bill", type="primary"):
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        with st.spinner("Reading and extracting line items..."):
            try:
                bill = extract_bill_items(tmp_path, api_key=api_key)
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.stop()

        with st.spinner("Checking line items against reference pricing..."):
            flags = detect_overcharges(bill)

        st.session_state["bill"] = bill
        st.session_state["flags"] = flags
        st.session_state.pop("letter", None)  # reset any previously generated letter

if "bill" in st.session_state:
    bill = st.session_state["bill"]
    flags = st.session_state.get("flags", [])
    summary = summarize_flags(flags)

    col1, col2, col3 = st.columns(3)
    col1.metric("Line items found", len(bill.line_items))
    col2.metric("Items flagged", summary["total_flags"])
    col3.metric("Estimated excess", f"\u20b9{summary['estimated_excess_inr']:,.0f}")

    st.subheader("Extracted line items")
    st.dataframe(
        [
            {
                "Description": item.description,
                "Category": item.category,
                "Qty": item.quantity,
                "Unit price (\u20b9)": item.unit_price,
                "Total (\u20b9)": item.total_amount,
            }
            for item in bill.line_items
        ],
        use_container_width=True,
    )

    if flags:
        st.subheader("\u26a0\ufe0f Flagged items")
        for f in flags:
            icon = "\U0001F534" if f.severity == "high" else "\U0001F7E1"
            st.markdown(f"{icon} **{f.line_item}** \u2014 \u20b9{f.billed_amount:,.0f}  \n{f.reason}")
    else:
        st.success("No overcharges detected against the reference price list.")

    st.divider()
    if st.button("Generate dispute letter"):
        with st.spinner("Drafting letter..."):
            st.session_state["letter"] = generate_dispute_letter(bill, flags, api_key=api_key)

    if "letter" in st.session_state:
        st.text_area("Dispute letter (editable)", st.session_state["letter"], height=400)
        st.download_button(
            "Download letter (.txt)",
            st.session_state["letter"],
            file_name="bill_dispute_letter.txt",
        )

st.divider()
st.caption(
    "\u26a0\ufe0f Reference prices in `data/benchmark_rates.json` are illustrative starter data, "
    "not verified official rates \u2014 swap in the official CGHS rate list (cghs.gov.in) before "
    "relying on this for real decisions. Also avoid uploading bills with real patient-identifying "
    "details on the free API tier, since Google may use free-tier inputs to improve its models."
)
