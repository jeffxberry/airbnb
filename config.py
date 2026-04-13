import os
from dotenv import load_dotenv

load_dotenv()

RECEIPTS_DIR      = os.environ["RECEIPTS_DIR"]
SOURCE_EMAIL      = os.environ["SOURCE_EMAIL"]
SUBJECT_KEYWORDS  = [kw.strip() for kw in os.environ["SUBJECT_KEYWORDS"].split(",")]
GMAIL_ACCOUNT     = os.environ["GMAIL_ACCOUNT"]
REPORT_TO         = os.environ["REPORT_TO"]
AVALARA_PROPERTY  = os.environ["AVALARA_PROPERTY"]
AIRBNB_TAX_PHRASE = "Taxes for this reservation already paid by Vendor"
