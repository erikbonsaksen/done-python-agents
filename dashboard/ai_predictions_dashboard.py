#!/usr/bin/env python3
"""
AI Predictions Dashboard

Visualizes predictions from ML agents:
- Payment Risk Scorer
- Cash Flow Forecaster
- Future: Churn Risk, Revenue Predictor, etc.

Usage:
    streamlit run dashboard/ai_predictions_dashboard.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import json

DB_PATH = "tfso-data.db"

# Page config
st.set_page_config(
    page_title="AI Predictions Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .big-metric {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin: 0;
    }
    .risk-high {
        color: #dc3545;
        font-weight: bold;
    }
    .risk-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .risk-low {
        color: #28a745;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_predictions(prediction_type: str = None):
    """Load predictions from database"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            id,
            prediction_type,
            entity_type,
            entity_id,
            entity_name,
            prediction_date,
            target_date,
            predicted_value,
            predicted_category,
            confidence_score,
            model_version,
            features_used,
            metadata,
            is_active,
            created_at
        FROM ml_predictions
        WHERE is_active = 1
    """
    
    if prediction_type:
        query += f" AND prediction_type = '{prediction_type}'"
    
    query += " ORDER BY prediction_date DESC, predicted_value DESC"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Parse JSON fields
    if len(df) > 0:
        df['features_used'] = df['features_used'].apply(lambda x: json.loads(x) if x else {})
        df['metadata'] = df['metadata'].apply(lambda x: json.loads(x) if x else {})
    
    return df


@st.cache_data(ttl=300)
def load_model_performance():
    """Load model performance metrics"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            model_name,
            model_type,
            evaluation_date,
            accuracy,
            precision_score,
            recall_score,
            f1_score,
            auc_roc,
            mae,
            rmse,
            r2_score
        FROM ml_model_performance
        ORDER BY evaluation_date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def main():
    st.title("🤖 AI Predictions Dashboard")
    st.markdown("Real-time insights from machine learning models")
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choose a view:",
        ["Overview", "Payment Risk", "Cash Flow Forecast", "Model Performance"]
    )
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Last updated
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Route to pages
    if page == "Overview":
        show_overview()
    elif page == "Payment Risk":
        show_payment_risk()
    elif page == "Cash Flow Forecast":
        show_cash_flow()
    elif page == "Model Performance":
        show_model_performance()


def show_overview():
    """Overview of all predictions"""
    st.header("📊 AI Predictions Overview")
    
    # Load all predictions
    predictions = load_predictions()
    
    if len(predictions) == 0:
        st.warning("⚠️ No predictions found. Run the ML agents first!")
        st.code("""
# Train and generate predictions:
python -m agents.payment_risk_scorer --train
python -m agents.payment_risk_scorer --predict
python agents/cash_flow_forecaster_v2.py --predict
        """)
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_predictions = len(predictions)
        st.metric("Total Predictions", total_predictions)
    
    with col2:
        prediction_types = predictions['prediction_type'].nunique()
        st.metric("Active Models", prediction_types)
    
    with col3:
        latest = predictions['prediction_date'].max()
        st.metric("Latest Prediction", latest)
    
    with col4:
        avg_confidence = predictions['confidence_score'].mean()
        st.metric("Avg Confidence", f"{avg_confidence:.1%}")
    
    st.markdown("---")
    
    # Predictions by type
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Predictions by Type")
        type_counts = predictions['prediction_type'].value_counts()
        
        fig = px.bar(
            x=type_counts.index,
            y=type_counts.values,
            labels={'x': 'Prediction Type', 'y': 'Count'},
            color=type_counts.values,
            color_continuous_scale='Blues'
        )
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Recent Predictions")
        recent = predictions.head(10)[['prediction_type', 'entity_name', 'predicted_category', 'prediction_date']]
        st.dataframe(recent, use_container_width=True, hide_index=True)


