#!/usr/bin/env python3
"""
Financial Dashboard - Streamlit App

Displays metrics calculated from Finago data in an interactive dashboard.

Usage:
    streamlit run dashboard_app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Financial Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better card styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .alert-card {
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid;
    }
    .alert-high {
        background-color: #fee;
        border-left-color: #d00;
    }
    .alert-medium {
        background-color: #ffeaa7;
        border-left-color: #fdcb6e;
    }
    .alert-low {
        background-color: #dfe6e9;
        border-left-color: #74b9ff;
    }
    </style>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def get_connection(db_path="tfso-data.db"):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def format_currency(value, currency="NOK"):
    """Format currency values"""
    if value is None:
        return f"0.00 {currency}"
    return f"{value:,.2f} {currency}"

def format_number(value):
    """Format numbers with thousand separators"""
    if value is None:
        return "0"
    return f"{value:,.0f}"

# ============================================
# DATA LOADING FUNCTIONS
# ============================================

def load_metrics_by_category(conn, category):
    """Load all metrics for a specific category"""
    cur = conn.cursor()
    cur.execute("""
        SELECT metric_name, metric_value, metric_unit, metadata
        FROM dashboard_metrics
        WHERE metric_category = ?
        ORDER BY metric_name
    """, (category,))
    
    metrics = {}
    for row in cur.fetchall():
        metrics[row['metric_name']] = {
            'value': row['metric_value'],
            'unit': row['metric_unit'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
        }
    return metrics

def load_alerts(conn, severity=None, limit=10):
    """Load alerts from database"""
    cur = conn.cursor()
    query = """
        SELECT alert_type, severity, title, description, amount, 
               due_date, created_at
        FROM dashboard_alerts
        WHERE is_resolved = 0
    """
    params = []
    
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    
    query += " ORDER BY severity DESC, created_at DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]

def load_customer_metrics(conn, limit=10):
    """Load top customers"""
    cur = conn.cursor()
    cur.execute("""
        SELECT customer_name, total_revenue, invoice_count, 
               avg_payment_days, payment_status
        FROM customer_metrics
        ORDER BY total_revenue DESC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cur.fetchall()]

def load_revenue_timeseries(conn):
    """Load revenue time series data"""
    cur = conn.cursor()
    cur.execute("""
        SELECT date, value
        FROM metrics_timeseries
        WHERE metric_name = 'revenue_monthly'
        ORDER BY date
    """)
    rows = cur.fetchall()
    if rows:
        df = pd.DataFrame(rows, columns=['date', 'value'])
        df['date'] = pd.to_datetime(df['date'])
        return df
    return pd.DataFrame()

# ============================================
# MAIN DASHBOARD
# ============================================

