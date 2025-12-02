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
    """
    cur = conn.cursor()

    # Companies
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS companies_sync (
            companyId       INTEGER PRIMARY KEY,
            companyName     TEXT,
            organizationNo  TEXT,
            customerNumber  TEXT,
            email           TEXT,
            phone           TEXT,
            dateChanged     TEXT
        );
        """
    )

    # Persons / contacts
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS persons_sync (
            personId        INTEGER PRIMARY KEY,
            companyId       INTEGER,
            customerId      INTEGER,
            name            TEXT,
            email           TEXT,
            phone           TEXT,
            role            TEXT,
            dateChanged     TEXT
        );
        """
    )

    # Invoices (AR / AP)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices_sync (
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
        );
        """
    )

    # Products
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products_sync (
            productId      INTEGER PRIMARY KEY,
            productNo      TEXT,
            name           TEXT,
            description    TEXT,
            unitPrice      REAL,
            costPrice      REAL,
            isActive       INTEGER,
            vatCode        TEXT,
            dateChanged    TEXT
        );
        """
    )

    # Transactions (general ledger)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions_sync (
            transactionId  TEXT PRIMARY KEY,
            voucherNo      INTEGER,
            lineNo         INTEGER,
            date           TEXT,
            accountNo      TEXT,
            amount         REAL,
            debit          REAL,
            credit         REAL,
            currency       TEXT,
            description    TEXT,
            invoiceNo      TEXT,
            linkId         INTEGER,
            ocr            TEXT,
            customerId     INTEGER,
            projectId      INTEGER,
            departmentId   INTEGER
        );
        """
    )

    # Accounts (chart of accounts)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts_sync (
            accountNo      TEXT PRIMARY KEY,
            name           TEXT,
            accountType    TEXT,
            isActive       INTEGER,
            vatCode        TEXT,
            openingBalance REAL,
            closingBalance REAL
        );
        """
    )

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
            dateChanged,
            totalIncVat,
            totalVat,
            currencySymbol,
            status,
            externalStatus
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
            :dateChanged,
            :totalIncVat,
            :totalVat,
            :currencySymbol,
            :status,
            :externalStatus
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
            dateChanged    = excluded.dateChanged,
            totalIncVat    = excluded.totalIncVat,
            totalVat       = excluded.totalVat,
            currencySymbol = excluded.currencySymbol,
            status         = excluded.status,
            externalStatus = excluded.externalStatus;
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
