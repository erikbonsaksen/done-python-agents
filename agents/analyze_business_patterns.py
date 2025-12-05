#!/usr/bin/env python3
"""
Business Pattern Analyzer

Analyzes your actual financial data to extract:
- Real monthly expenses by category
- Payroll patterns
- Fixed vs variable costs
- Revenue patterns
- Cash flow seasonality

This data will be used to build a realistic cash flow forecaster.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "tfso-data.db"


def analyze_business_patterns():
    print("\n" + "=" * 70)
    print("  BUSINESS PATTERN ANALYSIS")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)

    # =========================================
    # 1. ANALYZE TRANSACTIONS BY ACCOUNT TYPE
    # =========================================
    print("\n📊 1. TRANSACTION ANALYSIS (Last 12 Months)\n")

    # Load transactions
    query = """
        SELECT 
            t.date,
            t.accountNo,
            a.name as accountName,
            a.accountType,
            t.amount,
            t.debit,
            t.credit,
            t.description
        FROM transactions_sync t
        LEFT JOIN accounts_sync a ON t.accountNo = a.accountNo
        WHERE t.date >= date('now', '-365 days')
        ORDER BY t.date DESC
    """

    df = pd.read_sql_query(query, conn)

    if len(df) == 0:
        print("   ⚠️  No transactions found in last 12 months")
    else:
        print(f"   Total transactions: {len(df):,}")

        # Group by account type
        print(f"\n   By Account Type:")
        account_summary = (
            df.groupby("accountType")
            .agg({"amount": "sum", "accountNo": "count"})
            .round(2)
        )

        for acc_type, row in account_summary.iterrows():
            if pd.notna(acc_type):
                print(
                    f"     {acc_type:20} {row['accountNo']:>6} txns  {row['amount']:>15,.2f} NOK"
                )

    # =========================================
    # 2. MONTHLY EXPENSE PATTERNS
    # =========================================
    print(f"\n📊 2. MONTHLY EXPENSE PATTERNS\n")

    # Identify expense accounts (typically 4xxx-8xxx in Norwegian accounting)
    # Adjust based on your chart of accounts
    expense_accounts = df[
        (df["accountNo"].str.match(r"^[4-8]", na=False))
        | (df["accountType"].str.contains("expense|cost|utgift", case=False, na=False))
    ].copy()

    if len(expense_accounts) > 0:
        expense_accounts["month"] = pd.to_datetime(
            expense_accounts["date"]
        ).dt.to_period("M")
        monthly_expenses = expense_accounts.groupby("month")["amount"].sum().abs()

        print(f"   Last 6 months expenses:")
        for month, amount in monthly_expenses.tail(6).items():
            print(f"     {month}  {amount:>12,.2f} NOK")

        print(f"\n   Summary:")
        print(f"     Average: {monthly_expenses.mean():>12,.2f} NOK")
        print(f"     Median:  {monthly_expenses.median():>12,.2f} NOK")
        print(f"     Min:     {monthly_expenses.min():>12,.2f} NOK")
        print(f"     Max:     {monthly_expenses.max():>12,.2f} NOK")

    # =========================================
    # 3. IDENTIFY RECURRING COSTS
    # =========================================
    print(f"\n📊 3. RECURRING COSTS (Appear Every Month)\n")

    # Group by description/account to find recurring items
    recurring = (
        df.groupby(["accountNo", "accountName", "description"])
        .agg({"date": "count", "amount": ["mean", "std"]})
        .round(2)
    )

    recurring.columns = ["frequency", "avg_amount", "std_amount"]
    recurring = recurring[recurring["frequency"] >= 6]  # Appears at least 6 times
    recurring = recurring.sort_values("avg_amount", key=abs, ascending=False)

    if len(recurring) > 0:
        print(f"   Top 10 recurring expenses:")
        for idx, row in recurring.head(10).iterrows():
            acc_no, acc_name, desc = idx
            print(
                f"     {acc_name[:30]:30}  {row['frequency']:>3}x  {row['avg_amount']:>10,.2f} NOK"
            )

    # =========================================
    # 4. REVENUE ANALYSIS
    # =========================================
    print(f"\n📊 4. REVENUE ANALYSIS\n")

    # Load invoices for revenue
    invoice_query = """
        SELECT 
            dateInvoiced,
            datePaid,
            totalIncVat,
            status
        FROM invoices_sync
        WHERE dateInvoiced >= date('now', '-365 days')
        ORDER BY dateInvoiced DESC
    """

    invoices = pd.read_sql_query(invoice_query, conn)
    invoices["dateInvoiced"] = pd.to_datetime(invoices["dateInvoiced"])
    invoices["month"] = invoices["dateInvoiced"].dt.to_period("M")

    monthly_revenue = invoices.groupby("month")["totalIncVat"].sum()

    print(f"   Last 6 months revenue (invoiced):")
    for month, amount in monthly_revenue.tail(6).items():
        print(f"     {month}  {amount:>12,.2f} NOK")

    print(f"\n   Summary:")
    print(f"     Average: {monthly_revenue.mean():>12,.2f} NOK/month")
    print(f"     Median:  {monthly_revenue.median():>12,.2f} NOK/month")

    # =========================================
    # 5. CASH CONVERSION ANALYSIS
    # =========================================
    print(f"\n📊 5. CASH CONVERSION METRICS\n")

    paid_invoices = invoices[invoices["status"] == "Paid"].copy()

    if len(paid_invoices) > 0:
        paid_invoices["datePaid"] = pd.to_datetime(paid_invoices["datePaid"])
        paid_invoices["days_to_payment"] = (
            paid_invoices["datePaid"] - paid_invoices["dateInvoiced"]
        ).dt.days

        avg_days = paid_invoices["days_to_payment"].median()
        print(f"   Average Days to Payment: {avg_days:.0f} days")
        print(f"   (Customers pay ~{avg_days:.0f} days after invoice)")

    # =========================================
    # 6. CURRENT POSITION
    # =========================================
    print(f"\n📊 6. CURRENT FINANCIAL POSITION\n")

    # Outstanding receivables
    unpaid = invoices[invoices["status"] == "Unpaid"]["totalIncVat"].sum()
    print(f"   Outstanding Receivables: {unpaid:>12,.2f} NOK")

    # Recent monthly burn
    cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=90)
    recent_expenses = expense_accounts[
        pd.to_datetime(expense_accounts['date']).dt.tz_localize(None) >= cutoff_date.tz_localize(None)
    ]['amount'].sum() / 3

    if recent_expenses > 0:
        recent_expenses = abs(recent_expenses)

    print(f"   Recent Burn Rate:        {recent_expenses:>12,.2f} NOK/month")

    # Cash runway (if we had cash balance)
    print(f"\n   If all receivables collected:")
    print(f"     Cash Runway: {unpaid / recent_expenses:.1f} months")

    # =========================================
    # 7. RECOMMENDATIONS
    # =========================================
    print(f"\n📊 7. RECOMMENDATIONS FOR CASH FLOW MODEL\n")

    print(f"   Use these values for forecaster:")
    print(f"     Monthly Expense Baseline: {monthly_expenses.median():,.2f} NOK")
    print(f"     Payment Timing: {avg_days:.0f} days average")
    print(f"     Expense Volatility: ±{monthly_expenses.std():,.2f} NOK")

    print(f"\n   Key accounts to monitor:")
    if len(recurring) > 0:
        for idx, row in recurring.head(5).iterrows():
            acc_no, acc_name, desc = idx
            print(f"     - {acc_name[:40]:40} {row['avg_amount']:>10,.2f} NOK/month")

    print("\n" + "=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70 + "\n")

    conn.close()

    return {
        "monthly_expense_avg": (
            monthly_expenses.median() if len(expense_accounts) > 0 else 0
        ),
        "monthly_expense_std": (
            monthly_expenses.std() if len(expense_accounts) > 0 else 0
        ),
        "monthly_revenue_avg": monthly_revenue.mean() if len(invoices) > 0 else 0,
        "avg_days_to_payment": avg_days if len(paid_invoices) > 0 else 30,
        "outstanding_receivables": unpaid,
    }


if __name__ == "__main__":
    stats = analyze_business_patterns()
