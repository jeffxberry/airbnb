from __future__ import annotations
import sys
import os
import logging
from pathlib import Path

# Ensure project root is in sys.path when called by launchd
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gmail_monitor import build_service, fetch_new_receipts, get_credentials, get_or_create_label, mark_as_processed
from src.pdf_extractor import extract
from src.email_report import send_report, send_failure_notice

_handlers = [logging.StreamHandler()]
if os.environ.get('CLAUDE_CODE_REMOTE') != 'true':
    _log_file = Path.home() / 'Library' / 'Logs' / 'airbnb_monitor.log'
    _handlers.append(logging.FileHandler(str(_log_file)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=_handlers,
)
log = logging.getLogger(__name__)


def main() -> None:
    log.info('Pipeline started')
    service = None

    try:
        service = build_service()
        label_id = get_or_create_label(service)
        new_receipts = fetch_new_receipts(service)

        if not new_receipts:
            log.info('No new receipts found. Exiting.')
            return

        for msg_id, pdf_path in new_receipts:
            log.info(f'Processing: {pdf_path}')
            data = extract(pdf_path)

            if data['warnings']:
                log.warning(f"Extraction warnings: {data['warnings']}")

            send_report(service, data)
            log.info(f'Report sent for tax period: {data["tax_period"]}')

            mark_as_processed(service, msg_id, label_id)
            log.info(f'Labeled as processed: {msg_id}')

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
