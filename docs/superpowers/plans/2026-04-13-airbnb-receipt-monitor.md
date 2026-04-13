# AirBnB Receipt Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a scheduled Python pipeline that monitors berrystaysllc@gmail.com for Rental Advisor receipt emails, extracts booking data from the PDF, and emails a formatted Avalara-ready summary to berrystaysllc@gmail.com.

**Architecture:** Four focused modules (gmail_monitor, pdf_extractor, email_report, run_pipeline) orchestrated by a single entry point. launchd calls the entry point at noon on days 1–9 each month. Gmail API handles both reading and sending. Sentinel `.done` files prevent reprocessing. Email is only sent when a new unprocessed PDF is found.

**Tech Stack:** Python 3.12, pdfplumber, google-api-python-client, google-auth-oauthlib, google-auth-httplib2, launchd

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | All constants — paths, email addresses, keywords, Avalara property |
| `src/gmail_monitor.py` | OAuth credentials, Gmail search, PDF attachment download |
| `src/pdf_extractor.py` | PDF text extraction, booking block parsing, channel detection |
| `src/email_report.py` | Format summary text, build subject line, send via Gmail API |
| `src/run_pipeline.py` | Entry point — orchestrates all modules, logging, error handling |
| `tests/test_pdf_extractor.py` | Unit + integration tests for extractor |
| `tests/test_email_report.py` | Unit tests for formatter (no Gmail API needed) |
| `tests/test_gmail_monitor.py` | Unit test for query builder |
| `launchd/com.jeffberry.airbnb-monitor.plist` | macOS scheduler |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Exclude credentials, venv, .done files |
| `pytest.ini` | Set pythonpath so imports work in tests |

---

## Task 1: Project Scaffold

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `config.py`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `credentials/` directory (empty, gitignored)

- [ ] **Step 1: Create `.gitignore`**

```
.venv/
credentials/token.json
credentials.json
__pycache__/
*.pyc
.DS_Store
*.done
```

- [ ] **Step 2: Create `requirements.txt`**

```
pdfplumber>=0.11
google-api-python-client>=2.100
google-auth-oauthlib>=1.0
google-auth-httplib2>=0.2
pytest>=8.0
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
```

- [ ] **Step 4: Create `config.py`**

```python
RECEIPTS_DIR      = "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/"
SOURCE_EMAIL      = "Accounting@myrentaladvisor.com"
SUBJECT_KEYWORDS  = ["Sales Receipt", "Tempe Townhome", "Owner Statement"]
GMAIL_ACCOUNT     = "berrystaysllc@gmail.com"
REPORT_TO         = "berrystaysllc@gmail.com"
AVALARA_PROPERTY  = "167558 - Rice Drive LLC"
AIRBNB_TAX_PHRASE = "Taxes for this reservation already paid by Vendor"
```

- [ ] **Step 5: Create virtual environment and install dependencies**

Run:
```bash
cd /Users/jeffberry/projects/airbnb_receipt_monitor
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: packages install without errors.

- [ ] **Step 6: Create empty init files and credentials directory**

```bash
touch src/__init__.py tests/__init__.py
mkdir -p credentials
```

- [ ] **Step 7: Commit**

```bash
git init
git add .gitignore requirements.txt pytest.ini config.py src/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: PDF Extractor (TDD)

**Files:**
- Create: `tests/test_pdf_extractor.py`
- Create: `src/pdf_extractor.py`

The integration test uses the existing receipt PDF. Expected values are known from the February 2026 receipt.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pdf_extractor.py`:

```python
import pytest
from pathlib import Path
from src.pdf_extractor import extract, normalize_date, parse_money

PDF_PATH = "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/2026-03_Sales_Receipt_10879_from_Rental_Advisor.pdf"
PDF_EXISTS = Path(PDF_PATH).exists()


def test_normalize_date_slash_format():
    assert normalize_date("02/28/2026") == "2026-02-28"


def test_normalize_date_short_year():
    assert normalize_date("02/28/26") == "2026-02-28"


def test_normalize_date_already_normalized():
    assert normalize_date("2026-02-28") == "2026-02-28"


def test_parse_money_with_comma():
    assert parse_money("3,241.68") == 3241.68


def test_parse_money_with_dollar():
    assert parse_money("$1,234.56") == 1234.56


