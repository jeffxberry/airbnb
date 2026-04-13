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
        '\u2500\u2500 BOOKINGS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
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

    ab_nights = ab.get('nights', 0)
    ab_rev = ab.get('revenue', 0.0)
    di_nights = di.get('nights', 0)
    di_rev = di.get('revenue', 0.0)

    lines += [
        '\u2500\u2500 AVALARA ENTRY \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
        f'  AirBnB  \u2192  {ab_nights:2d} nights  /  {_fmt_money(ab_rev)}   (leave "Revenue Includes Tax" UNCHECKED)',
        f'  Direct  \u2192  {di_nights:2d} nights  /  {_fmt_money(di_rev)}   (CHECK "Revenue Includes Tax")',
        f'  VRBO    \u2192   0 nights  /       $0.00',
        '',
        '\u2500\u2500 WARNINGS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
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
