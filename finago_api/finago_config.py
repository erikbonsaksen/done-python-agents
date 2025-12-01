# finago_config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Core credentials
FINAGO_APP_ID = os.getenv("FINAGO_APPLICATION_ID")
FINAGO_USERNAME = os.getenv("FINAGO_USERNAME")
FINAGO_PASSWORD = os.getenv("FINAGO_PASSWORD")

# Endpoints – strip ?singleWsdl if present
FINAGO_AUTH_URL = (os.getenv("FINAGO_AUTH_URL") or "").split("?")[0] or \
    "https://api.24sevenoffice.com/authenticate/v001/authenticate.asmx"

FINAGO_CRM_URL = (os.getenv("FINAGO_CRM_URL") or "").split("?")[0]
FINAGO_PERSON_URL = (os.getenv("FINAGO_PERSON_URL") or "").split("?")[0]
FINAGO_INVOICE_URL = (os.getenv("FINAGO_INVOICE_URL") or "").split("?")[0]

# Shared namespace (same as in Next.js AuthService)
NS = "http://24sevenOffice.com/webservices"


def require_core_config() -> None:
    """Fail fast if required env vars are missing."""
    missing = []
    if not FINAGO_APP_ID:
        missing.append("FINAGO_APPLICATION_ID")
    if not FINAGO_USERNAME:
        missing.append("FINAGO_USERNAME")
    if not FINAGO_PASSWORD:
        missing.append("FINAGO_PASSWORD")
    if missing:
        raise SystemExit(
            "Missing required env vars: " + ", ".join(missing)
        )