def test_parse_money_invalid():
    assert parse_money("N/A") is None


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_returns_required_keys():
    data = extract(PDF_PATH)
    assert "tax_period" in data
    assert "bookings" in data
    assert "avalara_channels" in data
    assert "warnings" in data


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_tax_period():
    data = extract(PDF_PATH)
    assert data["tax_period"] == "2026-02"


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_airbnb_totals():
    data = extract(PDF_PATH)
    ab = data["avalara_channels"]["airbnb"]
    assert ab["nights"] == 37
    assert ab["revenue"] == pytest.approx(4392.88, abs=0.01)


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_direct_totals():
    data = extract(PDF_PATH)
    di = data["avalara_channels"]["direct"]
    assert di["nights"] == 15
    assert di["revenue"] == pytest.approx(3166.58, abs=0.01)


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_no_warnings():
    data = extract(PDF_PATH)
    assert data["warnings"] == []


@pytest.mark.skipif(not PDF_EXISTS, reason="Test PDF not present")
def test_extract_bookings_have_channels():
    data = extract(PDF_PATH)
    for booking in data["bookings"]:
        assert booking["channel"] in ("airbnb", "direct")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_pdf_extractor.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `src.pdf_extractor`.

- [ ] **Step 3: Implement `src/pdf_extractor.py`**

```python
from __future__ import annotations
import re
import os
from datetime import datetime
import pdfplumber
from config import AIRBNB_TAX_PHRASE

BOOKING_REF_RE = re.compile(r'\b(ORB|BK|RES|CONF|INV)(\d+)\b', re.IGNORECASE)
EXCLUDE_LINE_RE = re.compile(
    r'service\s+fee|payment\s+released|balance\s+due|tax\s+disclaimer',
    re.IGNORECASE
)
_AIRBNB_RE = re.compile(re.escape(AIRBNB_TAX_PHRASE), re.IGNORECASE)


def normalize_date(raw: str) -> str:
    """Normalize a date string to YYYY-MM-DD. Returns raw string if no format matches."""
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return raw.strip()


def parse_money(s: str) -> float | None:
    """Convert a money string like '$1,234.56' to float. Returns None if unparseable."""
    try:
        return float(re.sub(r'[,$\s]', '', s))
    except (ValueError, TypeError):
        return None


def _parse_bookings(full_text: str) -> list[dict]:
    """
    Slice full PDF text into per-booking blocks bounded by ORB reference positions.
    This prevents the AirBnB tax phrase from one booking bleeding into an adjacent
    booking's channel detection.
    """
    seen: dict[str, int] = {}
    for m in BOOKING_REF_RE.finditer(full_text):
        ref = m.group(0).upper()
        if ref not in seen:
            seen[ref] = m.start()

    unique_orbs = sorted(seen.items(), key=lambda x: x[1])
    if not unique_orbs:
        return []

    bookings = []
    for i, (ref, pos) in enumerate(unique_orbs):
        next_pos = unique_orbs[i + 1][1] if i + 1 < len(unique_orbs) else len(full_text)
        block = full_text[pos:next_pos]

        channel = "airbnb" if _AIRBNB_RE.search(block) else "direct"

        # Date extraction — two strategies to handle PDFs where pdfplumber
        # renders amounts between the two dates on a single line.
        block_flat = ' '.join(block.split())
        check_in = check_out = None
        nights = None

        # Strategy A: "date to date" directly adjacent
        direct_m = re.search(
            r'(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})',
            block_flat
        )
        if direct_m:
            check_in = normalize_date(direct_m.group(1))
            check_out = normalize_date(direct_m.group(2))
        else:
            # Strategy B: first date = check-in, then look for "to <date>"
            # or the next distinct date in the block
            checkin_m = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', block_flat)
            if checkin_m:
                check_in = normalize_date(checkin_m.group(1))
                to_m = re.search(r'\bto\s+(\d{1,2}/\d{1,2}/\d{4})', block_flat)
                if to_m:
                    check_out = normalize_date(to_m.group(1))
                else:
                    all_dates = [
                        normalize_date(d)
                        for d in re.findall(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', block_flat)
                    ]
                    others = [d for d in all_dates if d != check_in]
                    if others:
                        check_out = others[0]

        if check_in and check_out:
            try:
                d1 = datetime.strptime(check_in, '%Y-%m-%d')
                d2 = datetime.strptime(check_out, '%Y-%m-%d')
                nights = (d2 - d1).days
            except Exception:
                pass

        # Revenue: sum all positive line items, skip fee/payment lines and negatives
        revenue = 0.0
        for line in block.splitlines():
            if EXCLUDE_LINE_RE.search(line):
                continue
            if re.search(r'-\s*[\d,]+\.\d{2}', line):
                continue
            amt_m = re.search(r'(?<!\d)([\d,]+\.\d{2})(?!\d)', line)
            if amt_m:
                amt = parse_money(amt_m.group(1))
                if amt and amt > 0:
                    revenue += amt

        bookings.append({
            'ref': ref,
            'channel': channel,
            'check_in': check_in,
            'check_out': check_out,
            'nights': nights,
            'revenue': round(revenue, 2),
        })

    return bookings


def extract(pdf_path: str) -> dict:
    """
    Extract booking data from a QuickBooks sales receipt PDF.

    Returns:
        {
            'source_file': str,
            'tax_period': str | None,   # YYYY-MM, derived from receipt date
            'bookings': list[dict],
            'avalara_channels': {
                'airbnb': {'revenue': float, 'nights': int},
                'direct': {'revenue': float, 'nights': int},
            },
            'warnings': list[str],
        }
    """
    result = {
        'source_file': os.path.basename(pdf_path),
        'tax_period': None,
        'bookings': [],
        'avalara_channels': {
            'airbnb': {'revenue': 0.0, 'nights': 0},
            'direct': {'revenue': 0.0, 'nights': 0},
        },
        'warnings': [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [page.extract_text() or '' for page in pdf.pages]
    full_text = '\n'.join(pages_text)

    bookings = _parse_bookings(full_text)
    result['bookings'] = bookings

    for b in bookings:
        ch = b['channel']
        result['avalara_channels'][ch]['revenue'] = round(
            result['avalara_channels'][ch]['revenue'] + b['revenue'], 2
        )
        result['avalara_channels'][ch]['nights'] += (b['nights'] or 0)

    # Tax period: prefer explicit receipt date label; fall back to latest check-out
    date_match = re.search(
        r'(?:Date|Invoice Date|Sale Date)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
        full_text, re.IGNORECASE
    )
    if date_match:
        result['tax_period'] = normalize_date(date_match.group(1))[:7]
    elif bookings:
        dates = [b['check_out'] for b in bookings if b.get('check_out')]
        if dates:
            result['tax_period'] = max(dates)[:7]

    if not bookings:
        result['warnings'].append('No booking blocks detected — verify PDF format.')

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_pdf_extractor.py -v
```