def main():
    # Sidebar
    with st.sidebar:
        st.title("📊 Dashboard")
        st.markdown("---")
        
        # Database selector
        db_path = st.text_input("Database Path", value="tfso-data.db")
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Navigation")
        page = st.radio(
            "Select View",
            ["Overview", "Financial Details", "Customers", "Alerts"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("### About")
        st.caption("Financial metrics from Finago ERP")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Main content
    conn = get_connection(db_path)
    
    if page == "Overview":
        show_overview(conn)
    elif page == "Financial Details":
        show_financial_details(conn)
    elif page == "Customers":
        show_customers(conn)
    elif page == "Alerts":
        show_alerts(conn)

# ============================================
# OVERVIEW PAGE
# ============================================

def show_overview(conn):
    st.title("📊 Financial Overview")
    st.markdown("---")
    
    # Load metrics
    financial_metrics = load_metrics_by_category(conn, "financial")
    operational_metrics = load_metrics_by_category(conn, "operational")
    customer_metrics = load_metrics_by_category(conn, "customer")
    
    # Key Metrics Row
    st.subheader("💰 Key Financial Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        revenue = financial_metrics.get("total_revenue_90d", {}).get("value", 0)
        st.metric(
            "Revenue (90 days)",
            format_currency(revenue),
            help="Total revenue from last 90 days"
        )
    
    with col2:
        receivables = financial_metrics.get("outstanding_receivables", {}).get("value", 0)
        st.metric(
            "Outstanding Receivables",
            format_currency(receivables),
            help="Total unpaid invoices"
        )
    
    with col3:
        avg_invoice = financial_metrics.get("avg_invoice_value", {}).get("value", 0)
        st.metric(
            "Avg Invoice Value",
            format_currency(avg_invoice),
            help="Average invoice amount"
        )
    
    with col4:
        cash_flow = financial_metrics.get("net_cash_flow_90d", {}).get("value", 0)
        delta_color = "normal" if cash_flow >= 0 else "inverse"
        st.metric(
            "Net Cash Flow (90d)",
            format_currency(cash_flow),
            delta=f"{cash_flow:,.0f}" if cash_flow != 0 else None,
            delta_color=delta_color,
            help="Net cash inflow/outflow"
        )
    
    st.markdown("---")
    
    # Aging Analysis
    st.subheader("📅 Accounts Receivable Aging")
    col1, col2, col3, col4 = st.columns(4)
    
    aging_data = []
    with col1:
        current = financial_metrics.get("aging_current", {}).get("value", 0)
        st.metric("Current (0-30 days)", format_currency(current))
        aging_data.append({"period": "Current", "amount": current})
    
    with col2:
        days_30 = financial_metrics.get("aging_30_days", {}).get("value", 0)
        st.metric("30-60 days", format_currency(days_30))
        aging_data.append({"period": "30-60 days", "amount": days_30})
    
    with col3:
        days_60 = financial_metrics.get("aging_60_days", {}).get("value", 0)
        st.metric("60-90 days", format_currency(days_60))
        aging_data.append({"period": "60-90 days", "amount": days_60})
    
    with col4:
        days_90_plus = financial_metrics.get("aging_90_plus_days", {}).get("value", 0)
        st.metric("90+ days", format_currency(days_90_plus))
        aging_data.append({"period": "90+ days", "amount": days_90_plus})
    
    # Aging chart
    if aging_data:
        df_aging = pd.DataFrame(aging_data)
        fig = px.bar(
            df_aging, 
            x='period', 
            y='amount',
            title="Aging Distribution",
            labels={'amount': 'Amount (NOK)', 'period': 'Period'},
            color='amount',
            color_continuous_scale='RdYlGn_r'
        )
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Operational & Customer Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Operational Metrics")
        
        invoice_count = operational_metrics.get("invoice_count_90d", {}).get("value", 0)
        overdue_count = operational_metrics.get("overdue_invoice_count", {}).get("value", 0)
        avg_payment = operational_metrics.get("avg_payment_days", {}).get("value", 0)
        
        st.metric("Invoices (90d)", format_number(invoice_count))
        st.metric("Overdue Invoices", format_number(overdue_count))
        if avg_payment:
            st.metric("Avg Payment Time", f"{avg_payment:.0f} days")
    
    with col2:
        st.subheader("👥 Customer Metrics")
        
        active_customers = customer_metrics.get("active_customers", {}).get("value", 0)
        avg_customer_rev = customer_metrics.get("avg_customer_revenue", {}).get("value", 0)
        
        st.metric("Active Customers", format_number(active_customers))
        st.metric("Avg Customer Revenue", format_currency(avg_customer_rev))
    
    st.markdown("---")
    
    # Alerts Preview
    st.subheader("🚨 Recent Alerts")
    alerts = load_alerts(conn, limit=5)
    
    if alerts:
        for alert in alerts:
            severity_class = f"alert-{alert['severity']}"
            emoji = "🔴" if alert['severity'] == 'high' else "🟡" if alert['severity'] == 'medium' else "🔵"
            
            st.markdown(f"""
                <div class="alert-card {severity_class}">
                    <strong>{emoji} {alert['title']}</strong><br>
                    <small>{alert['description']}</small>
                    {f"<br><small>Amount: {format_currency(alert['amount'])}</small>" if alert['amount'] else ""}
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No alerts at the moment")
    
    if len(alerts) >= 5:
        st.markdown("👉 [View all alerts](#)")

# ============================================
# FINANCIAL DETAILS PAGE
# ============================================

def show_financial_details(conn):
    st.title("💰 Financial Details")
    st.markdown("---")
    
    financial_metrics = load_metrics_by_category(conn, "financial")
    
    # Revenue Trend
    st.subheader("📈 Revenue Trend")
    df_revenue = load_revenue_timeseries(conn)
    
    if not df_revenue.empty:
        fig = px.line(
            df_revenue,
            x='date',
            y='value',
            title="Monthly Revenue",
            labels={'value': 'Revenue (NOK)', 'date': 'Month'}
        )
        fig.update_traces(line_color='#00cc96', line_width=3)
        fig.update_layout(height=400, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No time series data available yet")
    
    st.markdown("---")
    
    # Detailed Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💵 Cash Flow Details")
        
        cash_flow_data = financial_metrics.get("net_cash_flow_90d", {})
        metadata = cash_flow_data.get("metadata", {})
        
        if metadata:
            inflow = metadata.get("inflow", 0)
            outflow = metadata.get("outflow", 0)
            
            st.metric("Total Inflow", format_currency(inflow))
            st.metric("Total Outflow", format_currency(outflow))
            st.metric("Net Flow", format_currency(inflow - outflow))
            
            # Cash flow chart
            df_flow = pd.DataFrame({
                'Type': ['Inflow', 'Outflow'],
                'Amount': [inflow, outflow]
            })
            fig = px.bar(
                df_flow,
                x='Type',
                y='Amount',
                color='Type',
                color_discrete_map={'Inflow': '#00cc96', 'Outflow': '#ef553b'}
            )
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Aging Analysis Details")
        
        aging_metrics = [
            ("Current (0-30)", "aging_current"),
            ("30-60 days", "aging_30_days"),
            ("60-90 days", "aging_60_days"),
            ("90+ days", "aging_90_plus_days")
        ]
        
        total_ar = 0
        aging_breakdown = []
        
        for label, key in aging_metrics:
            value = financial_metrics.get(key, {}).get("value", 0)
            total_ar += value
            aging_breakdown.append({"Period": label, "Amount": value})
        
        if total_ar > 0:
            df_aging = pd.DataFrame(aging_breakdown)
            df_aging['Percentage'] = (df_aging['Amount'] / total_ar * 100).round(1)
            
            fig = px.pie(
                df_aging,
                values='Amount',
                names='Period',
                title='AR Distribution by Age',
                hole=0.4
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(
                df_aging,
                use_container_width=True,
                hide_index=True
            )

# ============================================
# CUSTOMERS PAGE
# ============================================

def show_customers(conn):
    st.title("👥 Customer Insights")
    st.markdown("---")
    
    customers = load_customer_metrics(conn, limit=20)
    
    if not customers:
        st.warning("No customer data available")
        return
    
    # Top Customers
    st.subheader("🏆 Top Customers by Revenue")
    
    df_customers = pd.DataFrame(customers)
    
    # Top 10 chart
    df_top10 = df_customers.head(10)
    fig = px.bar(
        df_top10,
        x='total_revenue',
        y='customer_name',
        orientation='h',
        title='Top 10 Customers',
        labels={'total_revenue': 'Revenue (NOK)', 'customer_name': 'Customer'},
        color='total_revenue',
        color_continuous_scale='Viridis'
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Customer Details Table
    st.subheader("📋 Customer Details")
    
    # Format the dataframe for display
    df_display = df_customers.copy()
    df_display['total_revenue'] = df_display['total_revenue'].apply(lambda x: f"{x:,.2f}")
    df_display['avg_payment_days'] = df_display['avg_payment_days'].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "N/A"
    )
    
    # Rename columns
    df_display.columns = ['Customer', 'Revenue (NOK)', 'Invoices', 'Avg Payment (days)', 'Status']
    
    # Color code payment status
    def color_status(val):
        colors = {
            'fast_payer': 'background-color: #d4edda',
            'average': 'background-color: #fff3cd',
            'slow_payer': 'background-color: #f8d7da'
        }
        return colors.get(val, '')
    
    st.dataframe(
        df_display.style.applymap(color_status, subset=['Status']),
        use_container_width=True,
        hide_index=True
    )
    
    # Payment behavior distribution
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💳 Payment Behavior")
        status_counts = df_customers['payment_status'].value_counts()
        
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title='Customer Payment Status Distribution',
            color=status_counts.index,
            color_discrete_map={
                'fast_payer': '#28a745',
                'average': '#ffc107',
                'slow_payer': '#dc3545'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Statistics")
        st.metric("Total Customers", len(customers))
        st.metric("Total Revenue", format_currency(df_customers['total_revenue'].sum()))
        st.metric("Avg Revenue per Customer", format_currency(df_customers['total_revenue'].mean()))
        
        if df_customers['avg_payment_days'].notna().any():
            st.metric(
                "Avg Payment Days (All)", 
                f"{df_customers['avg_payment_days'].mean():.0f} days"
            )

# ============================================
# ALERTS PAGE
# ============================================

def show_alerts(conn):
    st.title("🚨 Alerts & Action Items")
    st.markdown("---")
    
    # Alert filters
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        severity_filter = st.selectbox(
            "Filter by Severity",
            ["All", "high", "medium", "low"],
            index=0
        )
    
    with col2:
        alert_type_filter = st.selectbox(
            "Filter by Type",
            ["All", "overdue_invoice", "low_cash", "unusual_transaction"],
            index=0
        )
    
    with col3:
        limit = st.number_input("Show", min_value=5, max_value=100, value=20, step=5)
    
    # Load alerts
    severity = None if severity_filter == "All" else severity_filter
    alerts = load_alerts(conn, severity=severity, limit=limit)
    
    if alert_type_filter != "All":
        alerts = [a for a in alerts if a['alert_type'] == alert_type_filter]
    
    # Summary metrics
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    all_alerts = load_alerts(conn, limit=1000)
    
    with col1:
        st.metric("Total Alerts", len(all_alerts))
    with col2:
        high_count = sum(1 for a in all_alerts if a['severity'] == 'high')
        st.metric("High Priority", high_count)
    with col3:
        medium_count = sum(1 for a in all_alerts if a['severity'] == 'medium')
        st.metric("Medium Priority", medium_count)
    with col4:
        total_amount = sum(a['amount'] for a in all_alerts if a['amount'])
        st.metric("Total at Risk", format_currency(total_amount))
    
    st.markdown("---")
    
    # Alert list
    if alerts:
        for i, alert in enumerate(alerts):
            severity_emoji = {
                'high': '🔴',
                'medium': '🟡',
                'low': '🔵'
            }
            
            with st.expander(
                f"{severity_emoji.get(alert['severity'], '⚪')} {alert['title']} "
                f"({alert['severity'].upper()})",
                expanded=(i < 3)  # Expand first 3
            ):
                st.markdown(f"**Type:** {alert['alert_type']}")
                st.markdown(f"**Description:** {alert['description']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if alert['amount']:
                        st.markdown(f"**Amount:** {format_currency(alert['amount'])}")
                with col2:
                    if alert['due_date']:
                        st.markdown(f"**Due Date:** {alert['due_date']}")
                
                st.caption(f"Created: {alert['created_at']}")
                
                # Action button
                if st.button("Mark as Resolved", key=f"resolve_{i}"):
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE dashboard_alerts 
                        SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                        WHERE title = ? AND created_at = ?
                    """, (alert['title'], alert['created_at']))
                    conn.commit()
                    st.success("Alert marked as resolved!")
                    st.rerun()
    else:
        st.success("🎉 No alerts matching your criteria!")

# ============================================
# RUN APP
# ============================================

if __name__ == "__main__":
    main()