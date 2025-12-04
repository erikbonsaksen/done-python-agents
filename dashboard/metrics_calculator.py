#!/usr/bin/env python3
"""
Metrics Calculator Service

Calculates and stores dashboard metrics from Finago data.
Run on command to compute all metrics and store in dashboard tables.

Usage:
    python metrics_calculator.py --db tfso-data.db
"""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import sys


@dataclass
class MetricResult:
    """Result of a metric calculation"""
    name: str
    category: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: str = "count"
    metadata: Optional[Dict] = None


class MetricsCalculator:
    """
    Calculates dashboard metrics from Finago sync data
    """

    def __init__(self, db_path: str = "tfso-data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.today = datetime.now().date()
        self.period_start = self.today - timedelta(days=90)  # Last 90 days default
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def init_metrics_schema(self):
        """Initialize metrics tables if they don't exist"""
        # Embedded SQL schema
        schema_sql = """
-- Dashboard Metrics Schema
-- Tables for storing pre-calculated dashboard metrics

-- Main metrics table for KPIs
CREATE TABLE IF NOT EXISTS dashboard_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_category TEXT NOT NULL,
    metric_value REAL,
    metric_value_text TEXT,
    metric_unit TEXT,
    period_start DATE,
    period_end DATE,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

-- Alerts and action items
CREATE TABLE IF NOT EXISTS dashboard_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    amount REAL,
    due_date DATE,
    entity_id INTEGER,
    entity_type TEXT,
    is_resolved BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Time series metrics for trends/charts
CREATE TABLE IF NOT EXISTS metrics_timeseries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    comparison_value REAL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_name, date)
);

-- Customer insights and segmentation
CREATE TABLE IF NOT EXISTS customer_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT,
    total_revenue REAL,
    invoice_count INTEGER,
    avg_payment_days REAL,
    last_invoice_date DATE,
    payment_status TEXT,
    lifetime_value REAL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_metrics_category ON dashboard_metrics(metric_category);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON dashboard_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON dashboard_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON dashboard_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON dashboard_alerts(is_resolved);
CREATE INDEX IF NOT EXISTS idx_timeseries_metric ON metrics_timeseries(metric_name, date);
CREATE INDEX IF NOT EXISTS idx_customer_metrics_id ON customer_metrics(customer_id);
"""
        
        # Execute each CREATE statement
        for statement in schema_sql.split(';'):
            if statement.strip():
                self.conn.execute(statement)
        self.conn.commit()
        print("✓ Metrics schema initialized")

    def clear_old_metrics(self):
        """Clear old calculated metrics"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM dashboard_metrics")
        cur.execute("DELETE FROM dashboard_alerts WHERE is_resolved = 0")
        cur.execute("DELETE FROM customer_metrics")
        self.conn.commit()
        print("✓ Cleared old metrics")

    # ============================================
    # FINANCIAL HEALTH METRICS
    # ============================================

    def calculate_financial_health(self) -> List[MetricResult]:
        """Calculate core financial health metrics"""
        metrics = []
        cur = self.conn.cursor()

        # Total Revenue (last 90 days)
        cur.execute("""
            SELECT COALESCE(SUM(totalIncVat), 0) as total_revenue
            FROM invoices_sync
            WHERE dateInvoiced >= date('now', '-90 days')
                AND status != 'Cancelled'
        """)
        revenue = cur.fetchone()['total_revenue']
        metrics.append(MetricResult(
            name="total_revenue_90d",
            category="financial",
            value=revenue,
            unit="currency",
            metadata={"period": "90_days"}
        ))

        # Outstanding Receivables
        cur.execute("""
            SELECT COALESCE(SUM(totalIncVat), 0) as outstanding
            FROM invoices_sync
            WHERE status NOT IN ('Paid', 'Cancelled')
        """)
        receivables = cur.fetchone()['outstanding']
        metrics.append(MetricResult(
            name="outstanding_receivables",
            category="financial",
            value=receivables,
            unit="currency"
        ))

        # Average Invoice Value
        cur.execute("""
            SELECT AVG(totalIncVat) as avg_invoice
            FROM invoices_sync
            WHERE dateInvoiced >= date('now', '-90 days')
                AND status != 'Cancelled'
        """)
        avg_invoice = cur.fetchone()['avg_invoice'] or 0
        metrics.append(MetricResult(
            name="avg_invoice_value",
            category="financial",
            value=avg_invoice,
            unit="currency"
        ))

        # Cash Flow Trend (Revenue vs Expenses approximation)
        # Using transaction data to calculate net cash flow
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as inflow,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as outflow
            FROM transactions_sync
            WHERE date >= date('now', '-90 days')
        """)
        flow = cur.fetchone()
        net_flow = flow['inflow'] - flow['outflow']
        metrics.append(MetricResult(
            name="net_cash_flow_90d",
            category="financial",
            value=net_flow,
            unit="currency",
            metadata={"inflow": flow['inflow'], "outflow": flow['outflow']}
        ))

        return metrics

    def calculate_aging_analysis(self) -> List[MetricResult]:
        """Calculate invoice aging buckets"""
        metrics = []
        cur = self.conn.cursor()

        aging_buckets = [
            ("current", 0, 30),
            ("30_days", 30, 60),
            ("60_days", 60, 90),
            ("90_plus_days", 90, 999999)
        ]

        for bucket_name, days_from, days_to in aging_buckets:
            cur.execute("""
                SELECT COALESCE(SUM(totalIncVat), 0) as total
                FROM invoices_sync
                WHERE status NOT IN ('Paid', 'Cancelled')
                    AND julianday('now') - julianday(dateInvoiced) BETWEEN ? AND ?
            """, (days_from, days_to))
            
            total = cur.fetchone()['total']
            metrics.append(MetricResult(
                name=f"aging_{bucket_name}",
                category="financial",
                value=total,
                unit="currency",
                metadata={"days_from": days_from, "days_to": days_to}
            ))

        return metrics

    # ============================================
    # OPERATIONAL METRICS
    # ============================================

    def calculate_invoice_metrics(self) -> List[MetricResult]:
        """Calculate invoice-related operational metrics"""
        metrics = []
        cur = self.conn.cursor()

        # Total invoices count
        cur.execute("""
            SELECT COUNT(*) as count
            FROM invoices_sync
            WHERE dateInvoiced >= date('now', '-90 days')
        """)
        invoice_count = cur.fetchone()['count']
        metrics.append(MetricResult(
            name="invoice_count_90d",
            category="operational",
            value=invoice_count,
            unit="count"
        ))

        # Overdue invoices
        cur.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(totalIncVat), 0) as total
            FROM invoices_sync
            WHERE status NOT IN ('Paid', 'Cancelled')
                AND date(dateInvoiced) < date('now', '-30 days')
        """)
        overdue = cur.fetchone()
        metrics.append(MetricResult(
            name="overdue_invoice_count",
            category="operational",
            value=overdue['count'],
            unit="count",
            metadata={"total_amount": overdue['total']}
        ))

        # Average time to payment (approximation using paid invoices)
        # Note: This is a simplified calculation
        cur.execute("""
            SELECT AVG(
                julianday(dateChanged) - julianday(dateInvoiced)
            ) as avg_days
            FROM invoices_sync
            WHERE status = 'Paid'
                AND dateInvoiced >= date('now', '-180 days')
        """)
        avg_payment_days = cur.fetchone()['avg_days']
        if avg_payment_days:
            metrics.append(MetricResult(
                name="avg_payment_days",
                category="operational",
                value=avg_payment_days,
                unit="days"
            ))

        return metrics

    # ============================================
    # CUSTOMER INSIGHTS
    # ============================================

    def calculate_customer_metrics(self) -> List[MetricResult]:
        """Calculate customer-level metrics and store in customer_metrics table"""
        cur = self.conn.cursor()

        # Clear old customer metrics
        cur.execute("DELETE FROM customer_metrics")

        # Calculate top customers by revenue
        cur.execute("""
            SELECT 
                customerId,
                customerName,
                COUNT(*) as invoice_count,
                SUM(totalIncVat) as total_revenue,
                MAX(dateInvoiced) as last_invoice_date,
                AVG(CASE 
                    WHEN status = 'Paid' 
                    THEN julianday(dateChanged) - julianday(dateInvoiced)
                    ELSE NULL 
                END) as avg_payment_days
            FROM invoices_sync
            WHERE customerId IS NOT NULL
                AND dateInvoiced >= date('now', '-365 days')
            GROUP BY customerId, customerName
            HAVING total_revenue > 0
            ORDER BY total_revenue DESC
            LIMIT 100
        """)

        customers = cur.fetchall()
        
        # Insert customer metrics
        for customer in customers:
            # Determine payment status
            payment_status = 'average'
            if customer['avg_payment_days']:
                if customer['avg_payment_days'] < 15:
                    payment_status = 'fast_payer'
                elif customer['avg_payment_days'] > 45:
                    payment_status = 'slow_payer'
            
            cur.execute("""
                INSERT OR REPLACE INTO customer_metrics (
                    customer_id, customer_name, total_revenue, invoice_count,
                    avg_payment_days, last_invoice_date, payment_status, lifetime_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer['customerId'],
                customer['customerName'],
                customer['total_revenue'],
                customer['invoice_count'],
                customer['avg_payment_days'],
                customer['last_invoice_date'],
                payment_status,
                customer['total_revenue']  # Simplified LTV
            ))

        self.conn.commit()

        # Return summary metrics
        metrics = []
        
        cur.execute("SELECT COUNT(*) as count FROM customer_metrics")
        total_customers = cur.fetchone()['count']
        metrics.append(MetricResult(
            name="active_customers",
            category="customer",
            value=total_customers,
            unit="count"
        ))

        cur.execute("""
            SELECT AVG(total_revenue) as avg_revenue
            FROM customer_metrics
        """)
        avg_customer_revenue = cur.fetchone()['avg_revenue'] or 0
        metrics.append(MetricResult(
            name="avg_customer_revenue",
            category="customer",
            value=avg_customer_revenue,
            unit="currency"
        ))

        return metrics

    # ============================================
    # ALERTS & ACTION ITEMS
    # ============================================

    def generate_alerts(self) -> int:
        """Generate alerts for action items"""
        cur = self.conn.cursor()
        alert_count = 0

        # 1. Overdue Invoices
        cur.execute("""
            SELECT invoiceId, customerId, customerName, invoiceNo, 
                   totalIncVat, dateInvoiced,
                   julianday('now') - julianday(dateInvoiced) as days_overdue
            FROM invoices_sync
            WHERE status NOT IN ('Paid', 'Cancelled')
                AND date(dateInvoiced) < date('now', '-30 days')
            ORDER BY days_overdue DESC
            LIMIT 50
        """)

        for row in cur.fetchall():
            severity = 'high' if row['days_overdue'] > 90 else 'medium' if row['days_overdue'] > 60 else 'low'
            
            cur.execute("""
                INSERT INTO dashboard_alerts (
                    alert_type, severity, title, description, amount, 
                    due_date, entity_id, entity_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'overdue_invoice',
                severity,
                f"Overdue Invoice: {row['invoiceNo']}",
                f"{row['customerName']} - {int(row['days_overdue'])} days overdue",
                row['totalIncVat'],
                row['dateInvoiced'],
                row['invoiceId'],
                'invoice'
            ))
            alert_count += 1

        # 2. Low Cash Warning (if net flow is negative)
        cur.execute("""
            SELECT 
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as inflow,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as outflow
            FROM transactions_sync
            WHERE date >= date('now', '-30 days')
        """)
        flow = cur.fetchone()
        if flow and flow['inflow'] and flow['outflow']:
            net_flow = flow['inflow'] - flow['outflow']
            if net_flow < 0:
                cur.execute("""
                    INSERT INTO dashboard_alerts (
                        alert_type, severity, title, description, amount, entity_type
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    'low_cash',
                    'high',
                    "Negative Cash Flow",
                    f"Cash outflow exceeds inflow by {abs(net_flow):,.2f} in last 30 days",
                    abs(net_flow),
                    'transaction'
                ))
                alert_count += 1

        # 3. Large Transactions (potential anomalies)
        cur.execute("""
            SELECT AVG(ABS(amount)) as avg_amount, 
                   MAX(ABS(amount)) as max_amount
            FROM transactions_sync
            WHERE date >= date('now', '-90 days')
        """)
        stats = cur.fetchone()
        if stats and stats['avg_amount']:
            threshold = stats['avg_amount'] * 5  # 5x average
            
            cur.execute("""
                SELECT transactionId, date, amount, description, accountNo
                FROM transactions_sync
                WHERE date >= date('now', '-7 days')
                    AND ABS(amount) > ?
                ORDER BY ABS(amount) DESC
                LIMIT 10
            """, (threshold,))
            
            for row in cur.fetchall():
                cur.execute("""
                    INSERT INTO dashboard_alerts (
                        alert_type, severity, title, description, amount,
                        entity_id, entity_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    'unusual_transaction',
                    'medium',
                    "Large Transaction",
                    f"Account {row['accountNo']}: {row['description'][:100]}",
                    abs(row['amount']),
                    row['transactionId'],
                    'transaction'
                ))
                alert_count += 1

        self.conn.commit()
        return alert_count

    # ============================================
    # TIME SERIES METRICS
    # ============================================

    def calculate_revenue_timeseries(self):
        """Calculate daily/monthly revenue trends"""
        cur = self.conn.cursor()

        # Delete old timeseries data for revenue
        cur.execute("""
            DELETE FROM metrics_timeseries 
            WHERE metric_name LIKE 'revenue_%'
        """)

        # Monthly revenue for last 12 months
        cur.execute("""
            SELECT 
                strftime('%Y-%m', dateInvoiced) as month,
                SUM(totalIncVat) as revenue
            FROM invoices_sync
            WHERE dateInvoiced >= date('now', '-365 days')
                AND status != 'Cancelled'
            GROUP BY month
            ORDER BY month
        """)

        for row in cur.fetchall():
            month_date = datetime.strptime(row['month'], '%Y-%m').date()
            cur.execute("""
                INSERT OR REPLACE INTO metrics_timeseries (
                    metric_name, date, value
                ) VALUES (?, ?, ?)
            """, ('revenue_monthly', month_date, row['revenue']))

        self.conn.commit()

    # ============================================
    # MAIN CALCULATION ORCHESTRATION
    # ============================================

    def store_metrics(self, metrics: List[MetricResult]):
        """Store calculated metrics in the database"""
        cur = self.conn.cursor()
        
        for metric in metrics:
            metadata_json = json.dumps(metric.metadata) if metric.metadata else None
            
            cur.execute("""
                INSERT INTO dashboard_metrics (
                    metric_name, metric_category, metric_value, metric_value_text,
                    metric_unit, period_start, period_end, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.name,
                metric.category,
                metric.value,
                metric.value_text,
                metric.unit,
                self.period_start,
                self.today,
                metadata_json
            ))
        
        self.conn.commit()

    def calculate_all_metrics(self):
        """Calculate all metrics and store in database"""
        print(f"\n{'='*60}")
        print(f"  CALCULATING DASHBOARD METRICS")
        print(f"{'='*60}\n")
        print(f"Database: {self.db_path}")
        print(f"Period: {self.period_start} to {self.today}\n")

        # Initialize schema
        self.init_metrics_schema()
        
        # Clear old metrics
        self.clear_old_metrics()

        all_metrics = []

        # Calculate different metric categories
        print("📊 Calculating financial health metrics...")
        all_metrics.extend(self.calculate_financial_health())
        all_metrics.extend(self.calculate_aging_analysis())
        
        print("📈 Calculating operational metrics...")
        all_metrics.extend(self.calculate_invoice_metrics())
        
        print("👥 Calculating customer metrics...")
        all_metrics.extend(self.calculate_customer_metrics())
        
        print("⏰ Calculating time series...")
        self.calculate_revenue_timeseries()
        
        print("🚨 Generating alerts...")
        alert_count = self.generate_alerts()

        # Store all metrics
        print(f"💾 Storing {len(all_metrics)} metrics...")
        self.store_metrics(all_metrics)

        print(f"\n{'='*60}")
        print(f"  ✓ CALCULATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Metrics calculated: {len(all_metrics)}")
        print(f"  Alerts generated: {alert_count}")
        print(f"{'='*60}\n")

        return all_metrics

    def print_summary(self):
        """Print a summary of calculated metrics"""
        cur = self.conn.cursor()
        
        print("\n📊 METRICS SUMMARY:\n")
        
        categories = ['financial', 'operational', 'customer']
        for category in categories:
            print(f"\n{category.upper()}:")
            cur.execute("""
                SELECT metric_name, metric_value, metric_unit
                FROM dashboard_metrics
                WHERE metric_category = ?
                ORDER BY metric_name
            """, (category,))
            
            for row in cur.fetchall():
                value = row['metric_value']
                if row['metric_unit'] == 'currency':
                    print(f"  • {row['metric_name']}: {value:,.2f} NOK")
                elif row['metric_unit'] == 'percentage':
                    print(f"  • {row['metric_name']}: {value:.1f}%")
                else:
                    print(f"  • {row['metric_name']}: {value:.0f} {row['metric_unit']}")


def main():
    parser = argparse.ArgumentParser(description='Calculate dashboard metrics from Finago data')
    parser.add_argument('--db', type=str, default='tfso-data.db',
                        help='Path to SQLite database')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary after calculation')
    parser.add_argument('--schema-only', action='store_true',
                        help='Only initialize schema without calculating metrics')
    
    args = parser.parse_args()

    try:
        with MetricsCalculator(args.db) as calculator:
            if args.schema_only:
                calculator.init_metrics_schema()
                print("✓ Schema initialized successfully")
            else:
                calculator.calculate_all_metrics()
                
                if args.summary:
                    calculator.print_summary()
        
        print("\n✓ All done!\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()