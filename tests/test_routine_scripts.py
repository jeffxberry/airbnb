"""Tests for Routine helper scripts."""
from __future__ import annotations
import json
import base64
import subprocess
import sys
from unittest.mock import patch, MagicMock
import pytest


def test_routine_pdf_download_prints_path(tmp_path, monkeypatch):
    """routine_pdf_download writes the PDF to disk and prints the path."""
    monkeypatch.setenv('GMAIL_TOKEN_JSON', '{"token": "fake", "refresh_token": "fake", "client_id": "x", "client_secret": "y", "token_uri": "https://oauth2.googleapis.com/token"}')
    monkeypatch.setenv('RECEIPTS_DIR', str(tmp_path))
    monkeypatch.setenv('SOURCE_EMAIL', 'test@example.com')
    monkeypatch.setenv('SUBJECT_KEYWORDS', 'Test')
    monkeypatch.setenv('GMAIL_ACCOUNT', 'test@example.com')
    monkeypatch.setenv('REPORT_TO', 'test@example.com')
    monkeypatch.setenv('AVALARA_PROPERTY', '12345 - Test LLC')

    from src.routine_pdf_download import download_pdf

    fake_pdf_bytes = b'%PDF-1.4 fake content'
    encoded = base64.urlsafe_b64encode(fake_pdf_bytes).decode()

    mock_service = MagicMock()
    mock_service.users().messages().get().execute.return_value = {
        'payload': {
            'parts': [
                {
                    'mimeType': 'text/html',
                    'filename': '',
                    'body': {'size': 100},
                },
                {
                    'mimeType': 'application/pdf',
                    'filename': 'Sales_Receipt_11029.pdf',
                    'body': {'attachmentId': 'att-123', 'size': 42628},
                },
            ]
        }
    }
    mock_service.users().messages().attachments().get().execute.return_value = {
        'data': encoded
    }

    with patch('src.routine_pdf_download.build_service', return_value=mock_service):
        result_path = download_pdf('msg-abc123', str(tmp_path))

    assert result_path.endswith('.pdf')
    assert (tmp_path / 'Sales_Receipt_11029.pdf').read_bytes() == fake_pdf_bytes


def test_routine_pdf_download_no_attachment(tmp_path, monkeypatch):
    """routine_pdf_download returns None when no PDF attachment found."""
    monkeypatch.setenv('GMAIL_TOKEN_JSON', '{"token": "fake", "refresh_token": "fake", "client_id": "x", "client_secret": "y", "token_uri": "https://oauth2.googleapis.com/token"}')
    monkeypatch.setenv('RECEIPTS_DIR', str(tmp_path))
    monkeypatch.setenv('SOURCE_EMAIL', 'test@example.com')
    monkeypatch.setenv('SUBJECT_KEYWORDS', 'Test')
    monkeypatch.setenv('GMAIL_ACCOUNT', 'test@example.com')
    monkeypatch.setenv('REPORT_TO', 'test@example.com')
    monkeypatch.setenv('AVALARA_PROPERTY', '12345 - Test LLC')

    from src.routine_pdf_download import download_pdf

    mock_service = MagicMock()
    mock_service.users().messages().get().execute.return_value = {
        'payload': {
            'parts': [
                {'mimeType': 'text/html', 'filename': '', 'body': {'size': 100}},
            ]
        }
    }

    with patch('src.routine_pdf_download.build_service', return_value=mock_service):
        result = download_pdf('msg-abc123', str(tmp_path))

    assert result is None
