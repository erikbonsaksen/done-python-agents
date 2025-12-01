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
    Calls the Invoice SOAP service and returns list of dicts for invoices_sync.
    """
    if not FINAGO_INVOICE_URL:
        print("FINAGO_INVOICE_URL not set – skipping invoice download.")
        return []

    invoice_client = FinagoSoapClient(FINAGO_INVOICE_URL)
    invoice_client.set_session(session_id)

    # 👉 IMPORTANT:
    # Copy the body from Next.js /api/tfso/download-invoices.
    inner = f"""
      <GetInvoices xmlns="{NS}">
        <filter>
          <ChangedAfter>{changed_after}</ChangedAfter>
          <!-- Copy any other filters from Next.js (ClientId, Status, etc.) -->
        </filter>
      </GetInvoices>
    """

    # 🔹 Replace SOAPAction with the same as in Next.js:
    # e.g. 'http://24sevenOffice.com/webservices/IInvoiceService/GetInvoices'
    doc = invoice_client.call(
        "http://24sevenOffice.com/webservices/IInvoiceService/GetInvoices",
        inner,
        full_action=True,
    )

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
        raw_invoices = result.get("Invoice") or result.get("InvoiceItems") or []

    if isinstance(raw_invoices, dict):
        raw_invoices = [raw_invoices]

    invoices: List[Dict[str, Any]] = []

    for inv in raw_invoices:
        invoices.append(
            {
                "invoiceId": int(_val(inv, "InvoiceId") or 0),
                "orderId": int(_val(inv, "OrderId") or 0),
                "customerId": int(_val(inv, "CustomerId") or 0),
                "customerName": _val(inv, "CustomerName") or "",
                "dateInvoiced": _val(inv, "DateInvoiced") or "",
                "dateChanged": _val(inv, "DateChanged") or "",
                "totalIncVat": float(_val(inv, "TotalIncVat") or 0)
                if _val(inv, "TotalIncVat")
                else 0.0,
                "totalVat": float(_val(inv, "TotalVat") or 0)
                if _val(inv, "TotalVat")
                else 0.0,
                "currencySymbol": _val(inv, "CurrencySymbol") or "",
                "status": _val(inv, "Status") or "",
                "externalStatus": _val(inv, "ExternalStatus") or "",
            }
        )

    return invoices
