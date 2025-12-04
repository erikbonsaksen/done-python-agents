#!/usr/bin/env python3
"""
ML Agents Orchestrator

Runs all ML prediction agents in sequence.
Useful for scheduled jobs (daily/weekly predictions).

Usage:
    python run_all_agents.py --train-all    # Train all models
    python run_all_agents.py --predict-all  # Generate all predictions
    python run_all_agents.py --agent payment_risk --predict  # Run specific agent
"""

import argparse
import sys
from datetime import datetime
import subprocess


AGENTS = {
    'payment_risk': {
        'script': 'payment_risk_scorer.py',
        'description': 'Payment Risk Scoring',
        'frequency': 'daily'
    },
    # Add more agents as they're created
    # 'churn_risk': {
    #     'script': 'churn_risk_scorer.py',
    #     'description': 'Customer Churn Risk',
    #     'frequency': 'weekly'
    # },
    # 'cash_flow': {
    #     'script': 'cash_flow_forecaster.py',
    #     'description': 'Cash Flow Forecasting',
    #     'frequency': 'daily'
    # },
}


def run_agent(agent_name: str, action: str, db_path: str = 'tfso-data.db') -> bool:
    """Run a single agent"""
    if agent_name not in AGENTS:
        print(f"❌ Unknown agent: {agent_name}")
        return False
    
    agent = AGENTS[agent_name]
    script = agent['script']
    
    print(f"\n{'='*60}")
    print(f"  Running: {agent['description']}")
    print(f"{'='*60}")
    
    cmd = ['python', script, f'--{action}', '--db', db_path]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {agent['description']} - {action} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {agent['description']} - {action} failed")
        return False
    except FileNotFoundError:
        print(f"❌ Script not found: {script}")
        return False


def train_all(db_path: str):
    """Train all agents"""
    print(f"\n{'#'*60}")
    print(f"  TRAINING ALL ML AGENTS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")
    
    results = {}
    for agent_name, agent_info in AGENTS.items():
        success = run_agent(agent_name, 'train', db_path)
        results[agent_name] = success
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  TRAINING SUMMARY")
    print(f"{'='*60}")
    
    for agent_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {AGENTS[agent_name]['description']:30} {status}")
    
    total = len(results)
    successful = sum(results.values())
    print(f"\n  Total: {successful}/{total} agents trained successfully")
    print(f"{'='*60}\n")
    
    return all(results.values())


def predict_all(db_path: str):
    """Generate predictions from all agents"""
    print(f"\n{'#'*60}")
    print(f"  GENERATING PREDICTIONS FROM ALL AGENTS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")
    
    results = {}
    for agent_name, agent_info in AGENTS.items():
        success = run_agent(agent_name, 'predict', db_path)
        results[agent_name] = success
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  PREDICTION SUMMARY")
    print(f"{'='*60}")
    
    for agent_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {AGENTS[agent_name]['description']:30} {status}")
    
    total = len(results)
    successful = sum(results.values())
    print(f"\n  Total: {successful}/{total} agents completed successfully")
    print(f"{'='*60}\n")
    
    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description='ML Agents Orchestrator')
    parser.add_argument('--train-all', action='store_true', 
                       help='Train all agents')
    parser.add_argument('--predict-all', action='store_true', 
                       help='Generate predictions from all agents')
    parser.add_argument('--agent', type=str, 
                       help='Run specific agent')
    parser.add_argument('--train', action='store_true', 
                       help='Train specific agent')
    parser.add_argument('--predict', action='store_true', 
                       help='Predict with specific agent')
    parser.add_argument('--db', type=str, default='tfso-data.db', 
                       help='Database path')
    parser.add_argument('--list', action='store_true',
                       help='List all available agents')
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable ML Agents:")
        print("="*60)
        for name, info in AGENTS.items():
            print(f"  {name:20} - {info['description']}")
            print(f"  {'':20}   Runs: {info['frequency']}")
        print("="*60)
        sys.exit(0)
    
    if args.train_all:
        success = train_all(args.db)
        sys.exit(0 if success else 1)
    
    elif args.predict_all:
        success = predict_all(args.db)
        sys.exit(0 if success else 1)
    
    elif args.agent:
        if args.train:
            success = run_agent(args.agent, 'train', args.db)
            sys.exit(0 if success else 1)
        elif args.predict:
            success = run_agent(args.agent, 'predict', args.db)
            sys.exit(0 if success else 1)
        else:
            print("Please specify --train or --predict with --agent")
            sys.exit(1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()