Expected: all tests PASS. Integration tests run if PDF exists and show AirBnB 37 nights / $4,392.88 and Direct 15 nights / $3,166.58.

- [ ] **Step 5: Commit**

```bash
git add src/pdf_extractor.py tests/test_pdf_extractor.py
git commit -m "feat: PDF extractor with per-booking block parsing"
```

---

## Task 3: Email Report

**Files:**
- Create: `tests/test_email_report.py`
- Create: `src/email_report.py`

Unit tests cover formatting only — no Gmail API required. The send functions are implemented but tested via integration in Task 6.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_email_report.py`:

```python
from src.email_report import format_report, build_subject, _month_label

SAMPLE_DATA = {
    'tax_period': '2026-02',
    'bookings': [
        {
            'channel': 'airbnb',
            'check_in': '2026-01-03',
            'check_out': '2026-02-02',
            'nights': 30,
            'revenue': 3425.85,
        },
        {
            'channel': 'direct',
            'check_in': '2026-02-10',
            'check_out': '2026-02-25',
            'nights': 15,
            'revenue': 3166.58,
        },
    ],
    'avalara_channels': {
        'airbnb': {'nights': 37, 'revenue': 4392.88},
        'direct': {'nights': 15, 'revenue': 3166.58},
    },
    'warnings': [],
}


def test_month_label_february():
    assert _month_label('2026-02') == 'February 2026'


def test_month_label_december():
    assert _month_label('2026-12') == 'December 2026'


def test_build_subject():
    assert build_subject(SAMPLE_DATA) == 'AirBnB Tax Summary \u2014 February 2026'


def test_format_report_has_avalara_section():
    assert 'AVALARA ENTRY' in format_report(SAMPLE_DATA)


