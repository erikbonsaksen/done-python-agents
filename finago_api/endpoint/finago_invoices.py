# finago_api/endpoint/finago_invoices.py

from typing import List, Dict, Any

from ..finago_config import FINAGO_INVOICE_URL, NS
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v


def download_invoices(
    session_id: str,
    changed_after: str = "2000-01-01",
) -> List[Dict[str, Any]]:
    """
    Fetch outgoing invoices/orders via InvoiceService.GetInvoices.

    Target table: invoices_sync

    Expected columns in invoices_sync:
      invoiceId       INTEGER PRIMARY KEY,
      orderId         INTEGER,
      customerId      INTEGER,
      customerName    TEXT,
      invoiceNo       TEXT,
      supplierName    TEXT,
      supplierOrgNo   TEXT,
      invoiceText     TEXT,
      dateInvoiced    TEXT,
      dateChanged     TEXT,
      totalIncVat     REAL,
      totalVat        REAL,
      currencySymbol  TEXT,
      status          TEXT,
      externalStatus  TEXT
    """
    if not FINAGO_INVOICE_URL:
        print("FINAGO_INVOICE_URL not set – skipping invoices.")
        return []

    client = FinagoSoapClient(FINAGO_INVOICE_URL, namespace=NS)
    client.set_session(session_id)

    # Ensure full datetime as required by ChangedAfter
    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

    # Search by ChangedAfter
    search_xml = f"""
<ChangedAfter>{ds}</ChangedAfter>
""".strip()

    # Ask for the properties we actually want to persist
    invoice_return_props = """
<string>OrderId</string>
<string>CustomerId</string>
<string>CustomerName</string>
<string>InvoiceId</string>
<string>InvoiceNumber</string>
<string>DateInvoiced</string>
<string>DateChanged</string>
<string>OrderTotalIncVat</string>
<string>OrderTotalVat</string>
<string>Currency</string>
<string>OrderStatus</string>
<string>ExternalStatus</string>
""".strip()

    # Row properties – required by API even if we ignore them for now
    row_return_props = """
<string>ProductId</string>
<string>RowId</string>
<string>Name</string>
<string>Quantity</string>
<string>Price</string>
""".strip()

    inner = f"""
<GetInvoices xmlns="{NS}">
  <searchParams>
    {search_xml}
  </searchParams>
  <invoiceReturnProperties>
    {invoice_return_props}
  </invoiceReturnProperties>
  <rowReturnProperties>
    {row_return_props}
  </rowReturnProperties>
</GetInvoices>
""".strip()

    doc = client.call("GetInvoices", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetInvoicesResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetInvoicesResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_items = []
    if isinstance(result, dict):
        # In 24SO docs, the element is normally InvoiceOrder[]
        raw_items = result.get("InvoiceOrder") or result.get("Invoice") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    invoices: List[Dict[str, Any]] = []

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

    for inv in raw_items:
        # Currency is often a nested object with .Symbol
        currency_symbol = ""
        currency = inv.get("Currency")
        if isinstance(currency, list):
            currency = currency[0]
        if isinstance(currency, dict):
            currency_symbol = _v(currency, "Symbol") or ""

        invoices.append(
            {
                "invoiceId": _to_int(_v(inv, "InvoiceId")) or 0,
                "orderId": _to_int(_v(inv, "OrderId")),
                "customerId": _to_int(_v(inv, "CustomerId")),
                "customerName": _v(inv, "CustomerName") or "",
                # This is important for joining transactions ↔ invoices
                "invoiceNo": _v(inv, "InvoiceNumber") or _v(inv, "InvoiceNo") or "",
                # For AR this may be empty; for AP you'd typically get this from another service,
                # but we keep the columns so the schema is stable.
                "supplierName": _v(inv, "SupplierName") or "",
                "supplierOrgNo": _v(inv, "SupplierOrganizationNumber") or "",
                "invoiceText": _v(inv, "Text") or _v(inv, "Description") or "",
                "dateInvoiced": _v(inv, "DateInvoiced") or _v(inv, "InvoiceDate") or "",
                "dateChanged": _v(inv, "DateChanged") or "",
                "totalIncVat": _to_float(_v(inv, "OrderTotalIncVat")),
                "totalVat": _to_float(_v(inv, "OrderTotalVat")),
                "currencySymbol": currency_symbol,
                "status": _v(inv, "OrderStatus") or "",
                "externalStatus": str(_v(inv, "ExternalStatus") or ""),
            }
        )

    # Filter out obviously broken rows (no invoiceId)
    invoices = [inv for inv in invoices if inv["invoiceId"]]

    return invoices
