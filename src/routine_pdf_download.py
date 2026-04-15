"""Download a PDF attachment from a Gmail message.

Usage: python -m src.routine_pdf_download <message_id> [output_dir]

Prints the path to the downloaded PDF on stdout.
Exits with code 1 if no PDF attachment is found.
"""
from __future__ import annotations
import base64
import sys
from pathlib import Path
from src.gmail_monitor import build_service


def download_pdf(message_id: str, output_dir: str) -> str | None:
    """Download the first PDF attachment from a Gmail message.

    Returns the path to the saved PDF, or None if no PDF found.
    """
    service = build_service()
    msg = service.users().messages().get(
        userId='me', id=message_id, format='full'
    ).execute()

    parts = msg.get('payload', {}).get('parts', [])
    result = _find_and_download_pdf(service, message_id, parts, output_dir)
    return result


def _find_and_download_pdf(service, msg_id: str, parts: list, output_dir: str) -> str | None:
    """Recursively search message parts for a PDF and download it."""
    for part in parts:
        mime = part.get('mimeType', '')
        filename = part.get('filename', '')

        if mime.startswith('multipart/') and part.get('parts'):
            result = _find_and_download_pdf(service, msg_id, part['parts'], output_dir)
            if result:
                return result

        if filename.lower().endswith('.pdf') or mime == 'application/pdf':
            att_id = part.get('body', {}).get('attachmentId')
            if att_id:
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id
                ).execute()
                data = base64.urlsafe_b64decode(att['data'])
                dest = Path(output_dir) / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                return str(dest)
    return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python -m src.routine_pdf_download <message_id> [output_dir]', file=sys.stderr)
        sys.exit(1)

    msg_id = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else '/tmp/receipts'

    path = download_pdf(msg_id, out_dir)
    if path:
        print(path)
    else:
        print('No PDF attachment found', file=sys.stderr)
        sys.exit(1)
