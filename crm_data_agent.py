import json
import os
import sqlite3
import tempfile

from dotenv import load_dotenv

load_dotenv()  # Load .env variables

import pandas as pd
import streamlit as st
from phi.model.openai import OpenAIChat
from phi.agent.duckdb import DuckDbAgent
from phi.tools.pandas import PandasTools

# Path to the SQLite database copied from your Next.js project
DB_PATH = "tfso-data.db"

# Load API key from .env
openai_key = os.getenv("OPENAI_API_KEY")

if not openai_key:
    st.error("OPENAI_API_KEY not found in .env. Please add it before running the app.")
    st.stop()

# Base tables from your Finago connector you want to expose
BASE_TABLES = {
    "companies_sync": "Companies imported from Finago/24SO via Done Finago Connector. Key column: companyId.",
    "invoices_sync": (
        "Invoices imported from Finago/24SO via Done Finago Connector. "
        "Key column: invoiceId. Customer link: customerId → companies_sync.companyId. "
        "Includes amounts (totalIncVat) and dates (dateInvoiced)."
    ),
    "persons_sync": (
        "Persons imported from Finago/24SO via Done Finago Connector. "
        "Key column: personId. Company link: customerId → companies_sync.companyId."
    ),
}


def export_table_to_csv(table_name: str):
    """
    Read a table from SQLite and save it as a temporary CSV for DuckDB.
    Returns (csv_path, dataframe).
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(tmp.name, index=False)
    return tmp.name, df


# --- UI ---

st.title("Done CRM – Finago Data Agent")
st.caption("Using automatic .env API key (OPENAI_API_KEY) on tfso-data.db")


# --- Load SQLite tables and build semantic model ---
semantic_tables = []
dfs: dict[str, pd.DataFrame] = {}

# Load base tables: companies, invoices, persons
for table_name, description in BASE_TABLES.items():
    try:
        csv_path, df = export_table_to_csv(table_name)
    except Exception as e:
        st.error(f"Failed to load table '{table_name}' from {DB_PATH}: {e}")
        continue

    dfs[table_name] = df
    semantic_tables.append(
        {
            "name": table_name,
            "description": description,
            "path": csv_path,
        }
    )

if not semantic_tables:
    st.error(
        "No tables loaded – check that tfso-data.db is in this folder and has data."
    )
    st.stop()

# --- Auto-join companies ↔ invoices ↔ persons into a combined table ---
joined_table_name = "company_invoice_person"

if {"invoices_sync", "companies_sync", "persons_sync"}.issubset(dfs.keys()):
    invoices = dfs["invoices_sync"]
    companies = dfs["companies_sync"]
    persons = dfs["persons_sync"]

    # Join invoices → companies
    joined = invoices.merge(
        companies,
        left_on="customerId",
        right_on="companyId",
        how="left",
        suffixes=("_invoice", "_company"),
    )

    # Join companies → persons (contacts)
    joined = joined.merge(
        persons,
        left_on="companyId",
        right_on="customerId",
        how="left",
        suffixes=("", "_person"),
    )

    tmp_joined = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    joined.to_csv(tmp_joined.name, index=False)

    dfs[joined_table_name] = joined
    semantic_tables.append(
        {
            "name": joined_table_name,
            "description": (
                "Auto-joined view combining invoices_sync, companies_sync and persons_sync. "
                "Use this when you need company, invoice and person information in one query. "
                "Join logic: invoices_sync.customerId → companies_sync.companyId, "
                "companies_sync.companyId → persons_sync.customerId."
            ),
            "path": tmp_joined.name,
        }
    )

# Final semantic model for DuckDB agent
semantic_model = {"tables": semantic_tables}

# --- Preview ---
st.subheader("Preview of Finago CRM dataset")

st.write("Loaded tables:", list(dfs.keys()))

for table_name, df in dfs.items():
    st.markdown(
        f"**{table_name}** – "
        f"{next((t['description'] for t in semantic_tables if t['name'] == table_name), '')}"
    )
    st.dataframe(df.head(10))


# --- Create the DuckDB-based data analysis agent ---
duckdb_agent = DuckDbAgent(
    model=OpenAIChat(model="gpt-4o", api_key=openai_key),
    semantic_model=json.dumps(semantic_model),
    tools=[PandasTools()],
    markdown=True,
    system_prompt=(
        "You are an expert data analyst working for an accounting/CRM company.\n"
        "\n"
        "You have the following tables available:\n"
        "- companies_sync: one row per company (key: companyId). Company name column: companyName.\n"
        "- invoices_sync: one row per invoice (key: invoiceId). Link to company via customerId → companies_sync.companyId.\n"
        "- persons_sync: one row per person/contact (key: personId). Link to company via customerId → companies_sync.companyId.\n"
        "- company_invoice_person: pre-joined view combining invoices, companies and persons on those keys, "
        "including companyId, companyName, totalIncVat, dateInvoiced, personId, etc.\n"
        "\n"
        "Always choose sensible joins:\n"
        "- To relate invoices to companies, join invoices_sync.customerId = companies_sync.companyId.\n"
        "- To relate persons to companies, join persons_sync.customerId = companies_sync.companyId.\n"
        "- For combined insights (company + invoices + persons), prefer querying company_invoice_person directly.\n"
        "\n"
        "When answering questions about customers or companies, ALWAYS include both companyId AND companyName "
        "in your results, not just the ID.\n"
        "\n"
        "You answer questions by writing SQL against these tables, then summarizing the results in clear, "
        "business-friendly language. When helpful, you:\n"
        "- Perform complex data aggregations (sums, averages, counts, group by, windows).\n"
        "- Filter and sort data to highlight key customers, trends or anomalies.\n"
        "- Generate statistical summaries such as distributions, top/bottom segments, growth over time.\n"
        "- Suggest which charts (bar charts, line charts, etc.) would best visualize the results.\n"
        "\n"
        "When you show tabular results, keep them compact and focused on the most relevant columns. "
        "Do NOT include SQL unless the user explicitly asks for it."
    ),
)

# --- Query UI ---
st.subheader("Ask questions about your CRM & invoice data")

default_question = (
    "Show the top 10 customers by total invoice amount in the last 12 months, "
    "with total revenue per customer and number of contacts (persons) per company."
)

user_query = st.text_area("Your question:", value=default_question, height=120)

if st.button("Run analysis"):
    if not user_query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Thinking..."):
            response = duckdb_agent.run(user_query)

        # Phidata returns a response object; get the text content
        try:
            response_text = response.content  # main answer as string
        except AttributeError:
            response_text = str(response)

        st.markdown("### Answer")
        st.markdown(response_text)  # this will render the markdown table nicely
