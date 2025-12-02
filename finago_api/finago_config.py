import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# CORE CREDENTIALS
# -----------------------------
FINAGO_APP_ID = os.getenv("FINAGO_APPLICATION_ID")
FINAGO_USERNAME = os.getenv("FINAGO_USERNAME")
FINAGO_PASSWORD = os.getenv("FINAGO_PASSWORD")


# -----------------------------
# HELPER — Strip ?singleWsdl or other URL params
# -----------------------------
def clean_url(url: str | None) -> str:
    if not url:
        return ""
    return url.split("?")[0].strip()


# -----------------------------
# SOAP ENDPOINTS
# -----------------------------

# Authentication
FINAGO_AUTH_URL = clean_url(
    os.getenv("FINAGO_AUTH_URL")
    or "https://api.24sevenoffice.com/authenticate/v001/authenticate.asmx"
)

# CRM: Companies
FINAGO_CRM_URL = clean_url(os.getenv("FINAGO_CRM_URL"))

# Persons
FINAGO_PERSON_URL = clean_url(os.getenv("FINAGO_PERSON_URL"))

# Invoices / orders
FINAGO_INVOICE_URL = clean_url(os.getenv("FINAGO_INVOICE_URL"))

# Products
FINAGO_PRODUCT_URL = clean_url(os.getenv("FINAGO_PRODUCT_URL"))

# Transactions / bilag
FINAGO_TRANSACTION_URL = clean_url(os.getenv("FINAGO_TRANSACTION_URL"))

# Accounts / chart of accounts
FINAGO_ACCOUNT_URL = clean_url(os.getenv("FINAGO_ACCOUNT_URL"))


# -----------------------------
# SHARED SOAP NAMESPACE
# -----------------------------
NS = "http://24sevenOffice.com/webservices"


# -----------------------------
# CONFIG VALIDATION
# -----------------------------
def require_core_config() -> None:
    """
    Fail fast if required env vars are missing.
    Only checks the *credentials*, not every endpoint, so you can
    enable/disable modules freely.
    """
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
