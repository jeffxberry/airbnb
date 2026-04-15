import pytest
from pathlib import Path
from src.pdf_extractor import extract, normalize_date, parse_money

PDF_PATH = str(Path(__file__).parent / "fixtures" / "test_receipt.pdf")
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
