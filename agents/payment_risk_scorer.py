#!/usr/bin/env python3
"""
Payment Risk Scorer

Predicts the likelihood that an invoice will be paid late or not at all.
Uses customer payment history, invoice characteristics, and timing.

Usage:
    python payment_risk_scorer.py --train
    python payment_risk_scorer.py --predict
    python payment_risk_scorer.py --evaluate
"""

import argparse
import sys
from datetime import datetime, date
from typing import List, Dict
import pandas as pd
import numpy as np

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler
    import joblib
except ImportError:
    print("⚠️  scikit-learn not installed. Install with: pip install scikit-learn joblib")
    sys.exit(1)

from agents._base_agent import BaseMLAgent, Prediction


class PaymentRiskScorer(BaseMLAgent):
    """
    Predicts payment risk for unpaid invoices
    
    Risk Categories:
    - LOW: < 20% chance of late payment
    - MEDIUM: 20-60% chance of late payment  
    - HIGH: > 60% chance of late payment
    """
    
    def __init__(self, db_path: str = "tfso-data.db"):
        super().__init__(db_path, model_name="payment_risk_scorer")
        self.model_version = "v1"
        self.scaler = StandardScaler()
        self.feature_names = []
        
    def get_model_type(self) -> str:
        return "classification"
    
    def prepare_features(self, df: pd.DataFrame, customer_history: pd.DataFrame) -> pd.DataFrame:
        """Engineer features for payment risk prediction"""
        
        # Merge with customer history - use 'left' to keep only invoice rows
        df = df.merge(customer_history, on='customerId', how='left', suffixes=('', '_hist'))
        
        # IMPORTANT: Reset index after merge to avoid index misalignment
        df = df.reset_index(drop=True)
        
        # Fill missing values
        df['avg_days_to_pay'] = df['avg_days_to_pay'].fillna(30)
        df['payment_rate'] = df['payment_rate'].fillna(0.5)
        df['total_invoices'] = df['total_invoices'].fillna(1)
        
        # Features
        features = pd.DataFrame()
        
        # Invoice characteristics
        features['invoice_amount'] = df['totalIncVat']
        features['payment_terms_days'] = df['payment_terms_days'].fillna(14)
        features['days_since_invoice'] = df['days_since_invoice']
        
        # Customer behavior
        features['customer_payment_rate'] = df['payment_rate']
        features['customer_avg_days_to_pay'] = df['avg_days_to_pay']
        features['customer_total_invoices'] = df['total_invoices']
        features['customer_avg_invoice'] = df['avg_invoice_amount'].fillna(df['totalIncVat'])
        
        # Relative features
        features['amount_vs_avg'] = df['totalIncVat'] / (df['avg_invoice_amount'] + 1)
        features['is_larger_than_usual'] = (features['amount_vs_avg'] > 1.5).astype(int)
        
        # Temporal features
        df['invoice_month'] = pd.to_datetime(df['dateInvoiced']).dt.month
        df['invoice_dayofweek'] = pd.to_datetime(df['dateInvoiced']).dt.dayofweek
        features['invoice_month'] = df['invoice_month']
        features['invoice_dayofweek'] = df['invoice_dayofweek']
        features['is_month_end'] = (pd.to_datetime(df['dateInvoiced']).dt.day > 25).astype(int)
        
        # Risk indicators
        features['customer_has_unpaid'] = (df['unpaid_invoices'] > 0).astype(int)
        features['slow_payer'] = (df['avg_days_to_pay'] > 30).astype(int)
        features['unreliable_payer'] = (df['payment_rate'] < 0.8).astype(int)
        
        self.feature_names = features.columns.tolist()
        
        return features
    
    def train(self, test_size: float = 0.2) -> bool:
        """
        Train payment risk model on historical data
        
        Target: Whether invoice was paid late (after due date)
        """
        print(f"\n{'='*60}")
        print(f"  Training Payment Risk Scorer")
        print(f"{'='*60}\n")
        
        start_time = datetime.now()
        
        try:
            # Load data
            print("📊 Loading data...")
            invoices = self.load_invoices(days_back=730)  # 2 years of data
            customer_history = self.load_customer_history()
            
            print(f"   Loaded {len(invoices)} invoices")
            print(f"   Loaded {len(customer_history)} customers")
            
            # Filter to paid invoices only (we need actual outcomes)
            paid_invoices = invoices[invoices['status'] == 'Paid'].copy()
            
            if len(paid_invoices) < 50:
                print("❌ Not enough paid invoices to train (need at least 50)")
                return False
            
            print(f"   Using {len(paid_invoices)} paid invoices for training")
            
            # Create target: was it paid late?
            # Late = paid more than 7 days after due date
            paid_invoices['effective_due_date'] = paid_invoices.apply(
                lambda row: row['dateDue'] if pd.notna(row['dateDue']) 
                            else row['dateInvoiced'] + pd.Timedelta(days=14),
                axis=1
            )

            paid_invoices['days_overdue'] = (
                (paid_invoices['datePaid'] - paid_invoices['effective_due_date']).dt.days
            )

            # Late = paid more than 7 days after due date
            paid_invoices['paid_late'] = (paid_invoices['days_overdue'] > 7).astype(int)
            
            late_count = paid_invoices['paid_late'].sum()
            late_pct = late_count / len(paid_invoices) * 100
            
            print(f"\n   Late payments: {late_count} ({late_pct:.1f}%)")
            
            if late_count < 10:
                print("❌ Not enough late payments to train (need at least 10)")
                return False
            
            # Prepare features
            print("\n🔧 Engineering features...")

            # Check for duplicate customers in history (should be unique per customerId)
            if customer_history['customerId'].duplicated().any():
                print("   ⚠️  Removing duplicate customers from history...")
                customer_history = customer_history.drop_duplicates(subset=['customerId'], keep='first')

            X = self.prepare_features(paid_invoices, customer_history)
            y = paid_invoices['paid_late']

            # Ensure X and y have same length
            assert len(X) == len(y), f"Feature matrix ({len(X)}) and target ({len(y)}) have different lengths!"
            
            print(f"   Features: {len(self.feature_names)}")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=y
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            print("\n🤖 Training Random Forest model...")
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                class_weight='balanced'  # Handle imbalanced data
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            print("\n📈 Evaluating model...")
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1': f1_score(y_test, y_pred, zero_division=0),
                'auc_roc': roc_auc_score(y_test, y_pred_proba)
            }
            
            print(f"   Accuracy:  {metrics['accuracy']:.2%}")
            print(f"   Precision: {metrics['precision']:.2%}")
            print(f"   Recall:    {metrics['recall']:.2%}")
            print(f"   F1 Score:  {metrics['f1']:.2%}")
            print(f"   AUC-ROC:   {metrics['auc_roc']:.2%}")
            
            # Feature importance
            feature_importance = dict(zip(
                self.feature_names,
                self.model.feature_importances_
            ))
            top_features = dict(sorted(
                feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10])
            
            print("\n   Top 10 important features:")
            for feat, importance in top_features.items():
                print(f"     {feat:30} {importance:.3f}")
            
            # Save model
            print("\n💾 Saving model...")
            joblib.dump(self.model, f"{self.model_name}_{self.model_version}.pkl")
            joblib.dump(self.scaler, f"{self.model_name}_{self.model_version}_scaler.pkl")
            
            # Save performance
            duration = (datetime.now() - start_time).total_seconds()
            self.save_model_performance(
                metrics=metrics,
                training_samples=len(X_train),
                test_samples=len(X_test),
                top_features=top_features,
                training_time=duration
            )
            
            # Log training
            self.log_training(
                date_range=(paid_invoices['dateInvoiced'].min().date(), 
                           paid_invoices['dateInvoiced'].max().date()),
                records_used=len(paid_invoices),
                features_count=len(self.feature_names),
                success=True,
                duration=duration
            )
            
            print(f"\n✅ Training complete! ({duration:.1f}s)")
            print(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Training failed: {e}")
            import traceback
            traceback.print_exc()
            
            self.log_training(
                date_range=(date.today(), date.today()),
                records_used=0,
                features_count=0,
                success=False,
                error_message=str(e)
            )
            
            return False
    
    def predict(self) -> List[Prediction]:
        """Generate payment risk predictions for all unpaid invoices"""
        print(f"\n{'='*60}")
        print(f"  Generating Payment Risk Predictions")
        print(f"{'='*60}\n")
        
        try:
            # Load model
            print("📦 Loading model...")
            self.model = joblib.load(f"{self.model_name}_{self.model_version}.pkl")
            self.scaler = joblib.load(f"{self.model_name}_{self.model_version}_scaler.pkl")
            
            # Load data
            print("📊 Loading unpaid invoices...")
            invoices = self.load_invoices(days_back=365)
            customer_history = self.load_customer_history()
            
            # Filter to unpaid only
            unpaid_invoices = invoices[invoices['status'] == 'Unpaid'].copy()
            
            if len(unpaid_invoices) == 0:
                print("✅ No unpaid invoices - nothing to predict!")
                return []
            
            print(f"   Found {len(unpaid_invoices)} unpaid invoices")
            
            # Prepare features
            print("\n🔧 Preparing features...")
            X = self.prepare_features(unpaid_invoices, customer_history)
            X_scaled = self.scaler.transform(X)
            
            # Predict
            print("🔮 Predicting payment risk...")
            risk_probabilities = self.model.predict_proba(X_scaled)[:, 1]
            
            # Create predictions
            predictions = []
            
            # Deactivate old predictions
            self.deactivate_old_predictions('payment_risk')
            
            for idx, row in unpaid_invoices.iterrows():
                risk_prob = risk_probabilities[unpaid_invoices.index.get_loc(idx)]
                
                # Categorize risk
                if risk_prob < 0.2:
                    category = "LOW"
                elif risk_prob < 0.6:
                    category = "MEDIUM"
                else:
                    category = "HIGH"
                
                pred = Prediction(
                    prediction_type='payment_risk',
                    entity_type='invoice',
                    entity_id=int(row['invoiceId']),
                    entity_name=f"Invoice {row['invoiceId']} - {row['customerName']}",
                    prediction_date=date.today(),
                    target_date=pd.to_datetime(row['dateDue']).date() if pd.notna(row['dateDue']) else None,
                    predicted_value=float(risk_prob),
                    predicted_category=category,
                    confidence_score=float(max(risk_prob, 1 - risk_prob)),
                    model_version=self.model_version,
                    features_used={
                        'invoice_amount': float(row['totalIncVat']),
                        'days_since_invoice': float(row['days_since_invoice']),
                        'customer': row['customerName']
                    },
                    metadata={
                        'due_date': str(row['dateDue']) if pd.notna(row['dateDue']) else None,
                        'amount': float(row['totalIncVat'])
                    }
                )
                
                predictions.append(pred)
            
            # Save predictions
            print(f"\n💾 Saving {len(predictions)} predictions...")
            self.save_predictions_batch(predictions)
            
            # Print summary
            self.print_summary(predictions)
            
            # Show high risk invoices
            high_risk = [p for p in predictions if p.predicted_category == "HIGH"]
            if high_risk:
                print(f"\n⚠️  HIGH RISK INVOICES ({len(high_risk)}):")
                for p in sorted(high_risk, key=lambda x: x.predicted_value, reverse=True)[:5]:
                    print(f"   {p.entity_name}: {p.predicted_value:.1%} risk")
            
            print(f"\n✅ Predictions complete!")
            print(f"{'='*60}\n")
            
            return predictions
            
        except FileNotFoundError:
            print("❌ Model not found. Please train first: python payment_risk_scorer.py --train")
            return []
        except Exception as e:
            print(f"❌ Prediction failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def evaluate(self) -> Dict[str, float]:
        """Evaluate model on recent data"""
        # TODO: Implement evaluation on newly paid invoices
        print("Evaluation not yet implemented")
        return {}


def main():
    parser = argparse.ArgumentParser(description='Payment Risk Scorer')
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--predict', action='store_true', help='Generate predictions')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate model')
    parser.add_argument('--db', type=str, default='tfso-data.db', help='Database path')
    
    args = parser.parse_args()
    
    scorer = PaymentRiskScorer(db_path=args.db)
    
    if args.train:
        success = scorer.train()
        sys.exit(0 if success else 1)
    
    elif args.predict:
        predictions = scorer.predict()
        sys.exit(0 if predictions is not None else 1)
    
    elif args.evaluate:
        metrics = scorer.evaluate()
        sys.exit(0)
    
    else:
        print("Please specify --train, --predict, or --evaluate")
        sys.exit(1)


if __name__ == "__main__":
    main()