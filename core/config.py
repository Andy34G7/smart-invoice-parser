import os
import re
from dotenv import load_dotenv
load_dotenv()
QA_MODEL = os.environ.get("INVOICE_QA_MODEL", "distilbert-base-cased-distilled-squad")
LLM_MODEL = os.environ.get("INVOICE_LLM_MODEL", "")
GSTIN_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$')
