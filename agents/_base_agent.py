"""
Base Agent Class for ML/AI Predictions

Provides common functionality for all prediction agents:
- Database connections
- Data loading
- Prediction storage
- Model versioning
- Performance tracking
"""

import sqlite3
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from abc import ABC, abstractmethod


@dataclass
class Prediction:
    """Standard prediction format"""

    prediction_type: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    entity_name: Optional[str]
    prediction_date: date
    target_date: Optional[date]
    predicted_value: Optional[float]
    predicted_category: Optional[str]
    confidence_score: float
    model_version: str
    features_used: Dict[str, Any]
    metadata: Dict[str, Any] = None


class BaseMLAgent(ABC):
    """
    Base class for all ML agents

    Each agent should implement:
    - train(): Train the model
    - predict(): Make predictions
    - evaluate(): Evaluate model performance
    """

    def __init__(self, db_path: str = "tfso-data.db", model_name: str = None):
        self.db_path = db_path
        self.model_name = model_name or self.__class__.__name__
        self.model_version = "v1"
        self.model = None

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================
    # DATA LOADING
    # ============================================

    def load_invoices(self, days_back: int = 365) -> pd.DataFrame:
        """Load invoice data for training/prediction"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    invoiceId,
                    customerId,
                    customerName,
                    dateInvoiced,
                    dateDue,
                    datePaid,
                    dateChanged,
                    totalIncVat,
                    amountPaid,
                    balance,
                    status,
                    julianday('now') - julianday(dateInvoiced) as days_since_invoice,
                    julianday(dateDue) - julianday(dateInvoiced) as payment_terms_days
                FROM invoices_sync
                WHERE dateInvoiced >= date('now', '-' || ? || ' days')
            """
            df = pd.read_sql_query(query, conn, params=(days_back,))

            # Convert date columns and strip timezone info to avoid tz-aware/tz-naive conflicts
            date_cols = ["dateInvoiced", "dateDue", "datePaid", "dateChanged"]
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(
                        df[col], errors="coerce", utc=True
                    ).dt.tz_localize(None)

            return df

    def load_customer_history(self) -> pd.DataFrame:
        """Load customer payment history and behavior"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    customerId,
                    customerName,
                    COUNT(*) as total_invoices,
                    COUNT(CASE WHEN status = 'Paid' THEN 1 END) as paid_invoices,
                    COUNT(CASE WHEN status = 'Unpaid' THEN 1 END) as unpaid_invoices,
                    SUM(totalIncVat) as total_revenue,
                    AVG(totalIncVat) as avg_invoice_amount,
                    MIN(dateInvoiced) as first_invoice_date,
                    MAX(dateInvoiced) as last_invoice_date,
                    AVG(CASE 
                        WHEN status = 'Paid' 
                        THEN julianday(dateChanged) - julianday(dateInvoiced)
                        ELSE NULL 
                    END) as avg_days_to_pay
                FROM invoices_sync
                WHERE customerId IS NOT NULL
                GROUP BY customerId, customerName
            """
            df = pd.read_sql_query(query, conn)

            # Calculate payment reliability
            df["payment_rate"] = df["paid_invoices"] / df["total_invoices"]

            return df

    def load_transactions(self, days_back: int = 365) -> pd.DataFrame:
        """Load transaction data"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    transactionId,
                    date,
                    accountNo,
                    amount,
                    debit,
                    credit,
                    description,
                    customerId
                FROM transactions_sync
                WHERE date >= date('now', '-' || ? || ' days')
            """
            df = pd.read_sql_query(query, conn, params=(days_back,))
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df

    # ============================================
    # PREDICTION STORAGE
    # ============================================

    def save_prediction(self, prediction: Prediction) -> int:
        """Save a prediction to the database"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO ml_predictions (
                    prediction_type, entity_type, entity_id, entity_name,
                    prediction_date, target_date, predicted_value, predicted_category,
                    confidence_score, model_version, features_used, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    prediction.prediction_type,
                    prediction.entity_type,
                    prediction.entity_id,
                    prediction.entity_name,
                    prediction.prediction_date,
                    prediction.target_date,
                    prediction.predicted_value,
                    prediction.predicted_category,
                    prediction.confidence_score,
                    prediction.model_version,
                    json.dumps(prediction.features_used),
                    json.dumps(prediction.metadata) if prediction.metadata else None,
                ),
            )

            conn.commit()
            return cur.lastrowid

    def save_predictions_batch(self, predictions: List[Prediction]) -> int:
        """Save multiple predictions efficiently"""
        count = 0
        for pred in predictions:
            self.save_prediction(pred)
            count += 1
        return count

    def deactivate_old_predictions(self, prediction_type: str):
        """Mark old predictions as inactive before generating new ones"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE ml_predictions 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE prediction_type = ? AND is_active = 1
            """,
                (prediction_type,),
            )
            conn.commit()

    def get_predictions(
        self,
        prediction_type: str,
        entity_id: Optional[int] = None,
        active_only: bool = True,
    ) -> pd.DataFrame:
        """Retrieve predictions from database"""
        with self.get_connection() as conn:
            query = """
                SELECT * FROM ml_predictions 
                WHERE prediction_type = ?
            """
            params = [prediction_type]

            if entity_id:
                query += " AND entity_id = ?"
                params.append(entity_id)

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY prediction_date DESC"

            return pd.read_sql_query(query, conn, params=params)

    # ============================================
    # MODEL PERFORMANCE
    # ============================================

    def save_model_performance(
        self,
        metrics: Dict[str, float],
        training_samples: int,
        test_samples: int,
        top_features: Dict[str, float] = None,
        hyperparameters: Dict[str, Any] = None,
        training_time: float = 0,
    ):
        """Save model performance metrics"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO ml_model_performance (
                    model_name, model_type, evaluation_date,
                    training_samples, test_samples,
                    mae, rmse, r2_score,
                    accuracy, precision_score, recall_score, f1_score, auc_roc,
                    top_features, hyperparameters, training_time_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{self.model_name}_{self.model_version}",
                    self.get_model_type(),
                    date.today(),
                    training_samples,
                    test_samples,
                    metrics.get("mae"),
                    metrics.get("rmse"),
                    metrics.get("r2_score"),
                    metrics.get("accuracy"),
                    metrics.get("precision"),
                    metrics.get("recall"),
                    metrics.get("f1"),
                    metrics.get("auc_roc"),
                    json.dumps(top_features) if top_features else None,
                    json.dumps(hyperparameters) if hyperparameters else None,
                    training_time,
                ),
            )

            conn.commit()

    def log_training(
        self,
        date_range: Tuple[date, date],
        records_used: int,
        features_count: int,
        success: bool,
        error_message: str = None,
        duration: float = 0,
    ):
        """Log training session"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ml_training_history (
                    model_name, training_date,
                    date_range_start, date_range_end,
                    records_used, features_count,
                    success, error_message, training_duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{self.model_name}_{self.model_version}",
                    datetime.now(),
                    date_range[0],
                    date_range[1],
                    records_used,
                    features_count,
                    success,
                    error_message,
                    duration,
                ),
            )
            conn.commit()

    # ============================================
    # ABSTRACT METHODS (implement in subclasses)
    # ============================================

    @abstractmethod
    def train(self) -> bool:
        """Train the model on historical data"""
        pass

    @abstractmethod
    def predict(self) -> List[Prediction]:
        """Generate predictions"""
        pass

    @abstractmethod
    def evaluate(self) -> Dict[str, float]:
        """Evaluate model performance"""
        pass

    @abstractmethod
    def get_model_type(self) -> str:
        """Return model type: 'regression', 'classification', or 'forecasting'"""
        pass

    # ============================================
    # UTILITY METHODS
    # ============================================

    def print_summary(self, predictions: List[Prediction]):
        """Print a summary of predictions"""
        print(f"\n{'='*60}")
        print(f"  {self.model_name} - Predictions Summary")
        print(f"{'='*60}")
        print(f"  Total predictions: {len(predictions)}")

        if predictions:
            avg_conf = sum(p.confidence_score for p in predictions) / len(predictions)
            print(f"  Average confidence: {avg_conf:.2%}")

            # Group by category if available
            if predictions[0].predicted_category:
                from collections import Counter

                categories = Counter(p.predicted_category for p in predictions)
                print(f"\n  By category:")
                for cat, count in categories.most_common():
                    print(f"    {cat}: {count}")

        print(f"{'='*60}\n")
