# Medical Bill Auditor

An AI agent that reads a hospital bill, checks every line item against reference
pricing, flags overcharges and duplicate charges, and drafts a dispute letter —
the first wedge of a "patient-side fiduciary" that nobody in Indian healthcare
fintech currently builds (every BNPL, insurance, and savings platform processes
the bill; none of them audit it).

Runs entirely on **Google Gemini's free API tier** — no credit card, no paid API.

## How it works

```
bill (PDF/JPG/PNG)
      │
      ▼
bill_extractor.py        →  Gemini (vision) extracts every line item as structured JSON
      │
      ▼
overcharge_detector.py   →  local logic: fuzzy-matches items against data/benchmark_rates.json,
      │                      flags duplicates + amounts above benchmark (no API call, free)
      ▼
letter_generator.py      →  Gemini (text) drafts a dispute letter from the flagged items
      │
      ▼
app.py                   →  Streamlit UI wiring it all together
```

## Setup

1. **Get a free Gemini API key** — go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey),
   sign in with a Google account, click "Create API key." No credit card required.

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your key**
   ```bash
   cp .env.example .env
   # then edit .env and paste your key:
   # GEMINI_API_KEY=your_key_here
   ```

4. **Run it**
   ```bash
   streamlit run app.py
   ```
   Opens at `http://localhost:8501`. Upload a bill, click "Analyze bill."

   You can also run the extractor standalone for testing:
   ```bash
   python bill_extractor.py path/to/bill.jpg
   ```

## Free tier limits (mid-2026)

| Model | Requests/min | Requests/day | Good for |
|---|---|---|---|
| `gemini-2.5-flash` (default) | 10 | 250 | best quality/speed balance |
| `gemini-2.5-flash-lite` | 15 | 1,000 | swap in if you hit rate limits |

Change the model by passing `model="gemini-2.5-flash-lite"` to `extract_bill_items()`
and `generate_dispute_letter()`, or edit the default in each file. No billing = no charge,
just a 429 error if you exceed the daily cap — the code doesn't retry automatically, so
add backoff if you're demoing this live to a lot of people at once.

## Important caveats (read before using on real bills)

- **`data/benchmark_rates.json` is starter/illustrative data**, not verified official
  pricing. Swap it for the [official CGHS rate list](https://cghs.gov.in) (or another
  verified, current benchmark) before trusting the flagged amounts for real decisions.
- **Free-tier privacy**: Google may use free-tier inputs to improve its models. Don't
  upload bills with real patient names/IDs on the free tier — redact identifying info,
  or move to a paid tier / Vertex AI if you're handling real patient data (this is the
  same DPDP Act 2023 gap every competitor in this space currently ignores — don't repeat it).
- The overcharge detector only flags items it can fuzzy-match to the benchmark list.
  Unmatched line items aren't flagged as suspicious — they're just unverifiable with
  the current reference data. Expand `benchmark_rates.json` to cover more procedures
  for better coverage.

## Project structure

```
medical-bill-auditor/
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   └── benchmark_rates.json   # reference price list (swap for real CGHS data)
├── bill_extractor.py          # Gemini vision → structured line items
├── overcharge_detector.py     # local matching + flagging logic
├── letter_generator.py        # Gemini text → dispute letter
└── app.py                     # Streamlit UI
```

## Roadmap (if you want to extend this)

- **Better benchmark coverage**: scrape/parse the full CGHS PDF into `benchmark_rates.json`
  instead of the ~30 starter entries here.
- **Multi-bill tracking**: SQLite table of bills over time, per patient.
- **Pre-treatment mode**: compare a cost *estimate* against benchmarks before the patient
  commits, not just after the bill arrives.
- **Insurance claim letter mode**: same flagging logic, different letter template, aimed
  at an insurer instead of a hospital billing desk.
- **WhatsApp interface**: distribution matters more than features in this market —
  most of the target users are not going to open a Streamlit app.
