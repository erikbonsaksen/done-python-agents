# finago_api/endpoint/finago_transactions.py
from datetime import datetime
from typing import List, Dict, Any

from ..finago_config import FINAGO_TRANSACTION_URL
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v

ACCOUNTING_NS = "http://24sevenoffice.com/webservices/economy/accounting"
ACCOUNTING_NS_XML = ACCOUNTING_NS + "/"


def extract_dimensions(t: dict) -> dict:
    dims = {
        "customerId": None,
        "projectId": None,
        "departmentId": None,
    }

    dim_root = t.get("Dimensions") or t.get("Dimension") or None
    if not dim_root:
        return dims

    dim_items = []
    if isinstance(dim_root, dict):
        dim_items = dim_root.get("Dimension") or dim_root.get("Dimensions") or []
    if isinstance(dim_items, dict):
        dim_items = [dim_items]

    for d in dim_items:
        dim_type = (d.get("Type") or "").lower()
        dim_id = d.get("Id") or d.get("Value") or None
        if not dim_id:
            continue
        try:
            dim_id_int = int(dim_id)
        except ValueError:
            continue

        if dim_type == "customer":
            dims["customerId"] = dim_id_int
        elif dim_type == "project":
            dims["projectId"] = dim_id_int
        elif dim_type == "department":
            dims["departmentId"] = dim_id_int

    return dims


def download_transactions(
    session_id: str,
    changed_after: str = "2000-01-01",
) -> List[Dict[str, Any]]:
    if not FINAGO_TRANSACTION_URL:
        print("FINAGO_TRANSACTION_URL not set – skipping transactions.")
        return []

    client = FinagoSoapClient(FINAGO_TRANSACTION_URL, namespace=ACCOUNTING_NS)
    client.set_session(session_id)

    ds = changed_after.split("T")[0] + "T00:00:00"
    de = datetime.utcnow().strftime("%Y-%m-%d") + "T23:59:59"

    inner = f"""
<GetTransactions xmlns="{ACCOUNTING_NS_XML}">
  <searchParams>
    <DateStart>{ds}</DateStart>
    <DateEnd>{de}</DateEnd>
  </searchParams>
</GetTransactions>
""".strip()

    doc = client.call("GetTransactions", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetTransactionsResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetTransactionsResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_items = []
    if isinstance(result, dict):
        raw_items = result.get("Transaction") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    rows: List[Dict[str, Any]] = []

    def _to_int(val: Any) -> int | None:
        if val in (None, ""):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def _to_float(val: Any) -> float:
        if val in (None, ""):
            return 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    for t in raw_items:
        dims = extract_dimensions(t)

        rows.append(
            {
                "transactionId": _v(t, "Id") or None,
                "voucherNo": _to_int(_v(t, "TransactionNo")),
                "lineNo": _to_int(_v(t, "SequenceNo")),
                "date": _v(t, "Date") or "",
                "accountNo": str(_v(t, "AccountNo") or ""),
                "amount": _to_float(_v(t, "Amount")),
                "debit": _to_float(_v(t, "Debit")),
                "credit": _to_float(_v(t, "Credit")),
                "currency": _v(t, "Currency") or "",
                "description": _v(t, "Comment") or _v(t, "Text") or "",
                "invoiceNo": _v(t, "InvoiceNo") or "",
                "linkId": _to_int(_v(t, "LinkId")),
                "ocr": _v(t, "OCR") or "",
                "customerId": dims["customerId"],
                "projectId": dims["projectId"],
                "departmentId": dims["departmentId"],
            }
        )

    return rows
