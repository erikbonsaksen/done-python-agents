-- Core Database Schema
-- Base tables for Finago data sync

-- Companies (Customers/Suppliers)
CREATE TABLE IF NOT EXISTS companies_sync (
    companyId       INTEGER PRIMARY KEY,
    companyName     TEXT,
    organizationNo  TEXT,
    customerNumber  TEXT,
    email           TEXT,
    phone           TEXT,
    dateChanged     TEXT
);

-- Persons / Contacts
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

-- Invoices (AR / AP)
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
    dateDue         TEXT,
    datePaid        TEXT,
    dateChanged     TEXT,
    totalIncVat     REAL,
    totalVat        REAL,
    amountPaid      REAL DEFAULT 0,
    balance         REAL DEFAULT 0,
    currencySymbol  TEXT,
    status          TEXT,
    externalStatus  TEXT,
    isCredited      INTEGER DEFAULT 0
);

-- Products
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

-- Transactions (General Ledger)
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

-- Accounts (Chart of Accounts)
CREATE TABLE IF NOT EXISTS accounts_sync (
    accountNo      TEXT PRIMARY KEY,
    name           TEXT,
    accountType    TEXT,
    isActive       INTEGER,
    vatCode        TEXT,
    openingBalance REAL,
    closingBalance REAL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_orgno ON companies_sync(organizationNo);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices_sync(customerId);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices_sync(status);
CREATE INDEX IF NOT EXISTS idx_invoices_balance ON invoices_sync(balance);
CREATE INDEX IF NOT EXISTS idx_invoices_date_invoiced ON invoices_sync(dateInvoiced);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices_sync(dateDue);
CREATE INDEX IF NOT EXISTS idx_invoices_paid_date ON invoices_sync(datePaid);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions_sync(date);
CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions_sync(customerId);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions_sync(accountNo);