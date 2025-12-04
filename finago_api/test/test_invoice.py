#!/usr/bin/env python3
"""
Test Paid Field Logic

This script fetches invoices and tests the payment status logic using the Paid field.
"""

import sys
from finago_api.finago_config import (
    FINAGO_APP_ID,
    FINAGO_USERNAME,
    FINAGO_PASSWORD,
    FINAGO_AUTH_URL,
    FINAGO_INVOICE_URL,
    NS,
)
from finago_api.finago_soap import FinagoSoapClient
from finago_api.finago_auth import AuthService

print("=" * 80)
print("Testing Paid Field Logic")
print("=" * 80)

# 1. Login
print("\n1. Logging in...")
auth_client = FinagoSoapClient(FINAGO_AUTH_URL)
auth_service = AuthService(auth_client)
session_id = auth_service.login(FINAGO_APP_ID, FINAGO_USERNAME, FINAGO_PASSWORD)
print(f"   ✓ Logged in")

# 2. Select identity
print("\n2. Setting identity...")
identities = auth_service.get_identities()
if identities:
    print("\nAvailable identities:")
    for i, identity in enumerate(identities, 1):
        print(f" {i}) {identity.name}")
    
    choice = input("\nSelect identity (or Enter for #1): ").strip()
    idx = int(choice) - 1 if choice else 0
    
    selected = identities[idx]
    auth_service.set_identity_by_id(selected.id)
    print(f"   ✓ Using: {selected.name}")

# 3. Fetch invoices
print("\n3. Fetching invoices from last 60 days...")
client = FinagoSoapClient(FINAGO_INVOICE_URL, namespace=NS)
client.set_session(session_id)

search_xml = "<ChangedAfter>2024-10-01T00:00:00</ChangedAfter>"

# Only request fields we care about
invoice_props = """
<string>InvoiceId</string>
<string>InvoiceNumber</string>
<string>CustomerId</string>
<string>CustomerName</string>
<string>DateInvoiced</string>
<string>OrderTotalIncVat</string>
<string>OrderStatus</string>
<string>Paid</string>
<string>IsCredited</string>
""".strip()

row_props = "<string>ProductId</string>"

inner = f"""
<GetInvoices xmlns="{NS}">
  <searchParams>{search_xml}</searchParams>
  <invoiceReturnProperties>{invoice_props}</invoiceReturnProperties>
  <rowReturnProperties>{row_props}</rowReturnProperties>
</GetInvoices>
"""

doc = client.call("GetInvoices", inner)

# Parse
body = doc.get("soap:Envelope", {}).get("soap:Body", {})
resp = body.get("GetInvoicesResponse")
if isinstance(resp, list):
    resp = resp[0]
result = resp.get("GetInvoicesResult") if isinstance(resp, dict) else None
if isinstance(result, list):
    result = result[0]

raw_items = []
if isinstance(result, dict):
    raw_items = result.get("InvoiceOrder") or result.get("Invoice") or []
if isinstance(raw_items, dict):
    raw_items = [raw_items]

print(f"   ✓ Found {len(raw_items)} invoices")

if not raw_items:
    print("   ❌ No invoices found!")
    sys.exit(1)

# 4. Test the payment status logic
print("\n" + "=" * 80)
print("TESTING PAYMENT STATUS LOGIC:")
print("=" * 80)

def safe_get(data, key):
    """Safely get value from dict or list"""
    val = data.get(key)
    if isinstance(val, list) and val:
        val = val[0]
    return val

def determine_status(invoice):
    """Apply our payment status logic"""
    paid_date = safe_get(invoice, "Paid") or ""
    is_credited = safe_get(invoice, "IsCredited")
    total = safe_get(invoice, "OrderTotalIncVat") or 0
    
    # Convert IsCredited to boolean
    if isinstance(is_credited, str):
        is_credited = is_credited.lower() in ('true', '1', 'yes')
    elif not isinstance(is_credited, bool):
        is_credited = bool(is_credited)
    
    # Determine status
    if is_credited:
        status = "Credited"
        balance = 0.0
        amount_paid = 0.0
    elif paid_date and str(paid_date).strip():
        status = "Paid"
        balance = 0.0
        amount_paid = float(total)
    else:
        status = "Unpaid"
        balance = float(total)
        amount_paid = 0.0
    
    return status, balance, amount_paid

# Categorize invoices
paid_invoices = []
unpaid_invoices = []
credited_invoices = []

for invoice in raw_items:
    status, balance, amount_paid = determine_status(invoice)
    
    invoice_data = {
        'invoice_id': safe_get(invoice, "InvoiceId"),
        'invoice_no': safe_get(invoice, "InvoiceNumber") or safe_get(invoice, "InvoiceId"),
        'customer': safe_get(invoice, "CustomerName"),
        'date': safe_get(invoice, "DateInvoiced"),
        'total': safe_get(invoice, "OrderTotalIncVat"),
        'order_status': safe_get(invoice, "OrderStatus"),
        'paid_date': safe_get(invoice, "Paid"),
        'status': status,
        'balance': balance,
        'amount_paid': amount_paid,
    }
    
    if status == "Paid":
        paid_invoices.append(invoice_data)
    elif status == "Credited":
        credited_invoices.append(invoice_data)
    else:
        unpaid_invoices.append(invoice_data)

# 5. Display results
print(f"\n📊 Summary:")
print(f"   Total invoices: {len(raw_items)}")
print(f"   Paid:           {len(paid_invoices)}")
print(f"   Unpaid:         {len(unpaid_invoices)}")
print(f"   Credited:       {len(credited_invoices)}")

total_outstanding = sum(inv['balance'] for inv in unpaid_invoices)
print(f"\n💰 Outstanding Receivables: {total_outstanding:,.2f} NOK")

# Show some examples
print("\n" + "=" * 80)
print("PAID INVOICES (first 5):")
print("=" * 80)
for inv in paid_invoices[:5]:
    print(f"\nInvoice {inv['invoice_no']} - {inv['customer']}")
    print(f"  Amount:     {float(inv['total']):,.2f} NOK")
    print(f"  Paid Date:  {inv['paid_date']}")
    print(f"  Status:     {inv['status']}")
    print(f"  Balance:    {inv['balance']:,.2f} NOK")

print("\n" + "=" * 80)
print("UNPAID INVOICES (first 5):")
print("=" * 80)
for inv in unpaid_invoices[:5]:
    print(f"\nInvoice {inv['invoice_no']} - {inv['customer']}")
    print(f"  Amount:     {float(inv['total']):,.2f} NOK")
    print(f"  Paid Date:  {inv['paid_date'] or '(not paid)'}")
    print(f"  Status:     {inv['status']}")
    print(f"  Balance:    {inv['balance']:,.2f} NOK")

print("\n" + "=" * 80)
print("✅ VERIFICATION:")
print("=" * 80)
print("Logic:")
print("  1. If Paid field has a date → Status = 'Paid', Balance = 0")
print("  2. If Paid field is empty   → Status = 'Unpaid', Balance = Total")
print("  3. If IsCredited = true     → Status = 'Credited', Balance = 0")
print("\nDoes this match what you see in Finago? (Check the numbers)")
print("=" * 80)