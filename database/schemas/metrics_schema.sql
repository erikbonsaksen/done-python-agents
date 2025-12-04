-- Dashboard Metrics Schema
-- Tables for storing pre-calculated dashboard metrics

-- Main metrics table for KPIs
CREATE TABLE IF NOT EXISTS dashboard_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_category TEXT NOT NULL, -- 'financial', 'operational', 'customer', 'tax'
    metric_value REAL,
    metric_value_text TEXT, -- For non-numeric values
    metric_unit TEXT, -- 'currency', 'percentage', 'days', 'count'
    period_start DATE,
    period_end DATE,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT -- JSON for additional context
);

-- Alerts and action items
CREATE TABLE IF NOT EXISTS dashboard_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL, -- 'overdue_invoice', 'low_cash', 'upcoming_payment', 'unusual_transaction'
    severity TEXT NOT NULL, -- 'high', 'medium', 'low'
    title TEXT NOT NULL,
    description TEXT,
    amount REAL,
    due_date DATE,
    entity_id INTEGER, -- reference to invoice/customer/etc
    entity_type TEXT, -- 'invoice', 'customer', 'bill', 'transaction'
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
    comparison_value REAL, -- for YoY comparisons
    metadata TEXT, -- JSON for additional context
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
    payment_status TEXT, -- 'fast_payer', 'average', 'slow_payer', 'overdue'
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