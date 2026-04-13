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
