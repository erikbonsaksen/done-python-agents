# finago_api/endpoint/finago_accounts.py

from typing import List, Dict, Any

from ..finago_config import FINAGO_ACCOUNT_URL, NS
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v


def download_accounts(session_id: str) -> List[Dict[str, Any]]:
    """
    Fetch chart of accounts via AccountService.GetAccountList.

    Target table: accounts_sync
      accountNo, name, accountType, isActive, vatCode,
      openingBalance, closingBalance
    """
    if not FINAGO_ACCOUNT_URL:
        print("FINAGO_ACCOUNT_URL not set – skipping accounts.")
        return []

    client = FinagoSoapClient(FINAGO_ACCOUNT_URL)
    client.set_session(session_id)

    inner = f"""
<GetAccountList xmlns="{NS}" />
""".strip()

    doc = client.call("GetAccountList", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetAccountListResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetAccountListResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_items = []
    if isinstance(result, dict):
        raw_items = result.get("AccountData") or result.get("Account") or []

    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    accounts: List[Dict[str, Any]] = []

    for a in raw_items:
        accounts.append(
            {
                "accountNo": str(_v(a, "AccountNo") or ""),
                "name": _v(a, "AccountName") or "",
                "accountType": str(_v(a, "AccountTax") or ""),
                "isActive": 1,  # no explicit isActive flag in AccountData model
                "vatCode": str(_v(a, "TaxNo") or ""),
                "openingBalance": 0.0,  # can be filled later via another endpoint
                "closingBalance": 0.0,
            }
        )

    return accounts
