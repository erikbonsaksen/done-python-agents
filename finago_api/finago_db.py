# finago_db.py
import sqlite3
from typing import List, Iterable, Dict, Any

# Default DB path (relative to project root)
DB_PATH = "tfso-data.db"


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Create tables if they don't exist yet.
    
    NOTE: This is now handled by database/init_db.py
    For backwards compatibility, this function still exists but
    is deprecated. Use: python database/init_db.py instead
    """
    import os
    from pathlib import Path
    
    # Get path to core schema
    project_root = Path(__file__).parent.parent
    schema_file = project_root / "database" / "schemas" / "core_schema.sql"
    
    if not schema_file.exists():
        print("⚠️  Warning: database/schemas/core_schema.sql not found")
        print("   Please run: python database/init_db.py")
        return
    
    # Execute schema file
    with open(schema_file, 'r') as f:
        sql = f.read()
    
    conn.executescript(sql)
    conn.commit()


# -----------------------------
# UPSERT HELPERS
# -----------------------------
def upsert_companies(
    conn: sqlite3.Connection, companies: Iterable[Dict[str, Any]]
) -> int:
    rows = list(companies)
    if not rows:
        return 0

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO companies_sync (
            companyId,
            companyName,
            organizationNo,
            customerNumber,
            email,
            phone,
            dateChanged
        ) VALUES (
            :companyId,
            :companyName,
            :organizationNo,
            :customerNumber,
            :email,
            :phone,
            :dateChanged
        )
        ON CONFLICT(companyId) DO UPDATE SET
            companyName    = excluded.companyName,
            organizationNo = excluded.organizationNo,
            customerNumber = excluded.customerNumber,
            email          = excluded.email,
            phone          = excluded.phone,
            dateChanged    = excluded.dateChanged;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_persons(conn: sqlite3.Connection, persons: Iterable[Dict[str, Any]]) -> int:
    rows = list(persons)
    if not rows:
        return 0

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO persons_sync (
            personId,
            companyId,
            customerId,
            name,
            email,
            phone,
            role,
            dateChanged
        ) VALUES (
            :personId,
            :companyId,
            :customerId,
            :name,
            :email,
            :phone,
            :role,
            :dateChanged
        )
        ON CONFLICT(personId) DO UPDATE SET
            companyId   = excluded.companyId,
            customerId  = excluded.customerId,
            name        = excluded.name,
            email       = excluded.email,
            phone       = excluded.phone,
            role        = excluded.role,
            dateChanged = excluded.dateChanged;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_invoices(
    conn: sqlite3.Connection, invoices: Iterable[Dict[str, Any]]
) -> int:
    """
    UPDATED: Now includes payment status fields and payment date
    """
    rows = list(invoices)
    if not rows:
        return 0

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO invoices_sync (
            invoiceId,
            orderId,
            customerId,
            customerName,
            invoiceNo,
            supplierName,
            supplierOrgNo,
            invoiceText,
            dateInvoiced,
            dateDue,
            datePaid,
            dateChanged,
            totalIncVat,
            totalVat,
            amountPaid,
            balance,
            currencySymbol,
            status,
            externalStatus,
            isCredited
        ) VALUES (
            :invoiceId,
            :orderId,
            :customerId,
            :customerName,
            :invoiceNo,
            :supplierName,
            :supplierOrgNo,
            :invoiceText,
            :dateInvoiced,
            :dateDue,
            :datePaid,
            :dateChanged,
            :totalIncVat,
            :totalVat,
            :amountPaid,
            :balance,
            :currencySymbol,
            :status,
            :externalStatus,
            :isCredited
        )
        ON CONFLICT(invoiceId) DO UPDATE SET
            orderId        = excluded.orderId,
            customerId     = excluded.customerId,
            customerName   = excluded.customerName,
            invoiceNo      = excluded.invoiceNo,
            supplierName   = excluded.supplierName,
            supplierOrgNo  = excluded.supplierOrgNo,
            invoiceText    = excluded.invoiceText,
            dateInvoiced   = excluded.dateInvoiced,
            dateDue        = excluded.dateDue,
            datePaid       = excluded.datePaid,
            dateChanged    = excluded.dateChanged,
            totalIncVat    = excluded.totalIncVat,
            totalVat       = excluded.totalVat,
            amountPaid     = excluded.amountPaid,
            balance        = excluded.balance,
            currencySymbol = excluded.currencySymbol,
            status         = excluded.status,
            externalStatus = excluded.externalStatus,
            isCredited     = excluded.isCredited;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_products(conn, products: List[Dict[str, Any]]) -> int:
    if not products:
        return 0
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT OR REPLACE INTO products_sync (
            productId, productNo, name, description,
            unitPrice, costPrice, isActive, vatCode, dateChanged
        ) VALUES (
            :productId, :productNo, :name, :description,
            :unitPrice, :costPrice, :isActive, :vatCode, :dateChanged
        )
        """,
        products,
    )
    conn.commit()
    return cur.rowcount


def upsert_transactions(conn, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    cur = conn.cursor()
    inserted = 0

    for i, r in enumerate(rows):
        try:
            cur.execute(
                """
                INSERT OR REPLACE INTO transactions_sync (
                    transactionId, voucherNo, lineNo, date,
                    accountNo, amount, debit, credit, currency,
                    description, invoiceNo, linkId, ocr,
                    customerId, projectId, departmentId
                ) VALUES (
                    :transactionId, :voucherNo, :lineNo, :date,
                    :accountNo, :amount, :debit, :credit, :currency,
                    :description, :invoiceNo, :linkId, :ocr,
                    :customerId, :projectId, :departmentId
                )
                """,
                r,
            )
            inserted += 1
        except sqlite3.Error as e:
            print("SQLite error on row index", i, ":", e)
            print("Offending row:", r)
            raise

    conn.commit()
    return inserted


def upsert_accounts(conn, accounts: List[Dict[str, Any]]) -> int:
    if not accounts:
        return 0
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT OR REPLACE INTO accounts_sync (
            accountNo, name, accountType, isActive,
            vatCode, openingBalance, closingBalance
        ) VALUES (
            :accountNo, :name, :accountType, :isActive,
            :vatCode, :openingBalance, :closingBalance
        )
        """,
        accounts,
    )
    conn.commit()
    return cur.rowcount