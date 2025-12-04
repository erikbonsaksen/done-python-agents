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
    
    UPDATED: Now fetches payment status fields

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
      dateDue         TEXT,          -- NEW
      dateChanged     TEXT,
      totalIncVat     REAL,
      totalVat        REAL,
      amountPaid      REAL,          -- NEW
      balance         REAL,          -- NEW
      currencySymbol  TEXT,
      status          TEXT,
      externalStatus  TEXT,
      isCredited      INTEGER        -- NEW
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

    # UPDATED: Request Paid field which contains payment date
    # NOTE: The API returns "Paid" field with payment date, not Balance/AmountPaid
    invoice_return_props = """
<string>OrderId</string>
<string>CustomerId</string>
<string>CustomerName</string>
<string>InvoiceId</string>
<string>InvoiceNumber</string>
<string>DateInvoiced</string>
<string>DueDate</string>
<string>DateChanged</string>
<string>OrderTotalIncVat</string>
<string>OrderTotalVat</string>
<string>Currency</string>
<string>OrderStatus</string>
<string>ExternalStatus</string>
<string>Paid</string>
<string>IsCredited</string>
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

    def _to_bool(val: Any) -> int:
        """Convert boolean-ish values to 1/0"""
        if val in (None, ""):
            return 0
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, str):
            return 1 if val.lower() in ('true', '1', 'yes') else 0
        return 0

    for inv in raw_items:
        # Currency is often a nested object with .Symbol
        currency_symbol = ""
        currency = inv.get("Currency")
        if isinstance(currency, list):
            currency = currency[0]
        if isinstance(currency, dict):
            currency_symbol = _v(currency, "Symbol") or ""

        # Get payment-related fields
        paid_date = _v(inv, "Paid") or ""
        is_credited = _to_bool(_v(inv, "IsCredited"))
        total_inc_vat = _to_float(_v(inv, "OrderTotalIncVat"))
        
        # Determine actual payment status based on Paid field
        # If Paid field has a date -> Status = "Paid"
        # If Paid field is empty/null -> Status = "Unpaid"
        order_status = _v(inv, "OrderStatus") or "Invoiced"
        
        if is_credited:
            actual_status = "Credited"
        elif paid_date and paid_date.strip():
            # Has a payment date -> invoice is paid
            actual_status = "Paid"
        else:
            # No payment date -> invoice is unpaid
            actual_status = "Unpaid"
        
        # Calculate balance based on payment status
        if actual_status == "Paid":
            balance = 0.0
            amount_paid = total_inc_vat
        elif actual_status == "Credited":
            balance = 0.0
            amount_paid = 0.0
        else:
            balance = total_inc_vat
            amount_paid = 0.0

        invoices.append(
            {
                "invoiceId": _to_int(_v(inv, "InvoiceId")) or 0,
                "orderId": _to_int(_v(inv, "OrderId")),
                "customerId": _to_int(_v(inv, "CustomerId")),
                "customerName": _v(inv, "CustomerName") or "",
                "invoiceNo": _v(inv, "InvoiceNumber") or _v(inv, "InvoiceNo") or "",
                "supplierName": _v(inv, "SupplierName") or "",
                "supplierOrgNo": _v(inv, "SupplierOrganizationNumber") or "",
                "invoiceText": _v(inv, "Text") or _v(inv, "Description") or "",
                "dateInvoiced": _v(inv, "DateInvoiced") or _v(inv, "InvoiceDate") or "",
                "dateDue": _v(inv, "DueDate") or "",
                "datePaid": paid_date if paid_date and paid_date.strip() else None,  # NEW: Store actual payment date
                "dateChanged": _v(inv, "DateChanged") or "",
                "totalIncVat": total_inc_vat,
                "totalVat": _to_float(_v(inv, "OrderTotalVat")),
                "amountPaid": amount_paid,
                "balance": balance,
                "currencySymbol": currency_symbol,
                "status": actual_status,
                "externalStatus": str(_v(inv, "ExternalStatus") or ""),
                "isCredited": is_credited,
            }
        )

    # Filter out obviously broken rows (no invoiceId)
    invoices = [inv for inv in invoices if inv["invoiceId"]]

    return invoices