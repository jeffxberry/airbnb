from src.gmail_monitor import _build_query
from config import SUBJECT_KEYWORDS


def test_build_query_contains_all_keywords():
    query = _build_query()
    for kw in SUBJECT_KEYWORDS:
        assert kw in query


def test_build_query_uses_subject_prefix():
    query = _build_query()
    assert query.startswith('subject:')
