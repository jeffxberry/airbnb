# AirBnB Receipt Monitor

Automates monthly short-term rental tax filing prep. When your property manager sends a QuickBooks sales receipt PDF, this pipeline detects it, extracts the booking data, and emails you a formatted summary with the exact numbers to enter into Avalara MyLodgeTax.

## How It Works

```
Gmail inbox (new receipt email)
    ↓
Pipeline downloads the PDF attachment
    ↓
PDF is parsed — bookings split by channel (AirBnB vs. Direct)
    ↓
Summary email sent with Avalara-ready numbers
    ↓
You log into Avalara and enter the numbers manually
```

### Execution Methods

**Claude Code Routine (primary)** — Runs automatically in the cloud on days 1–9 of each month at noon. Uses a hybrid approach:
- Gmail MCP tools search for and read receipt emails
- Python scripts download PDF attachments and extract booking data
- Gmail MCP sends the formatted report email
- Processed receipts are labeled in Gmail to prevent reprocessing

**macOS launchd (legacy)** — A local scheduler that runs the Python pipeline directly. Requires the Mac to be online. The plist is included in `launchd/` but is not loaded by default.

Both methods use the same Gmail label (`airbnb-receipt-processed`) for deduplication, so they can run side-by-side without processing the same receipt twice.

## Project Structure

```
airbnb_receipt_monitor/
├── config.py                  # Loads settings from .env
├── .env                       # Your personal settings (never committed)
├── .env.example               # Template — copy this to .env and fill in
├── src/
│   ├── gmail_monitor.py       # Finds and downloads receipt emails via Gmail API
│   ├── pdf_extractor.py       # Parses the PDF into structured booking data
│   ├── email_report.py        # Formats and sends the summary email
│   ├── run_pipeline.py        # Entry point for local execution
│   ├── routine_pdf_download.py  # CLI script — downloads PDF attachment by message ID
│   └── routine_extract.py     # CLI script — extracts booking data from PDF as JSON
├── tests/                     # Automated tests
├── launchd/
│   └── com.jeffberry.airbnb-monitor.plist  # macOS scheduler (legacy)
└── credentials/               # OAuth token lives here (never committed)
```

## Prerequisites

- Python 3.12
- A Gmail account that receives the property manager's receipt emails
- A [Google Cloud project](https://console.cloud.google.com/) with the Gmail API enabled

## Setup

### 1. Clone and install

```bash
git clone https://github.com/jeffxberry/airbnb.git
cd airbnb
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
RECEIPTS_DIR=/path/to/your/SalesReceipts/folder/
SOURCE_EMAIL=email@yourpropertymanager.com
SUBJECT_KEYWORDS=Sales Receipt,Your Property Name,Owner Statement
GMAIL_ACCOUNT=your-gmail@gmail.com
REPORT_TO=where-to-send-summary@gmail.com
AVALARA_PROPERTY=123456 - Your LLC Name
```

### 3. Set up Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. Enable the **Gmail API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
4. Set up the OAuth consent screen (External), add your Gmail as a test user
5. Application type: **Desktop app** — download the JSON file
6. Place it at `credentials/credentials.json`

### 4. Authenticate

```bash
.venv/bin/python src/run_pipeline.py --auth
```

A browser window opens. Log in with your Gmail account and approve access. The token is saved to `credentials/token.json` and auto-refreshes on future runs.

### 5. Run manually to test

```bash
.venv/bin/python src/run_pipeline.py
```

Check the log:
```bash
tail -30 ~/Library/Logs/airbnb_monitor.log
```

### 6. Set up the Claude Code Routine

1. Go to [claude.ai/code/routines](https://claude.ai/code/routines) and create a new Routine
2. Connect your GitHub repo and Gmail account as a connector
3. Set the schedule to run days 1–9 of each month at noon
4. Add environment variables: `GMAIL_TOKEN_JSON` (contents of `credentials/token.json`), `RECEIPTS_DIR`, `SOURCE_EMAIL`, `SUBJECT_KEYWORDS`, `GMAIL_ACCOUNT`, `REPORT_TO`, `AVALARA_PROPERTY`, and `CLAUDE_CODE_REMOTE=true`
5. Set the setup script to `pip install -r requirements.txt`
6. Add the Routine prompt with instructions to search Gmail, download PDFs, extract data, and send the report

### 6b. Alternative: macOS launchd (local)

```bash
cp launchd/com.jeffberry.airbnb-monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jeffberry.airbnb-monitor.plist
```

Update the paths inside the plist file to match your machine before loading.

## What the Summary Email Looks Like

```
Tax Period  : March 2026
Property    : 123456 - Your LLC Name

── BOOKINGS ────────────────────────────────────────
Stay #1  [AIRBNB]
  Check-in   : 2026-02-10
  Check-out  : 2026-03-05
  Nights     : 23
  Revenue    : $2,841.00

Stay #2  [DIRECT]
  ...

── AVALARA ENTRY ───────────────────────────────────
  AirBnB  →  23 nights  /  $2,841.00   (leave "Revenue Includes Tax" UNCHECKED)
  Direct  →  15 nights  /  $1,950.00   (CHECK "Revenue Includes Tax")
  VRBO    →   0 nights  /       $0.00

── WARNINGS ────────────────────────────────────────
  (none)
```

The Avalara Entry section has the exact numbers and checkbox instructions for each row.

## How AirBnB vs. Direct Is Detected

QuickBooks receipts include the phrase *"Taxes for this reservation already paid by Vendor"* on AirBnB bookings (because AirBnB remits occupancy tax directly). The pipeline detects this phrase within each booking block to classify it. Direct bookings have no such phrase.

## Running Tests

```bash
.venv/bin/pytest tests/ -v
```

PDF extraction integration tests require a test receipt PDF at `tests/fixtures/test_receipt.pdf`. All other tests run without any external dependencies.

## Logs

When running locally, all runs are logged to:
```
~/Library/Logs/airbnb_monitor.log
```

When running via Claude Code Routine, output is captured in the Routine session log on claude.ai.

If the pipeline fails, a short error notification is sent to the `REPORT_TO` email address.
