"""Extract booking data from a sales receipt PDF and output as JSON.

Usage: python -m src.routine_extract <pdf_path>

Prints JSON extraction result to stdout.
Exits with code 1 if the file doesn't exist.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from src.pdf_extractor import extract


def extract_to_json(pdf_path: str) -> str:
    """Run extraction on a PDF and return the result as a JSON string."""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f'PDF not found: {pdf_path}')
    data = extract(pdf_path)
    return json.dumps(data, indent=2)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python -m src.routine_extract <pdf_path>', file=sys.stderr)
        sys.exit(1)

    try:
        result = extract_to_json(sys.argv[1])
        print(result)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
