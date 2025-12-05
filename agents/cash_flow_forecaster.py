#!/usr/bin/env python3
"""
Cash Flow Forecaster v2 - Reality-Based

Predicts monthly cash flow for the next 3 months using YOUR actual business patterns:
- Monthly expenses: ~144K NOK (from your real data)
- Payment timing: 14 days average (actual customer behavior)
- Three scenarios: Best Case / Realistic / Worst Case

Usage:
    python cash_flow_forecaster.py --predict
    python cash_flow_forecaster.py --predict --scenario worst
    python cash_flow_forecaster.py --predict --scenario best
"""

import argparse
import sys
from datetime import datetime, date, timedelta
from typing import List, Dict
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np
import sqlite3

# Fix imports
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agents._base_agent import BaseMLAgent, Prediction


class CashFlowForecasterV2(BaseMLAgent):
    """
    Reality-based cash flow forecaster using actual business patterns
    
    No ML training needed - uses simple but realistic assumptions:
    - Monthly expenses: 144K NOK (your median)
    - Payment timing: 14 days (your customer average)
    - Scenarios for risk assessment
    """
    
    def __init__(self, db_path: str = "tfso-data.db"):
        super().__init__(db_path, model_name="cash_flow_forecaster")
        self.model_version = "v2"
        
        # REAL BUSINESS PARAMETERS (from your data analysis)
        self.MONTHLY_EXPENSE_BASELINE = 144000  # Your median monthly expenses
        self.EXPENSE_VOLATILITY = 50000  # Standard deviation in your expenses
        self.AVG_PAYMENT_DAYS = 14  # Your customers pay in 14 days on average
        self.MONTHLY_REVENUE_BASELINE = 126000  # Your baseline monthly revenue
        
        # SEASONAL MULTIPLIERS (from your actual data)
        self.SEASONAL_MULTIPLIERS = {
            1: 1.43,   # Jan - Strong 🔥
            2: 0.92,   # Feb
            3: 1.05,   # Mar
            4: 1.05,   # Apr
            5: 0.69,   # May - Weak ❄️
            6: 0.85,   # Jun - Weak ❄️
            7: 1.25,   # Jul - Strong 🔥
            8: 0.94,   # Aug
            9: 1.05,   # Sep
            10: 1.23,  # Oct - Strong 🔥
            11: 0.91,  # Nov
            12: 0.64   # Dec - Weak ❄️
        }
        
    def get_model_type(self) -> str:
        return "forecasting"
    
    def train(self) -> bool:
        """Not needed for v2 - uses actual data patterns"""
        print("\n⚠️  Training not required for v2 forecaster")
        print("   This version uses your actual business patterns directly")
        print("   Run: python cash_flow_forecaster.py --predict")
        return True
    
    def predict(self, scenario: str = "realistic") -> List[Prediction]:
        """
        Generate 3-month cash flow forecast
        
        Args:
            scenario: 'best', 'realistic', or 'worst'
        """
        print(f"\n{'='*70}")
        print(f"  CASH FLOW FORECAST - {scenario.upper()} SCENARIO")
        print(f"  Next 3 Months")
        print(f"{'='*70}\n")
        
        try:
            # ========================================
            # 1. LOAD UNPAID INVOICES
            # ========================================
            print("📊 Loading current receivables...\n")
            
            invoices = self.load_invoices(days_back=365)
            unpaid_invoices = invoices[invoices['status'] == 'Unpaid'].copy()
            
            total_outstanding = unpaid_invoices['balance'].sum()
            
            print(f"   Outstanding Receivables: {total_outstanding:,.2f} NOK")
            print(f"   Number of invoices: {len(unpaid_invoices)}")
            
            # ========================================
            # 2. PREDICT PAYMENT TIMING
            # ========================================
            print(f"\n🔮 Predicting payment timing ({scenario} scenario)...\n")
            
            if len(unpaid_invoices) > 0:
                # Calculate expected payment date based on scenario
                if scenario == "best":
                    # Best case: Everyone pays on time (14 days)
                    payment_days = self.AVG_PAYMENT_DAYS
                    payment_rate = 1.0  # 100% payment
                elif scenario == "worst":
                    # Worst case: 30% longer payment time, 20% don't pay
                    payment_days = self.AVG_PAYMENT_DAYS * 1.3
                    payment_rate = 0.8  # 80% payment
                else:  # realistic
                    # Realistic: Some variance, 95% payment
                    payment_days = self.AVG_PAYMENT_DAYS * 1.1
                    payment_rate = 0.95
                
                # Calculate expected payment date for each invoice
                unpaid_invoices['expected_payment_date'] = (
                    unpaid_invoices['dateInvoiced'] + 
                    pd.Timedelta(days=payment_days)
                )
                
                # Apply payment rate (some might not pay)
                unpaid_invoices['expected_amount'] = (
                    unpaid_invoices['balance'] * payment_rate
                )
                
                unpaid_invoices['payment_month'] = (
                    unpaid_invoices['expected_payment_date'].dt.to_period('M')
                )
            
            # ========================================
            # 3. ESTIMATE MONTHLY EXPENSES
            # ========================================
            print(f"💰 Estimating monthly expenses ({scenario} scenario)...\n")
            
            if scenario == "best":
                # Best case: Below average expenses
                monthly_expense = self.MONTHLY_EXPENSE_BASELINE * 0.9
            elif scenario == "worst":
                # Worst case: Above average expenses
                monthly_expense = self.MONTHLY_EXPENSE_BASELINE * 1.2
            else:  # realistic
                # Realistic: Baseline
                monthly_expense = self.MONTHLY_EXPENSE_BASELINE
            
            print(f"   Baseline monthly expense: {self.MONTHLY_EXPENSE_BASELINE:,.2f} NOK")
            print(f"   {scenario.capitalize()} scenario: {monthly_expense:,.2f} NOK/month")
            
            # ========================================
            # 4. CALCULATE MONTHLY FORECAST
            # ========================================
            print(f"\n📅 Monthly Cash Flow Forecast:\n")
            print(f"   {'Month':<12} {'AR Collect':<13} {'New Revenue':<13} {'Total In':<13} {'Outflows':<13} {'Net':<13} Status")
            print(f"   {'-'*100}")
            
            predictions = []
            cumulative_cash = 0  # Track running cash balance
            today = date.today()
            
            # Deactivate old predictions
            self.deactivate_old_predictions('cash_flow')
            
            for month_offset in range(3):
                target_date = today + relativedelta(months=month_offset)
                target_period = pd.Period(target_date, freq='M')
                target_month_num = target_date.month
                
                # ========================================
                # A. INFLOWS FROM EXISTING UNPAID INVOICES
                # ========================================
                if len(unpaid_invoices) > 0:
                    month_invoices = unpaid_invoices[
                        unpaid_invoices['payment_month'] == target_period
                    ]
                    inflow_from_ar = month_invoices['expected_amount'].sum()
                    invoice_count = len(month_invoices)
                else:
                    inflow_from_ar = 0
                    invoice_count = 0
                
                # ========================================
                # B. PREDICTED NEW REVENUE (SEASONAL)
                # ========================================
                seasonal_multiplier = self.SEASONAL_MULTIPLIERS.get(target_month_num, 1.0)
                base_new_revenue = self.MONTHLY_REVENUE_BASELINE * seasonal_multiplier
                
                # Apply scenario adjustment to new revenue
                if scenario == "best":
                    new_revenue = base_new_revenue * 1.1  # 10% above seasonal expectation
                elif scenario == "worst":
                    new_revenue = base_new_revenue * 0.7  # 30% below seasonal expectation
                else:  # realistic
                    new_revenue = base_new_revenue * 0.95  # Slightly conservative
                
                # ========================================
                # C. TOTAL EXPECTED INFLOWS
                # ========================================
                expected_inflow = inflow_from_ar + new_revenue
                
                # Expected outflows
                expected_outflow = monthly_expense
                
                # Net cash flow
                net_cash_flow = expected_inflow - expected_outflow
                cumulative_cash += net_cash_flow
                
                # Categorize
                if cumulative_cash < -100000:
                    status = "🔴 CRITICAL"
                elif cumulative_cash < 0:
                    status = "🟡 NEGATIVE"
                elif net_cash_flow < 0:
                    status = "🟠 BURNING"
                else:
                    status = "🟢 POSITIVE"
                
                # Print row with breakdown
                month_str = str(target_period)
                print(f"   {month_str:<12} "
                      f"{inflow_from_ar:>11,.0f}  "
                      f"{new_revenue:>11,.0f}  "
                      f"{expected_inflow:>11,.0f}  "
                      f"{expected_outflow:>11,.0f}  "
                      f"{net_cash_flow:>11,.0f}  "
                      f"{status}")
                
                # Create prediction
                pred = Prediction(
                    prediction_type='cash_flow',
                    entity_type='company',
                    entity_id=None,
                    entity_name=f"Cash Flow - {target_period} ({scenario})",
                    prediction_date=today,
                    target_date=target_date,
                    predicted_value=float(net_cash_flow),
                    predicted_category=self._categorize_cash_flow(cumulative_cash),
                    confidence_score=self._get_confidence(scenario),
                    model_version=self.model_version,
                    features_used={
                        'ar_collections': float(inflow_from_ar),
                        'new_revenue': float(new_revenue),
                        'expected_inflow': float(expected_inflow),
                        'expected_outflow': float(expected_outflow),
                        'invoice_count': int(invoice_count),
                        'seasonal_multiplier': float(seasonal_multiplier),
                        'scenario': scenario
                    },
                    metadata={
                        'month': str(target_period),
                        'ar_collections': float(inflow_from_ar),
                        'new_revenue': float(new_revenue),
                        'seasonal_multiplier': float(seasonal_multiplier),
                        'inflow': float(expected_inflow),
                        'outflow': float(expected_outflow),
                        'net': float(net_cash_flow),
                        'cumulative': float(cumulative_cash),
                        'invoices_due': int(invoice_count),
                        'scenario': scenario
                    }
                )
                
                predictions.append(pred)
            
            # ========================================
            # 5. SUMMARY & INSIGHTS
            # ========================================
            print(f"\n   {'-'*70}")
            print(f"   {'3-Month Total':<15} "
                  f"{sum(p.features_used['expected_inflow'] for p in predictions):>13,.0f}  "
                  f"{sum(p.features_used['expected_outflow'] for p in predictions):>13,.0f}  "
                  f"{sum(p.predicted_value for p in predictions):>13,.0f}")
            
            print(f"\n{'='*70}")
            print(f"  INSIGHTS & RECOMMENDATIONS")
            print(f"{'='*70}\n")
            
            total_net = sum(p.predicted_value for p in predictions)
            
            if cumulative_cash < -50000:
                print("   🔴 CRITICAL SITUATION")
                print(f"      Projected cumulative deficit: {cumulative_cash:,.0f} NOK")
                print("      ACTIONS NEEDED:")
                print("      • Chase all overdue invoices immediately")
                print("      • Delay non-critical expenses")
                print("      • Consider credit line/financing")
                print("      • Review cost structure urgently")
            elif cumulative_cash < 0:
                print("   🟡 CASH FLOW CHALLENGE")
                print(f"      Projected deficit: {cumulative_cash:,.0f} NOK")
                print("      ACTIONS RECOMMENDED:")
                print("      • Accelerate invoice collections")
                print("      • Defer non-urgent expenses")
                print("      • Monitor daily cash position")
            elif total_net < 50000:
                print("   🟠 TIGHT CASH FLOW")
                print(f"      Marginal surplus: {total_net:,.0f} NOK")
                print("      SUGGESTIONS:")
                print("      • Maintain collection focus")
                print("      • Build cash buffer when possible")
            else:
                print("   🟢 HEALTHY CASH FLOW")
                print(f"      Expected surplus: {total_net:,.0f} NOK")
                print("      OPPORTUNITIES:")
                print("      • Consider strategic investments")
                print("      • Build reserves for slower periods")
            
            # Calculate runway
            if total_net < 0:
                burn_rate = abs(total_net) / 3
                runway_months = total_outstanding / burn_rate if burn_rate > 0 else 999
                print(f"\n   💡 Cash Runway: ~{runway_months:.1f} months")
                print(f"      (If all receivables collected)")
            
            # Save predictions
            print(f"\n💾 Saving {len(predictions)} predictions to database...")
            self.save_predictions_batch(predictions)
            
            print(f"\n✅ Forecast complete!")
            print(f"{'='*70}\n")
            
            return predictions
            
        except Exception as e:
            print(f"❌ Prediction failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _categorize_cash_flow(self, cumulative: float) -> str:
        """Categorize overall cash position"""
        if cumulative < -100000:
            return "CRITICAL"
        elif cumulative < 0:
            return "NEGATIVE"
        elif cumulative < 50000:
            return "TIGHT"
        else:
            return "HEALTHY"
    
    def _get_confidence(self, scenario: str) -> float:
        """Return confidence score based on scenario"""
        if scenario == "realistic":
            return 0.75
        elif scenario == "best":
            return 0.60  # Less likely
        else:  # worst
            return 0.60  # Less likely
    
    def evaluate(self) -> Dict[str, float]:
        """Evaluate forecast accuracy (not implemented)"""
        print("Evaluation not yet implemented")
        return {}


def main():
    parser = argparse.ArgumentParser(description='Cash Flow Forecaster v2')
    parser.add_argument('--train', action='store_true', help='Not needed for v2')
    parser.add_argument('--predict', action='store_true', help='Generate forecast')
    parser.add_argument('--scenario', type=str, default='realistic',
                       choices=['best', 'realistic', 'worst'],
                       help='Forecast scenario (default: realistic)')
    parser.add_argument('--db', type=str, default='tfso-data.db', help='Database path')
    
    args = parser.parse_args()
    
    forecaster = CashFlowForecasterV2(db_path=args.db)
    
    if args.train:
        print("\n⚠️  Training not required for v2")
        print("   Run: python cash_flow_forecaster.py --predict")
        sys.exit(0)
    
    elif args.predict:
        predictions = forecaster.predict(scenario=args.scenario)
        sys.exit(0 if predictions else 1)
    
    else:
        print("Usage: python cash_flow_forecaster.py --predict [--scenario best|realistic|worst]")
        sys.exit(1)


if __name__ == "__main__":
    main()