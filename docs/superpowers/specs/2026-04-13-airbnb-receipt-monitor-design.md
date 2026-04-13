# AirBnB Receipt Monitor — Design Spec
**Date:** 2026-04-13  
**Property:** Rice Drive LLC — Tempe Townhome, Arizona  
**Owner:** Jeff Berry (berrystaysllc@gmail.com)

---

## Goal

Automate the monthly AirBnB tax filing prep. When Rental Advisor sends a QuickBooks sales receipt PDF, the pipeline detects it, extracts the booking data, and emails a formatted Avalara-ready summary. Jeff enters the numbers into Avalara manually. Once the data has proven reliable over several months, Avalara form-filling will be automated.

---

## Project Structure

```
airbnb_receipt_monitor/
├── .env                    # secrets (never committed)
├── .gitignore
├── config.py               # all constants in one place
├── src/
│   ├── gmail_monitor.py    # find + download new receipt emails via Gmail API
│   ├── pdf_extractor.py    # parse PDF → structured booking data
│   ├── email_report.py     # format + send summary email via Gmail API
│   └── run_pipeline.py     # orchestrator (what launchd calls)
├── credentials/            # OAuth token — gitignored
│   └── token.json
├── launchd/
│   └── com.jeffberry.airbnb-monitor.plist
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-13-airbnb-receipt-monitor-design.md
```

---

## Configuration (`config.py`)

All constants live here. Nothing is hardcoded in module files.

```python
RECEIPTS_DIR     = "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/"
SOURCE_EMAIL     = "Accounting@myrentaladvisor.com"
SUBJECT_KEYWORDS = ["Sales Receipt", "Tempe Townhome", "Owner Statement"]
GMAIL_ACCOUNT    = "berrystaysllc@gmail.com"
REPORT_TO        = "berrystaysllc@gmail.com"
AVALARA_PROPERTY = "167558 - Rice Drive LLC"
AIRBNB_TAX_PHRASE = "Taxes for this reservation already paid by Vendor"
LOG_FILE         = "~/Library/Logs/airbnb_monitor.log"
```

---

## Data Flow

```
launchd (12:00 PM, days 1–9 of each month)
    └── run_pipeline.py
            │
            ├── gmail_monitor.py
            │     • searches berrystaysllc@gmail.com for emails from
            │       Accounting@myrentaladvisor.com where subject
            │       contains "Sales Receipt" AND "Tempe Townhome" AND "Owner Statement"
            │     • skips any email whose PDF already has a .done sentinel
            │     • downloads PDF attachment → SalesReceipts/
            │     • returns list of new PDF paths
            │
            ├── pdf_extractor.py  (once per new PDF)
            │     • slices full text into per-booking blocks
            │       (bounded by ORB reference positions)
            │     • detects channel per block:
            │         AirBnB = AIRBNB_TAX_PHRASE found in block
            │         Direct = phrase absent
            │     • sums revenue per booking (all positive line items,
            │       excluding service fees, payments released, balance due)
            │     • derives tax_period from receipt date in PDF
            │     • returns: tax_period, bookings[], avalara_channels{}
            │
            ├── email_report.py
            │     • formats summary email (see Email Format below)
            │     • sends to berrystaysllc@gmail.com via Gmail API
            │     • subject derived from tax_period in the PDF
            │
            └── marks PDF as processed (.done sentinel file)

If no new PDFs found → exit silently, one line to log file, no email sent.
```

---

## Modules

### `gmail_monitor.py`
- Authenticates via OAuth2 (token stored at `credentials/token.json`, auto-refreshes)
- Searches Gmail for matching emails using Gmail API query syntax
- Downloads the PDF attachment to `RECEIPTS_DIR` with date prefix (e.g. `2026-03_Sales_Receipt_...pdf`)
- Uses `.done` sentinel files to skip already-processed PDFs
- Returns list of new PDF file paths

### `pdf_extractor.py`
- Uses `pdfplumber` to extract text
- Slices text into per-booking blocks bounded by ORB reference positions — prevents AirBnB tax phrase from one booking bleeding into an adjacent booking's detection
- Revenue = sum of all positive line items per booking (includes pet fees, extra guest fees, etc.)
- Excludes: RA Service Fee lines, Payment Released, Balance Due, Tax Disclaimer
- Returns structured dict:
  ```python
  {
    "tax_period": "2026-02",          # YYYY-MM, derived from receipt date
    "bookings": [
      {
        "ref": "ORB15923639",
        "channel": "airbnb",          # or "direct"
        "check_in": "2026-01-03",
        "check_out": "2026-02-02",
        "nights": 30,
        "revenue": 3425.85
      }
    ],
    "avalara_channels": {
      "airbnb": {"nights": 37, "revenue": 4392.88},
      "direct": {"nights": 15, "revenue": 3166.58}
    },
    "warnings": []
  }
  ```