def test_format_report_airbnb_nights_and_revenue():
    report = format_report(SAMPLE_DATA)
    assert '37' in report
    assert '$4,392.88' in report


def test_format_report_direct_nights_and_revenue():
    report = format_report(SAMPLE_DATA)
    assert '15' in report
    assert '$3,166.58' in report


def test_format_report_checkbox_reminders():
    report = format_report(SAMPLE_DATA)
    assert 'UNCHECKED' in report
    assert 'CHECK "Revenue Includes Tax"' in report


def test_format_report_no_warnings():
    assert '(none)' in format_report(SAMPLE_DATA)


def test_format_report_with_warnings():
    data = {**SAMPLE_DATA, 'warnings': ['Could not detect booking block']}
    assert 'Could not detect booking block' in format_report(data)


def test_format_report_has_property():
    assert '167558 - Rice Drive LLC' in format_report(SAMPLE_DATA)


def test_format_report_has_tax_period():
    assert 'February 2026' in format_report(SAMPLE_DATA)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_email_report.py -v
```

Expected: `ImportError` for `src.email_report`.

- [ ] **Step 3: Implement `src/email_report.py`**

```python
from __future__ import annotations
import base64
from datetime import datetime
from email.mime.text import MIMEText
from config import REPORT_TO, GMAIL_ACCOUNT, AVALARA_PROPERTY


def _month_label(tax_period: str) -> str:
    """Convert '2026-02' to 'February 2026'."""
    try:
        return datetime.strptime(tax_period, '%Y-%m').strftime('%B %Y')
    except Exception:
        return tax_period


def _fmt_money(val: float | None) -> str:
    if val is None:
        return 'UNKNOWN'
    return f'${val:,.2f}'


def build_subject(data: dict) -> str:
    month = _month_label(data.get('tax_period', 'Unknown'))
    return f'AirBnB Tax Summary \u2014 {month}'


def format_report(data: dict) -> str:
    month = _month_label(data.get('tax_period', ''))
    ch = data.get('avalara_channels', {})
    ab = ch.get('airbnb', {'revenue': 0.0, 'nights': 0})
    di = ch.get('direct', {'revenue': 0.0, 'nights': 0})

    lines = [
        f'Tax Period  : {month}',
        f'Property    : {AVALARA_PROPERTY}',
        '',
        '\u2500\u2500 BOOKINGS \u2500' * 4,
    ]

    for i, b in enumerate(data.get('bookings', []), 1):
        lines += [
            f"Stay #{i}  [{b['channel'].upper()}]",
            f"  Check-in   : {b.get('check_in', 'UNKNOWN')}",
            f"  Check-out  : {b.get('check_out', 'UNKNOWN')}",
            f"  Nights     : {b.get('nights', 'UNKNOWN')}",
            f"  Revenue    : {_fmt_money(b.get('revenue'))}",
            '',
        ]

    if not data.get('bookings'):
        lines += ['  (No bookings detected \u2014 see warnings below)', '']

    lines += [
        '\u2500\u2500 AVALARA ENTRY \u2500' * 3,
        f'  AirBnB  \u2192  {ab["nights"]:2d} nights  /  {_fmt_money(ab["revenue"])}'
        f'   (leave "Revenue Includes Tax" UNCHECKED)',
        f'  Direct  \u2192  {di["nights"]:2d} nights  /  {_fmt_money(di["revenue"])}'
        f'   (CHECK "Revenue Includes Tax")',
        f'  VRBO    \u2192   0 nights  /       $0.00',
        '',
        '\u2500\u2500 WARNINGS \u2500' * 4,
    ]

    warnings = data.get('warnings', [])
    if warnings:
        lines += [f'  ! {w}' for w in warnings]
    else:
        lines.append('  (none)')

    return '\n'.join(lines)


