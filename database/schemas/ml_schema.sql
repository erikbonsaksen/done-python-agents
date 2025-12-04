-- ML Predictions Database Schema
-- Tables for storing AI/ML predictions and model performance

-- Main predictions table - stores all types of predictions
CREATE TABLE IF NOT EXISTS ml_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_type TEXT NOT NULL, -- 'cash_flow', 'revenue', 'churn_risk', 'payment_risk', 'clv', etc.
    entity_type TEXT, -- 'customer', 'invoice', 'product', 'company'
    entity_id INTEGER, -- Reference to customer/invoice/etc
    entity_name TEXT, -- For display purposes
    
    -- Prediction details
    prediction_date DATE NOT NULL,
    target_date DATE, -- When this prediction is for (e.g., predicted payment date)
    predicted_value REAL, -- Numeric prediction (amount, probability, score)
    predicted_category TEXT, -- Categorical prediction (high/medium/low risk)
    confidence_score REAL, -- Model confidence (0-1)
    
    -- Additional context
    model_version TEXT, -- Track which model version made this
    features_used TEXT, -- JSON of features used
    metadata TEXT, -- JSON for additional data
    
    -- Status tracking
    is_active BOOLEAN DEFAULT 1,
    actual_value REAL, -- Fill in when actual result is known
    actual_date DATE, -- When the actual result occurred
    prediction_error REAL, -- Difference between predicted and actual
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model performance tracking
CREATE TABLE IF NOT EXISTS ml_model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL, -- 'payment_risk_v1', 'churn_risk_v2', etc.
    model_type TEXT NOT NULL, -- 'classification', 'regression', 'forecasting'
    
    -- Performance metrics
    evaluation_date DATE NOT NULL,
    training_samples INTEGER,
    test_samples INTEGER,
    
    -- Regression metrics
    mae REAL, -- Mean Absolute Error
    rmse REAL, -- Root Mean Squared Error
    r2_score REAL, -- R-squared
    
    -- Classification metrics
    accuracy REAL,
    precision_score REAL,
    recall_score REAL,
    f1_score REAL,
    auc_roc REAL,
    
    -- Feature importance
    top_features TEXT, -- JSON of most important features
    
    -- Model info
    hyperparameters TEXT, -- JSON of model config
    training_time_seconds REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Training history and audit trail
CREATE TABLE IF NOT EXISTS ml_training_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    training_date TIMESTAMP NOT NULL,
    
    -- Data used
    date_range_start DATE,
    date_range_end DATE,
    records_used INTEGER,
    features_count INTEGER,
    
    -- Results
    success BOOLEAN,
    error_message TEXT,
    training_duration_seconds REAL,
    
    -- Deployment
    deployed BOOLEAN DEFAULT 0,
    deployed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_predictions_type ON ml_predictions(prediction_type);
CREATE INDEX IF NOT EXISTS idx_predictions_entity ON ml_predictions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON ml_predictions(prediction_date);
CREATE INDEX IF NOT EXISTS idx_predictions_active ON ml_predictions(is_active);
CREATE INDEX IF NOT EXISTS idx_model_perf_name ON ml_model_performance(model_name);
CREATE INDEX IF NOT EXISTS idx_training_model ON ml_training_history(model_name);

-- Views for easy access

-- Active predictions summary
CREATE VIEW IF NOT EXISTS v_active_predictions AS
SELECT 
    prediction_type,
    entity_type,
    COUNT(*) as prediction_count,
    AVG(confidence_score) as avg_confidence,
    MIN(prediction_date) as oldest_prediction,
    MAX(prediction_date) as newest_prediction
FROM ml_predictions
WHERE is_active = 1
GROUP BY prediction_type, entity_type;

-- Model accuracy summary
CREATE VIEW IF NOT EXISTS v_model_accuracy AS
SELECT 
    prediction_type,
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN actual_value IS NOT NULL THEN 1 END) as verified_predictions,
    AVG(ABS(prediction_error)) as avg_error,
    AVG(confidence_score) as avg_confidence
FROM ml_predictions
WHERE actual_value IS NOT NULL
GROUP BY prediction_type;