#!/usr/bin/env python3
"""
Revenue Seasonality Analyzer

Analyzes your historical revenue to detect:
- Monthly patterns (which months are strong/weak)
- Quarterly trends
- Year-over-year growth
- Seasonal multipliers for forecasting
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_PATH = "tfso-data.db"

def analyze_revenue_seasonality():
    print("\n" + "="*70)
    print("  REVENUE SEASONALITY ANALYSIS")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load all invoices
    query = """
        SELECT 
            dateInvoiced,
            totalIncVat,
            status
        FROM invoices_sync
        WHERE dateInvoiced IS NOT NULL
        ORDER BY dateInvoiced
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if len(df) == 0:
        print("\n⚠️  No invoice data found")
        return
    
    df['dateInvoiced'] = pd.to_datetime(df['dateInvoiced'])
    df['year'] = df['dateInvoiced'].dt.year
    df['month'] = df['dateInvoiced'].dt.month
    df['month_name'] = df['dateInvoiced'].dt.strftime('%B')
    df['quarter'] = df['dateInvoiced'].dt.quarter
    df['year_month'] = df['dateInvoiced'].dt.to_period('M')
    
    # ========================================
    # 1. OVERALL MONTHLY REVENUE
    # ========================================
    print("\n📊 1. MONTHLY REVENUE HISTORY\n")
    
    monthly_revenue = df.groupby('year_month')['totalIncVat'].sum()
    
    print("   Last 12 months:")
    for month, revenue in monthly_revenue.tail(12).items():
        print(f"     {month}  {revenue:>12,.2f} NOK")
    
    avg_monthly = monthly_revenue.mean()
    print(f"\n   Overall Average: {avg_monthly:>12,.2f} NOK/month")
    
    # ========================================
    # 2. SEASONAL PATTERNS BY MONTH
    # ========================================
    print("\n📊 2. SEASONAL PATTERNS BY MONTH\n")
    
    monthly_avg = df.groupby('month')['totalIncVat'].agg(['sum', 'count', 'mean'])
    monthly_avg['pct_of_avg'] = (monthly_avg['mean'] / monthly_avg['mean'].mean()) * 100
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    print("   Month      Avg Revenue    vs Overall Avg    Multiplier")
    print("   " + "-"*60)
    
    seasonal_multipliers = {}
    
    for month_num in range(1, 13):
        if month_num in monthly_avg.index:
            row = monthly_avg.loc[month_num]
            multiplier = row['pct_of_avg'] / 100
            seasonal_multipliers[month_num] = multiplier
            
            indicator = "🔥" if multiplier > 1.1 else "❄️" if multiplier < 0.9 else "  "
            
            print(f"   {month_names[month_num-1]:3}  {row['mean']:>13,.2f}  "
                  f"{row['pct_of_avg']:>13.1f}%  {multiplier:>10.2f}x {indicator}")
        else:
            seasonal_multipliers[month_num] = 1.0
            print(f"   {month_names[month_num-1]:3}  {'No data':>13}  "
                  f"{'N/A':>13}  {'1.00x':>10}")
    
    # ========================================
    # 3. QUARTERLY PATTERNS
    # ========================================
    print("\n📊 3. QUARTERLY PATTERNS\n")
    
    quarterly = df.groupby(['year', 'quarter'])['totalIncVat'].sum().reset_index()
    quarterly_avg = df.groupby('quarter')['totalIncVat'].mean()
    
    print("   Quarter    Avg Monthly Revenue    vs Overall")
    print("   " + "-"*50)
    
    for q in range(1, 5):
        if q in quarterly_avg.index:
            q_avg = quarterly_avg[q]
            vs_overall = (q_avg / avg_monthly) * 100
            indicator = "🔥" if vs_overall > 110 else "❄️" if vs_overall < 90 else "  "
            print(f"   Q{q}     {q_avg:>16,.2f}     {vs_overall:>7.1f}% {indicator}")
    
    # ========================================
    # 4. GROWTH TREND
    # ========================================
    print("\n📊 4. YEAR-OVER-YEAR GROWTH\n")
    
    yearly = df.groupby('year')['totalIncVat'].sum()
    
    if len(yearly) > 1:
        print("   Year      Total Revenue      vs Previous Year")
        print("   " + "-"*50)
        
        prev_year_rev = None
        for year, revenue in yearly.items():
            if prev_year_rev:
                growth = ((revenue - prev_year_rev) / prev_year_rev) * 100
                indicator = "📈" if growth > 0 else "📉"
                print(f"   {year}  {revenue:>14,.2f}     {growth:>+7.1f}% {indicator}")
            else:
                print(f"   {year}  {revenue:>14,.2f}     {'N/A':>7}")
            prev_year_rev = revenue
    
    # ========================================
    # 5. RECOMMENDATIONS
    # ========================================
    print("\n📊 5. FORECASTING RECOMMENDATIONS\n")
    
    # Find strongest and weakest months
    strong_months = [m for m, mult in seasonal_multipliers.items() if mult > 1.1]
    weak_months = [m for m, mult in seasonal_multipliers.items() if mult < 0.9]
    
    print(f"   Baseline Monthly Revenue: {avg_monthly:,.0f} NOK")
    
    if strong_months:
        strong_names = [month_names[m-1] for m in strong_months]
        print(f"   💪 Strong Months: {', '.join(strong_names)}")
    
    if weak_months:
        weak_names = [month_names[m-1] for m in weak_months]
        print(f"   💤 Weak Months: {', '.join(weak_names)}")
    
    # Calculate next 3 months multipliers
    print("\n   Seasonal Multipliers for Next 3 Months:")
    
    today = datetime.now()
    for offset in range(3):
        future_month = (today.month + offset - 1) % 12 + 1
        future_year = today.year + ((today.month + offset - 1) // 12)
        multiplier = seasonal_multipliers.get(future_month, 1.0)
        month_name = month_names[future_month - 1]
        
        forecasted = avg_monthly * multiplier
        
        print(f"     {month_name} {future_year}: {multiplier:.2f}x = {forecasted:,.0f} NOK")
    
    print("\n" + "="*70)
    print("  ANALYSIS COMPLETE")
    print("="*70 + "\n")
    
    return {
        'baseline_monthly': avg_monthly,
        'seasonal_multipliers': seasonal_multipliers,
        'strong_months': strong_months,
        'weak_months': weak_months
    }


if __name__ == "__main__":
    analyze_revenue_seasonality()