import sqlite3

conn = sqlite3.connect("tfso-data.db")
cur = conn.cursor()

# Check invoice statuses
cur.execute("""
    SELECT status, COUNT(*) as count, SUM(totalIncVat) as total
    FROM invoices_sync
    GROUP BY status
""")

print("Invoice Statuses:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} invoices, {row[2]:,.2f} NOK")

# Check unpaid invoices
cur.execute("""
    SELECT COUNT(*) as count, SUM(totalIncVat) as total
    FROM invoices_sync
    WHERE status NOT IN ('Paid', 'Cancelled')
""")

row = cur.fetchone()
print(f"\nUnpaid invoices: {row[0]} invoices, {row[1]:,.2f} NOK")