# agents/subscription_agent.py

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# -----------------------------
# Load .env / API key (not used for this agent yet, but kept if you later add LLM)
# -----------------------------
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")

# -----------------------------
# Paths and helpers
# -----------------------------
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tfso-data.db"))


def export_table_to_csv(table_name: str):
    """Load a SQLite table → temporary CSV (DuckDB reads CSV easiest)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(tmp.name, index=False)
    return tmp.name, df


# -----------------------------
# Load base tables
# -----------------------------
BASE_TABLES = ["transactions_sync", "accounts_sync"]

semantic_tables = []
dfs: dict[str, pd.DataFrame] = {}

for tbl in BASE_TABLES:
    try:
        path, df = export_table_to_csv(tbl)
    except Exception as e:
        st.error(f"Failed to load {tbl} from {DB_PATH}: {e}")
        continue

    dfs[tbl] = df
    semantic_tables.append(
        {
            "name": tbl,
            "description": f"{tbl} from Finago/24SO sync.",
            "path": path,
        }
    )

# -----------------------------
# Create joined table for easier subscription detection: tx_account
# -----------------------------
if {"transactions_sync", "accounts_sync"}.issubset(dfs.keys()):
    tx = dfs["transactions_sync"]
    acc = dfs["accounts_sync"]

    # Join: transactions ←→ accounts on accountNo
    merged = tx.merge(
        acc,
        on="accountNo",
        how="left",
        suffixes=("", "_account"),
    )

    tmp_joined = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    merged.to_csv(tmp_joined.name, index=False)

    dfs["tx_account"] = merged

    semantic_tables.append(
        {
            "name": "tx_account",
            "description": (
                "Journal transactions joined with accounts. "
                "Join: transactions_sync.accountNo = accounts_sync.accountNo. "
                "Important columns: date, amount, debit, credit, description, "
                "accountNo, name (account name)."
            ),
            "path": tmp_joined.name,
        }
    )

# -----------------------------
# UI
# -----------------------------
st.title("💳 Subscription Detection Agent (24SO/Finago)")
st.caption("Detects recurring SaaS / telecom / cloud subscriptions from your accounting data.")

st.subheader("Available tables loaded")
st.write(list(dfs.keys()))

st.subheader("Preview sample data (first 10 rows from joined table)")
if "tx_account" in dfs:
    st.dataframe(dfs["tx_account"].head(10))
else:
    st.warning("Joined table 'tx_account' not available. Check DB or sync process.")

# -----------------------------
# Subscription detection with fixed SQL
# -----------------------------
st.subheader("Run subscription detection")

if st.button("Run Subscription Analysis"):
    if "tx_account" not in dfs:
        st.error("tx_account not available – make sure transactions_sync and accounts_sync loaded correctly.")
    else:
        with st.spinner("Detecting recurring subscriptions from transaction patterns..."):
            # 1) Create in-memory DuckDB and register CSVs as tables
            con = duckdb.connect()

            for t in semantic_tables:
                name = t["name"]
                path = t["path"]
                # Register each CSV as a DuckDB table
                con.execute(
                    f"""
                    CREATE OR REPLACE TABLE {name} AS
                    SELECT * FROM read_csv_auto('{path}', header=True);
                    """
                )

            # 2) Fixed SQL that we know works in DuckDB
            sql = """
            WITH tx AS (
                SELECT
                    CAST(date AS DATE)       AS tx_date,
                    amount,
                    accountNo,
                    name                     AS accountName,
                    description
                FROM tx_account
                WHERE description IS NOT NULL
                  AND description <> ''
            )
            SELECT
                lower(trim(description))                   AS vendor_name,
                accountNo,
                accountName,
                MIN(tx_date)                               AS first_date,
                MAX(tx_date)                               AS last_date,
                COUNT(*)                                   AS txn_count,
                COUNT(DISTINCT strftime(tx_date, '%Y-%m')) AS active_months,
                AVG(amount)                                AS avg_amount,
                STDDEV_POP(amount)                         AS amount_stddev
            FROM tx
            GROUP BY vendor_name, accountNo, accountName
            HAVING
                active_months >= 3     -- at least 3 distinct months
                AND txn_count   >= 3   -- at least 3 transactions
            ORDER BY avg_amount DESC
            LIMIT 200;
            """

            df = con.execute(sql).df()

            # 3) Post-process in pandas: mark likely active subs
            if not df.empty:
                # Ensure first_date / last_date are real dates
                df["first_date"] = pd.to_datetime(df["first_date"]).dt.date
                df["last_date"] = pd.to_datetime(df["last_date"]).dt.date

                # active if last_date within last 90 days
                cutoff = datetime.today().date() - timedelta(days=90)
                df["is_active"] = df["last_date"] >= cutoff

                # nicer column names
                df.rename(
                    columns={
                        "vendor_name": "Vendor Name",
                        "accountNo": "Account No",
                        "accountName": "Account Name",
                        "first_date": "First Date",
                        "last_date": "Last Date",
                        "txn_count": "Transaction Count",
                        "active_months": "Active Months",
                        "avg_amount": "Average Amount",
                        "amount_stddev": "Amount StdDev",
                        "is_active": "Likely Active Now",
                    },
                    inplace=True,
                )

                st.markdown("### Detected recurring subscription-like vendors")
                st.dataframe(df)

            else:
                st.info("No recurring patterns found that match the criteria (≥3 months and ≥3 transactions).")