def send_report(service, data: dict) -> None:
    """Send the formatted Avalara summary email via Gmail API."""
    body = format_report(data)
    subject = build_subject(data)
    msg = MIMEText(body)
    msg['to'] = REPORT_TO
    msg['from'] = GMAIL_ACCOUNT
    msg['subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()


def send_failure_notice(service, error_msg: str) -> None:
    """Send a short failure notification email."""
    msg = MIMEText(f'AirBnB receipt monitor failed with error:\n\n{error_msg}')
    msg['to'] = REPORT_TO
    msg['from'] = GMAIL_ACCOUNT
    msg['subject'] = 'AirBnB Monitor \u2014 Error'
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_email_report.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/email_report.py tests/test_email_report.py
git commit -m "feat: email report formatter and sender"
```

---

## Task 4: Gmail OAuth Setup (One-Time, User-Driven)

This task requires Jeff to interact with Google Cloud Console. No code is written here.

- [ ] **Step 1: Create a Google Cloud project**

1. Go to https://console.cloud.google.com/
2. Click "Select a project" → "New Project"
3. Name it `airbnb-receipt-monitor`, click Create

- [ ] **Step 2: Enable the Gmail API**

1. In the project, go to "APIs & Services" → "Enable APIs and Services"
2. Search for "Gmail API", click it, click "Enable"

- [ ] **Step 3: Create OAuth credentials**

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted to configure consent screen: choose "External", fill in app name (`AirBnB Monitor`), add your email as both developer and test user, save
4. Application type: **Desktop app**
5. Name: `airbnb-monitor`
6. Click Create, then **Download JSON**

- [ ] **Step 4: Place credentials file**

Move the downloaded file to the project root and rename it:
```bash
mv ~/Downloads/client_secret_*.json \
  /Users/jeffberry/projects/airbnb_receipt_monitor/credentials.json
```

- [ ] **Step 5: Verify file is gitignored**

```bash
git status
```

Expected: `credentials.json` does NOT appear in the output (it is gitignored).

---

## Task 5: Gmail Monitor

**Files:**
- Create: `tests/test_gmail_monitor.py`
- Create: `src/gmail_monitor.py`

- [ ] **Step 1: Write the query builder test**

Create `tests/test_gmail_monitor.py`:

```python
from src.gmail_monitor import _build_query
from config import SUBJECT_KEYWORDS


def test_build_query_contains_all_keywords():
    query = _build_query()
    for kw in SUBJECT_KEYWORDS:
        assert kw in query


def test_build_query_uses_subject_prefix():
    query = _build_query()
    assert query.startswith('subject:')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_gmail_monitor.py -v
```

Expected: `ImportError` for `src.gmail_monitor`.

- [ ] **Step 3: Implement `src/gmail_monitor.py`**

```python
from __future__ import annotations
import base64
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import SUBJECT_KEYWORDS, RECEIPTS_DIR

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]

_PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = _PROJECT_ROOT / 'credentials.json'
TOKEN_FILE = _PROJECT_ROOT / 'credentials' / 'token.json'

log = logging.getLogger(__name__)