### `email_report.py`
- Composes a plain-text email using extracted data
- Subject: `AirBnB Tax Summary — {Month} {Year}` (e.g. `AirBnB Tax Summary — February 2026`)
- Month/Year derived from `tax_period` in extracted data — always matches the receipt, not the run date
- Sends via Gmail API using the same OAuth credentials

### `run_pipeline.py`
- Entry point called by launchd
- Calls `gmail_monitor` → for each new PDF: `pdf_extractor` → `email_report` → write `.done`
- Logs every run (success or failure) to `~/Library/Logs/airbnb_monitor.log`
- On hard failure: logs error and sends a short failure notification email to `berrystaysllc@gmail.com`

---

## Email Format

```
Subject: AirBnB Tax Summary — February 2026

Tax Period  : February 2026
Property    : 167558 - Rice Drive LLC

── BOOKINGS ────────────────────────────────────────
Stay #1  [AIRBNB]
  Check-in   : 2026-01-03
  Check-out  : 2026-02-02
  Nights     : 30
  Revenue    : $3,425.85

Stay #2  [DIRECT]
  Check-in   : 2026-02-10
  Check-out  : 2026-02-25
  Nights     : 15
  Revenue    : $3,166.58

── AVALARA ENTRY ───────────────────────────────────
  AirBnB  →  37 nights  /  $4,392.88   (leave "Revenue Includes Tax" UNCHECKED)
  Direct  →  15 nights  /  $3,166.58   (CHECK "Revenue Includes Tax")
  VRBO    →   0 nights  /      $0.00

── WARNINGS ────────────────────────────────────────
  (none)
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| No new PDFs found | Exit silently; one log line written; no email sent |
| Extraction warnings (partial data) | Email sent with warnings section prominently displayed |
| Hard failure (API error, corrupt PDF) | Error logged; short failure notification emailed to berrystaysllc@gmail.com |

---

## Dependencies

```
pdfplumber                  # PDF text extraction
google-api-python-client    # Gmail API
google-auth-oauthlib        # OAuth2 flow
google-auth-httplib2        # HTTP transport
```

Virtual environment: `/Users/jeffberry/projects/airbnb_receipt_monitor/.venv/`

No poppler, no image processing libraries.

---

## Scheduling

**launchd plist:** `com.jeffberry.airbnb-monitor.plist`  
**Schedule:** 12:00 PM, days 1–9 of every month (`0 12 1-9 * *`)  
**Log:** `~/Library/Logs/airbnb_monitor.log`

Email is only sent on the day a new unprocessed PDF is found — not on every run.

---

## Gmail OAuth Setup (One-Time)

1. Create a Google Cloud project and enable the Gmail API
2. Create OAuth 2.0 credentials (Desktop app type), download `credentials.json`
3. Place `credentials.json` in project root (gitignored)
4. Run the auth flow once: `python src/run_pipeline.py --auth`
5. Browser opens, Jeff logs into berrystaysllc@gmail.com, approves access
6. Token saved to `credentials/token.json` — auto-refreshes on all future runs

---

## Future: Avalara Automation

When Jeff is confident in the data accuracy, a fifth module (`avalara_filer.py`) will be added to `run_pipeline.py`. It will use browser automation to open the Avalara form, pre-fill the numbers from the extracted JSON, take a screenshot, and wait for explicit approval before submitting. The email flow can remain as a confirmation receipt. No other modules need to change.

---

## Key Design Decisions

- **Per-booking text block slicing** — ORB reference boundaries prevent AirBnB channel detection from bleeding between adjacent bookings
- **Revenue = all positive line items** — Avalara expects total rental revenue including pet fees, extra guest fees, etc. Not just gross rent
- **Sentinel `.done` files** — prevent reprocessing if the pipeline runs again before the next receipt arrives
- **Single config file** — all magic strings in `config.py`; no hardcoded values in module files
- **Same OAuth credentials for read and send** — Gmail API scopes cover both; one auth flow, one token
