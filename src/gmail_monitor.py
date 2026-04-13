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
CREDENTIALS_FILE = _PROJECT_ROOT / 'credentials' / 'credentials.json'
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
    Recursively searches nested multipart structures. Returns None if not found.
    """
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    def _find_pdf(parts: list) -> tuple[str, bytes] | None:
        for part in parts:
            filename = part.get('filename', '')
            mime = part.get('mimeType', '')
            # Recurse into nested multipart
            if mime.startswith('multipart/') and part.get('parts'):
                result = _find_pdf(part['parts'])
                if result:
                    return result
            if filename.lower().endswith('.pdf') or mime == 'application/pdf':
                att_id = part.get('body', {}).get('attachmentId')
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=att_id
                    ).execute()
                    data = base64.urlsafe_b64decode(att['data'])
                    return filename, data
        return None

    parts = msg.get('payload', {}).get('parts', [])
    return _find_pdf(parts)


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
    receipts_dir.mkdir(parents=True, exist_ok=True)
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
