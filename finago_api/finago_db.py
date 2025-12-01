# finago_api/finago_db.py
import sqlite3
from typing import Iterable, Dict, Any

# Default DB path (relative to project root)
DB_PATH = "tfso-data.db"


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    """
    Open a SQLite connection to tfso-data.db (or custom path).
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Create tables if they don't exist yet.
    Schemas are aligned with what the agent expects:
      - companies_sync
      - persons_sync
      - invoices_sync
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

    # Invoices
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices_sync (
            invoiceId       INTEGER PRIMARY KEY,
            orderId         INTEGER,
            customerId      INTEGER,
            customerName    TEXT,
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

    conn.commit()


def upsert_companies(conn: sqlite3.Connection, companies: Iterable[Dict[str, Any]]) -> int:
    """
    Upsert list of company dicts into companies_sync.
    Expects keys:
      companyId, companyName, organizationNo, customerNumber, email, phone, dateChanged
    """
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
    """
    Upsert list of person dicts into persons_sync.
    Expects keys:
      personId, companyId, customerId, name, email, phone, role, dateChanged
    """
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


def upsert_invoices(conn: sqlite3.Connection, invoices: Iterable[Dict[str, Any]]) -> int:
    """
    Upsert list of invoice dicts into invoices_sync.
    Expects keys:
      invoiceId, orderId, customerId, customerName, dateInvoiced,
      dateChanged, totalIncVat, totalVat, currencySymbol, status, externalStatus
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