def show_payment_risk():
    """Payment risk predictions dashboard"""
    st.header("💳 Payment Risk Predictions")
    
    # Load payment risk predictions
    predictions = load_predictions('payment_risk')
    
    if len(predictions) == 0:
        st.warning("⚠️ No payment risk predictions found. Run the agent first:")
        st.code("python -m agents.payment_risk_scorer --predict")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    high_risk = len(predictions[predictions['predicted_category'] == 'HIGH'])
    medium_risk = len(predictions[predictions['predicted_category'] == 'MEDIUM'])
    low_risk = len(predictions[predictions['predicted_category'] == 'LOW'])
    
    total_at_risk = predictions['predicted_value'].sum()
    
    with col1:
        st.markdown('<p class="metric-label">High Risk Invoices</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="big-metric risk-high">{high_risk}</p>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<p class="metric-label">Medium Risk</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="big-metric risk-medium">{medium_risk}</p>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<p class="metric-label">Low Risk</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="big-metric risk-low">{low_risk}</p>', unsafe_allow_html=True)
    
    with col4:
        # Calculate total value at risk
        high_risk_invoices = predictions[predictions['predicted_category'] == 'HIGH']
        if len(high_risk_invoices) > 0:
            total_value = sum([meta.get('amount', 0) for meta in high_risk_invoices['metadata']])
            st.metric("High Risk Value", f"{total_value:,.0f} NOK")
        else:
            st.metric("High Risk Value", "0 NOK")
    
    st.markdown("---")
    
    # Risk distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Risk Distribution")
        
        risk_counts = predictions['predicted_category'].value_counts()
        colors = {'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#28a745'}
        
        fig = go.Figure(data=[go.Pie(
            labels=risk_counts.index,
            values=risk_counts.values,
            marker=dict(colors=[colors.get(cat, '#999') for cat in risk_counts.index]),
            hole=0.4
        )])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Risk Probability Distribution")
        
        fig = px.histogram(
            predictions,
            x='predicted_value',
            nbins=20,
            labels={'predicted_value': 'Late Payment Probability'},
            color_discrete_sequence=['#1f77b4']
        )
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    # High risk invoices table
    st.subheader("⚠️ High Risk Invoices - Action Required")
    
    high_risk_df = predictions[predictions['predicted_category'] == 'HIGH'].copy()
    
    if len(high_risk_df) > 0:
        # Extract metadata
        high_risk_df['amount'] = high_risk_df['metadata'].apply(lambda x: x.get('amount', 0))
        high_risk_df['due_date'] = high_risk_df['metadata'].apply(lambda x: x.get('due_date', 'N/A'))
        high_risk_df['risk_pct'] = (high_risk_df['predicted_value'] * 100).round(1)
        
        display_df = high_risk_df[[
            'entity_name', 'risk_pct', 'amount', 'due_date', 'confidence_score'
        ]].sort_values('risk_pct', ascending=False)
        
        display_df.columns = ['Invoice', 'Risk %', 'Amount (NOK)', 'Due Date', 'Confidence']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.info("💡 Tip: Contact these customers proactively to ensure timely payment")
    else:
        st.success("✅ No high-risk invoices detected!")