def get_credentials() -> Credentials:
    """Load OAuth token from disk, refreshing if expired. Runs browser flow if no token exists."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def build_service():
    """Return an authenticated Gmail API service object."""
    return build('gmail', 'v1', credentials=get_credentials())


def _build_query() -> str:
    """Build Gmail search query requiring all subject keywords."""
    return ' '.join(f'subject:"{kw}"' for kw in SUBJECT_KEYWORDS)


def _get_pdf_attachment(service, msg_id: str) -> tuple[str, bytes] | None:
    """
    Return (filename, raw_bytes) for the first PDF attachment in the message.
    Returns None if no PDF attachment is found.
    """
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    parts = msg.get('payload', {}).get('parts', [])
    for part in parts:
        filename = part.get('filename', '')
        mime = part.get('mimeType', '')
        if filename.lower().endswith('.pdf') or mime == 'application/pdf':
            att_id = part.get('body', {}).get('attachmentId')
            if att_id:
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id
                ).execute()
                data = base64.urlsafe_b64decode(att['data'])
                return filename, data
    return None


def fetch_new_receipts(service) -> list[str]:
    """
    Search Gmail for matching receipt emails and download any unprocessed PDFs.

    Skips emails whose PDF already has a .done sentinel file.
    Returns list of absolute paths to newly downloaded (or pre-existing unprocessed) PDFs.
    """
    query = _build_query()
    log.info(f'Gmail search: {query}')

    result = service.users().messages().list(userId='me', q=query).execute()
    messages = result.get('messages', [])

    if not messages:
        log.info('No matching emails found.')
        return []

    receipts_dir = Path(RECEIPTS_DIR)
    new_pdfs: list[str] = []

    for msg_meta in messages:
        attachment = _get_pdf_attachment(service, msg_meta['id'])
        if not attachment:
            continue

        filename, data = attachment
        dest_path = receipts_dir / filename
        done_path = receipts_dir / (Path(filename).stem + '.done')

        if done_path.exists():
            log.info(f'Already processed: {filename}')
            continue

        if not dest_path.exists():
            dest_path.write_bytes(data)
            log.info(f'Downloaded: {filename}')
        else:
            log.info(f'PDF exists, not yet processed: {filename}')

        new_pdfs.append(str(dest_path))

    return new_pdfs
```

- [ ] **Step 4: Run the query builder tests**

```bash
.venv/bin/pytest tests/test_gmail_monitor.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Run the one-time auth flow**

```bash
.venv/bin/python src/run_pipeline.py --auth
```

Note: `run_pipeline.py` does not exist yet. Run this after Task 6.

- [ ] **Step 6: Commit**

```bash
git add src/gmail_monitor.py tests/test_gmail_monitor.py
git commit -m "feat: Gmail monitor with OAuth and PDF download"
```

---

## Task 6: Orchestrator

**Files:**
- Create: `src/run_pipeline.py`

- [ ] **Step 1: Implement `src/run_pipeline.py`**

```python
from __future__ import annotations
import sys
import logging
from pathlib import Path

# Ensure project root is in sys.path when called by launchd
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gmail_monitor import build_service, fetch_new_receipts, get_credentials
from src.pdf_extractor import extract
from src.email_report import send_report, send_failure_notice

LOG_FILE = Path.home() / 'Library' / 'Logs' / 'airbnb_monitor.log'

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger(__name__)


def main() -> None:
    log.info('Pipeline started')
    service = None

    try:
        service = build_service()
        new_pdfs = fetch_new_receipts(service)

        if not new_pdfs:
            log.info('No new receipts found. Exiting.')
            return

        for pdf_path in new_pdfs:
            log.info(f'Processing: {pdf_path}')
            data = extract(pdf_path)

            if data['warnings']:
                log.warning(f"Extraction warnings: {data['warnings']}")

            send_report(service, data)
            log.info(f'Report sent for tax period: {data["tax_period"]}')

            done_path = Path(pdf_path).with_suffix('.done')
            done_path.touch()
            log.info(f'Marked as done: {done_path.name}')

    except Exception as e:
        log.exception('Pipeline failed')
        if service:
            try:
                send_failure_notice(service, str(e))
            except Exception:
                log.exception('Failed to send failure notice')

    log.info('Pipeline finished')


if __name__ == '__main__':
    if '--auth' in sys.argv:
        get_credentials()
        print('Authentication successful. Token saved to credentials/token.json')
    else:
        main()
```

- [ ] **Step 2: Run the one-time auth flow**

```bash
.venv/bin/python src/run_pipeline.py --auth
```

Expected: browser opens, you log into berrystaysllc@gmail.com, approve access. Terminal prints `Authentication successful. Token saved to credentials/token.json`.

- [ ] **Step 3: Verify token was saved**

```bash
ls credentials/token.json
```

Expected: file exists.

- [ ] **Step 4: Run the full pipeline as a dry-run test**

The existing receipt PDFs in SalesReceipts already have `.done` sentinel files, so the pipeline should find the emails but skip the PDFs.

```bash
.venv/bin/python src/run_pipeline.py
```

Expected output in `~/Library/Logs/airbnb_monitor.log`:
```
... Pipeline started
... Gmail search: subject:"Sales Receipt" subject:"Tempe Townhome" subject:"Owner Statement"
... Already processed: <filename>.pdf
... No new receipts found. Exiting.
... Pipeline finished
```

Check the log:
```bash
tail -20 ~/Library/Logs/airbnb_monitor.log
```

- [ ] **Step 5: Test with a fresh PDF (end-to-end)**

Copy an existing PDF and remove its `.done` file to simulate a new receipt:

```bash
cp "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/2026-03_Sales_Receipt_10879_from_Rental_Advisor.pdf" \
   "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/test_receipt.pdf"
.venv/bin/python src/run_pipeline.py
```

Expected:
- Log shows: `Downloaded: test_receipt.pdf` (or `PDF exists, not yet processed`)
- Log shows: `Report sent for tax period: 2026-02`
- Email arrives at berrystaysllc@gmail.com with subject `AirBnB Tax Summary — February 2026`
- `test_receipt.done` sentinel file created

Clean up after verifying:
```bash
rm "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/test_receipt.pdf"
rm "/Users/jeffberry/Documents/Rice Drive LLC/SalesReceipts/test_receipt.done"
```

- [ ] **Step 6: Commit**

```bash
git add src/run_pipeline.py
git commit -m "feat: pipeline orchestrator with logging and error handling"
```

---

## Task 7: launchd Scheduler

**Files:**
- Create: `launchd/com.jeffberry.airbnb-monitor.plist`

- [ ] **Step 1: Create the plist**

Create `launchd/com.jeffberry.airbnb-monitor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jeffberry.airbnb-monitor</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/jeffberry/projects/airbnb_receipt_monitor/.venv/bin/python3</string>
        <string>/Users/jeffberry/projects/airbnb_receipt_monitor/src/run_pipeline.py</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>1</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>2</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>3</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>4</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>5</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>6</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>7</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>8</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer><key>Day</key><integer>9</integer></dict>
    </array>

    <key>StandardOutPath</key>
    <string>/Users/jeffberry/Library/Logs/airbnb_monitor.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/jeffberry/Library/Logs/airbnb_monitor.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Install the plist**

```bash
cp launchd/com.jeffberry.airbnb-monitor.plist \
   ~/Library/LaunchAgents/com.jeffberry.airbnb-monitor.plist

launchctl load ~/Library/LaunchAgents/com.jeffberry.airbnb-monitor.plist
```

- [ ] **Step 3: Verify the job is loaded**

```bash
launchctl list | grep airbnb
```

Expected: a line containing `com.jeffberry.airbnb-monitor` with a PID of `-` (not running, because it's not noon on days 1–9).

- [ ] **Step 4: Trigger a manual test run via launchctl**

```bash
launchctl start com.jeffberry.airbnb-monitor
```

Then check the log:
```bash
tail -20 ~/Library/Logs/airbnb_monitor.log
```

Expected: pipeline runs, finds no new receipts (all have `.done` files), exits cleanly.

- [ ] **Step 5: Commit**

```bash
git add launchd/com.jeffberry.airbnb-monitor.plist
git commit -m "feat: launchd scheduler — noon, days 1-9 each month"
```

---

## Full Test Suite

Run all tests at any time:

```bash
.venv/bin/pytest tests/ -v
```

Expected output:
```
tests/test_email_report.py::test_month_label_february PASSED
tests/test_email_report.py::test_month_label_december PASSED
tests/test_email_report.py::test_build_subject PASSED
tests/test_email_report.py::test_format_report_has_avalara_section PASSED
tests/test_email_report.py::test_format_report_airbnb_nights_and_revenue PASSED
tests/test_email_report.py::test_format_report_direct_nights_and_revenue PASSED
tests/test_email_report.py::test_format_report_checkbox_reminders PASSED
tests/test_email_report.py::test_format_report_no_warnings PASSED
tests/test_email_report.py::test_format_report_with_warnings PASSED
tests/test_email_report.py::test_format_report_has_property PASSED
tests/test_email_report.py::test_format_report_has_tax_period PASSED
tests/test_gmail_monitor.py::test_build_query_contains_all_keywords PASSED
tests/test_gmail_monitor.py::test_build_query_uses_subject_prefix PASSED
tests/test_pdf_extractor.py::test_normalize_date_slash_format PASSED
tests/test_pdf_extractor.py::test_normalize_date_short_year PASSED
tests/test_pdf_extractor.py::test_normalize_date_already_normalized PASSED
tests/test_pdf_extractor.py::test_parse_money_with_comma PASSED
tests/test_pdf_extractor.py::test_parse_money_with_dollar PASSED
tests/test_pdf_extractor.py::test_parse_money_invalid PASSED
tests/test_pdf_extractor.py::test_extract_returns_required_keys PASSED
tests/test_pdf_extractor.py::test_extract_tax_period PASSED
tests/test_pdf_extractor.py::test_extract_airbnb_totals PASSED
tests/test_pdf_extractor.py::test_extract_direct_totals PASSED
tests/test_pdf_extractor.py::test_extract_no_warnings PASSED
tests/test_pdf_extractor.py::test_extract_bookings_have_channels PASSED
```
