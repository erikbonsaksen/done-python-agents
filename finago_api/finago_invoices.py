# finago_invoices.py
from typing import List, Dict, Any

from finago_config import FINAGO_INVOICE_URL, NS
from finago_soap import FinagoSoapClient


def _val(inv: Dict[str, Any], key: str):
    v = inv.get(key)
    if isinstance(v, list):
        v = v[0]
    return v


def download_invoices(
    session_id: str,
    changed_after: str,
) -> List[Dict[str, Any]]:
    """
    Calls the Invoice SOAP service (GetInvoices) and returns
    a list of dicts for invoices_sync.

    This mirrors the behaviour of your Next.js InvoiceService:
    - Uses ChangedAfter in searchParams
    - Requests the same invoiceReturnProperties
    """
    if not FINAGO_INVOICE_URL:
        print("FINAGO_INVOICE_URL not set – skipping invoice download.")
        return []

    invoice_client = FinagoSoapClient(FINAGO_INVOICE_URL)
    invoice_client.set_session(session_id)

    # Ensure proper dateTime format like in company call
    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

    # Shape based on official docs + your Next.js route:
    # https://developer.24sevenoffice.com/docs/invoiceservice.html
    inner = f"""
<GetInvoices xmlns="{NS}">
  <searchParams>
    <ChangedAfter>{ds}</ChangedAfter>
  </searchParams>
  <invoiceReturnProperties>
    <string>InvoiceId</string>
    <string>OrderId</string>
    <string>CustomerId</string>
    <string>CustomerName</string>
    <string>DateInvoiced</string>
    <string>DateChanged</string>
    <string>OrderTotalIncVat</string>
    <string>OrderTotalVat</string>
    <string>Currency.Symbol</string>
    <string>OrderStatus</string>
    <string>ExternalStatus</string>
  </invoiceReturnProperties>
</GetInvoices>
"""

    # FinagoSoapClient will send SOAPAction = f"{NS}/GetInvoices"
    doc = invoice_client.call("GetInvoices", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetInvoicesResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = None
    if isinstance(resp, dict):
        result = resp.get("GetInvoicesResult")

    if isinstance(result, list):
        result = result[0]

    raw_invoices = []
    if isinstance(result, dict):
        # WSDL says it returns InvoiceOrder[]
        raw_invoices = result.get("InvoiceOrder") or result.get("Invoice") or []

    if isinstance(raw_invoices, dict):
        raw_invoices = [raw_invoices]

    invoices: List[Dict[str, Any]] = []

    for inv in raw_invoices:
        # Map from InvoiceOrder fields to your SQLite schema.
        # Property names follow 24SO docs and your JS mapping.
        invoices.append(
            {
                "invoiceId": int(_val(inv, "InvoiceId") or 0),
                "orderId": int(_val(inv, "OrderId") or 0),
                "customerId": int(_val(inv, "CustomerId") or 0),
                "customerName": _val(inv, "CustomerName") or "",
                "dateInvoiced": _val(inv, "DateInvoiced") or "",
                "dateChanged": _val(inv, "DateChanged") or "",
                # In docs: OrderTotalIncVat / OrderTotalVat
                "totalIncVat": float(
                    _val(inv, "OrderTotalIncVat") or _val(inv, "TotalIncVat") or 0
                ),
                "totalVat": float(
                    _val(inv, "OrderTotalVat") or _val(inv, "TotalVat") or 0
                ),
                # Currency.Symbol comes back as nested object; your JS InvoiceService
                # presumably flattens this. xmltodict will give nested dict,
                # so we handle both.
                "currencySymbol": (
                    _val(inv, "Currency.Symbol")
                    or (
                        isinstance(_val(inv, "Currency"), dict)
                        and _val(inv, "Currency").get("Symbol")
                    )
                    or ""
                ),
                "status": _val(inv, "OrderStatus") or _val(inv, "Status") or "",
                "externalStatus": _val(inv, "ExternalStatus") or "",
            }
        )

    return invoices