def show_cash_flow():
    """Cash flow forecast dashboard"""
    st.header("💰 Cash Flow Forecast")
    
    # Load cash flow predictions
    predictions = load_predictions('cash_flow')
    
    if len(predictions) == 0:
        st.warning("⚠️ No cash flow predictions found. Run the forecaster first:")
        st.code("python agents/cash_flow_forecaster_v2.py --predict")
        return
    
    # Get scenarios
    scenarios = predictions['metadata'].apply(lambda x: x.get('scenario', 'realistic')).unique()
    
    selected_scenario = st.selectbox("Select Scenario:", scenarios, index=list(scenarios).index('realistic') if 'realistic' in scenarios else 0)
    
    scenario_predictions = predictions[
        predictions['metadata'].apply(lambda x: x.get('scenario') == selected_scenario)
    ].sort_values('target_date')
    
    if len(scenario_predictions) == 0:
        st.warning(f"No predictions for {selected_scenario} scenario")
        return
    
    # Extract data
    months = []
    inflows = []
    outflows = []
    net_flows = []
    cumulative = []
    ar_collections = []
    new_revenue = []
    
    for _, row in scenario_predictions.iterrows():
        meta = row['metadata']
        months.append(meta.get('month', 'Unknown'))
        ar_collections.append(meta.get('ar_collections', 0))
        new_revenue.append(meta.get('new_revenue', 0))
        inflows.append(meta.get('inflow', 0))
        outflows.append(meta.get('outflow', 0))
        net_flows.append(meta.get('net', 0))
        cumulative.append(meta.get('cumulative', 0))
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Expected Inflows", f"{sum(inflows):,.0f} NOK")
    
    with col2:
        st.metric("Total Expected Outflows", f"{sum(outflows):,.0f} NOK")
    
    with col3:
        total_net = sum(net_flows)
        st.metric("Net Cash Flow (3mo)", f"{total_net:,.0f} NOK", 
                 delta=f"{total_net:,.0f}" if total_net >= 0 else f"{total_net:,.0f}")
    
    with col4:
        final_position = cumulative[-1] if cumulative else 0
        status = "🟢 Healthy" if final_position > 0 else "🔴 Negative"
        st.metric("Final Position", f"{final_position:,.0f} NOK", delta=status)
    
    st.markdown("---")
    
    # Cash flow waterfall
    st.subheader("📊 Monthly Cash Flow Breakdown")
    
    fig = go.Figure()
    
    # Stacked bar chart
    fig.add_trace(go.Bar(
        name='AR Collections',
        x=months,
        y=ar_collections,
        marker_color='lightblue'
    ))
    
    fig.add_trace(go.Bar(
        name='New Revenue',
        x=months,
        y=new_revenue,
        marker_color='blue'
    ))
    
    fig.add_trace(go.Bar(
        name='Outflows',
        x=months,
        y=[-o for o in outflows],
        marker_color='red'
    ))
    
    fig.update_layout(
        barmode='relative',
        title=f"Cash Flow Forecast - {selected_scenario.capitalize()} Scenario",
        yaxis_title="NOK",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Cumulative cash position
    st.subheader("📈 Cumulative Cash Position")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=months,
        y=cumulative,
        mode='lines+markers',
        name='Cumulative Cash',
        line=dict(color='green' if cumulative[-1] > 0 else 'red', width=3),
        marker=dict(size=10)
    ))
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break Even")
    
    fig.update_layout(
        title="Projected Cash Position",
        yaxis_title="NOK",
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed table
    st.subheader("📋 Detailed Forecast")
    
    forecast_df = pd.DataFrame({
        'Month': months,
        'AR Collections': ar_collections,
        'New Revenue': new_revenue,
        'Total Inflows': inflows,
        'Outflows': outflows,
        'Net Cash Flow': net_flows,
        'Cumulative': cumulative
    })
    
    st.dataframe(forecast_df.style.format("{:,.0f}"), use_container_width=True, hide_index=True)
    
    # Insights
    st.subheader("💡 Insights")
    
    if final_position < -50000:
        st.error(f"""
        🔴 **CRITICAL**: Projected deficit of {final_position:,.0f} NOK
        
        **Immediate Actions:**
        - Chase all overdue invoices
        - Consider credit line or financing
        - Review and reduce non-essential expenses
        """)
    elif final_position < 0:
        st.warning(f"""
        🟡 **CAUTION**: Projected deficit of {final_position:,.0f} NOK
        
        **Recommended Actions:**
        - Accelerate collections
        - Monitor cash daily
        - Prepare contingency plans
        """)
    else:
        st.success(f"""
        🟢 **HEALTHY**: Projected surplus of {final_position:,.0f} NOK
        
        **Opportunities:**
        - Consider strategic investments
        - Build cash reserves
        - Plan for growth
        """)


def show_model_performance():
    """Model performance metrics"""
    st.header("📈 Model Performance")
    
    perf = load_model_performance()
    
    if len(perf) == 0:
        st.warning("⚠️ No performance metrics found. Train models first.")
        return
    
    # Show latest performance for each model
    latest_perf = perf.groupby('model_name').first().reset_index()
    
    for _, model in latest_perf.iterrows():
        with st.expander(f"🤖 {model['model_name']} - {model['model_type'].capitalize()}", expanded=True):
            
            col1, col2, col3, col4 = st.columns(4)
            
            if model['model_type'] == 'classification':
                with col1:
                    st.metric("Accuracy", f"{model['accuracy']:.1%}" if pd.notna(model['accuracy']) else "N/A")
                with col2:
                    st.metric("Precision", f"{model['precision_score']:.1%}" if pd.notna(model['precision_score']) else "N/A")
                with col3:
                    st.metric("Recall", f"{model['recall_score']:.1%}" if pd.notna(model['recall_score']) else "N/A")
                with col4:
                    st.metric("AUC-ROC", f"{model['auc_roc']:.1%}" if pd.notna(model['auc_roc']) else "N/A")
            
            elif model['model_type'] == 'regression' or model['model_type'] == 'forecasting':
                with col1:
                    st.metric("MAE", f"{model['mae']:.2f}" if pd.notna(model['mae']) else "N/A")
                with col2:
                    st.metric("RMSE", f"{model['rmse']:.2f}" if pd.notna(model['rmse']) else "N/A")
                with col3:
                    st.metric("R²", f"{model['r2_score']:.2%}" if pd.notna(model['r2_score']) else "N/A")
            
            st.caption(f"Last evaluated: {model['evaluation_date']}")


if __name__ == "__main__":
    main()