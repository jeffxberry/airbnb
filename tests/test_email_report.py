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
