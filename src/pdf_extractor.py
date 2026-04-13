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
# Build regex that matches the phrase even when pdfplumber inserts a newline
# mid-phrase (e.g. "already\npaid by Vendor" instead of "already paid by Vendor")
_AIRBNB_RE = re.compile(
    r'\s+'.join(re.escape(w) for w in AIRBNB_TAX_PHRASE.split()),
    re.IGNORECASE | re.DOTALL,
)


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
        # e.g. "01/03/2026 to 3,241.68 02/02/2026" (amount interrupts date range)
        # e.g. "02/04/2026 3,166.58 to 02/19/2026" (amount before "to")
        block_flat = ' '.join(block.split())
        check_in = check_out = None
        nights = None

        # Strategy A: "date to date" directly adjacent (clean layout)
        direct_m = re.search(
            r'(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})',
            block_flat
        )
        if direct_m:
            check_in = normalize_date(direct_m.group(1))
            check_out = normalize_date(direct_m.group(2))
        else:
            # Strategy B: first date = check-in, then look for "to <date>" or
            # "to <amount> <date>" (when an amount is rendered between "to" and checkout),
            # or fall back to next distinct date in the block.
            checkin_m = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', block_flat)
            if checkin_m:
                check_in = normalize_date(checkin_m.group(1))

                # Try "to <date>" first (e.g. "02/04/2026 3,166.58 to 02/19/2026")
                to_m = re.search(r'\bto\s+(\d{1,2}/\d{1,2}/\d{4})', block_flat)
                if to_m:
                    check_out = normalize_date(to_m.group(1))
                else:
                    # Try "to <amount> <date>" (e.g. "01/03/2026 to 3,241.68 02/02/2026")
                    to_amt_m = re.search(
                        r'\bto\s+[\d,]+\.\d{2}\s+(\d{1,2}/\d{1,2}/\d{4})',
                        block_flat
                    )
                    if to_amt_m:
                        check_out = normalize_date(to_amt_m.group(1))
                    else:
                        # Fallback: first date different from check-in in the block
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
