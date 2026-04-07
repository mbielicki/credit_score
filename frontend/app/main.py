import streamlit as st
import os
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="IRB Credit Rating Engine",
    page_icon="🏦",
    layout="wide"
)

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ST_SIDEBAR_STATE = "expanded"

# --- Helper Functions ---

def get_portfolio_summary():
    try:
        response = requests.get(f"{BACKEND_URL}/portfolio/summary", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching portfolio summary: {e}")
        return []

def get_company_history(nip: str):
    try:
        response = requests.get(f"{BACKEND_URL}/companies/{nip}/history", timeout=5)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching company history: {e}")
        return []

def submit_rating(payload: dict):
    try:
        # First ensure company exists/updated
        company_payload = {
            "nip": str(payload["company_nip"]),
            "name": payload.get("company_name", "Unknown")
        }
        if payload.get("company_krs"):
            company_payload["krs"] = str(payload["company_krs"])
        if payload.get("company_industry"):
            company_payload["industry"] = payload["company_industry"]
            
        requests.post(f"{BACKEND_URL}/companies", json=company_payload, timeout=5).raise_for_status()
        
        # Then submit statement
        # Remove frontend-only fields
        stmt_payload = {k: v for k, v in payload.items() if not k.startswith("company_")}
        stmt_payload["company_nip"] = payload["company_nip"]
        
        response = requests.post(f"{BACKEND_URL}/statements", json=stmt_payload, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error submitting rating: {e}")
        return None

# --- UI Components ---

st.title("🏦 IRB Credit Rating & Loan Decision Engine")
st.markdown("---")

st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Company Analysis", "New Rating"])

if page == "Dashboard":
    st.header("📊 Portfolio Risk Dashboard")
    
    summary_data = get_portfolio_summary()
    
    if summary_data:
        df = pd.DataFrame(summary_data)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Risk Distribution")
            fig = px.pie(
                df, 
                values='count', 
                names='rating_class', 
                title='Portfolio by Rating Class',
                color='rating_class',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.subheader("Detailed Breakdown")
            st.table(df)
            
        # Total Stats
        total_cases = df['count'].sum()
        st.metric("Total Rated Portfolios", total_cases)
    else:
        st.warning("No portfolio data available yet.")

elif page == "Company Analysis":
    st.header("🔍 Company Rating History")
    
    with st.container():
        nip = st.text_input("Enter Company NIP (10 digits)", max_chars=10)
        
        if nip:
            if len(nip) == 10 and nip.isdigit():
                history = get_company_history(nip)
                
                if history:
                    df_history = pd.DataFrame(history)
                    df_history['created_at'] = pd.to_datetime(df_history['created_at'])
                    
                    st.subheader(f"History for NIP: {nip}")
                    
                    # Trend chart
                    fig_trend = px.line(
                        df_history, 
                        x='created_at', 
                        y='z_score', 
                        title='Z-Score Trend (Mączyńska Model G)',
                        markers=True
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
                    
                    # Detailed Table
                    st.dataframe(
                        df_history[['created_at', 'rating_class', 'z_score', 'pd_percentage', 'decision_status', 'risk_profile']],
                        use_container_width=True
                    )
                else:
                    st.info("No rating history found for this company.")
            else:
                st.error("Please enter a valid 10-digit NIP.")

elif page == "New Rating":
    st.header("📝 Submit New Financial Statement")
    
    with st.form("rating_form"):
        st.subheader("Company Information")
        c1, c2 = st.columns(2)
        with c1:
            company_nip = st.text_input("NIP (Required)", max_chars=10)
            company_name = st.text_input("Company Name", value="Auto-generated Name")
        with c2:
            company_krs = st.text_input("KRS (Optional)", max_chars=10)
            company_industry = st.selectbox("Industry", ["Manufacturing", "Services", "Trade", "Construction", "Other"])
            
        st.subheader("Financial Statement Data")
        f1, f2, f3 = st.columns(3)
        with f1:
            fiscal_year = st.number_input("Fiscal Year", min_value=2000, max_value=2026, value=2024)
            total_assets = st.number_input("Total Assets", min_value=0.0, format="%.2f")
            total_liabilities = st.number_input("Total Liabilities", min_value=0.0, format="%.2f")
        with f2:
            equity = st.number_input("Equity", format="%.2f")
            current_assets = st.number_input("Current Assets", min_value=0.0, format="%.2f")
            current_liabilities = st.number_input("Current Liabilities", min_value=0.0, format="%.2f")
        with f3:
            operating_profit = st.number_input("Operating Profit (EBIT)", format="%.2f")
            net_profit = st.number_input("Net Profit", format="%.2f")
            sales_revenue = st.number_input("Sales Revenue", min_value=0.0, format="%.2f")

        st.subheader("Loan Request")
        requested_amount = st.number_input("Requested Loan Amount (PLN)", min_value=0.0, step=1000.0)
        
        # Hidden fields for model compatibility
        gross_profit = operating_profit # Approximation
        depreciation = 0.0

        submit_btn = st.form_submit_button("Generate Rating")
        
        if submit_btn:
            if not company_nip or len(company_nip) != 10:
                st.error("Valid NIP is required.")
            else:
                payload = {
                    "company_nip": company_nip,
                    "company_name": company_name,
                    "company_krs": company_krs,
                    "company_industry": company_industry,
                    "fiscal_year": fiscal_year,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "equity": equity,
                    "current_assets": current_assets,
                    "current_liabilities": current_liabilities,
                    "operating_profit": operating_profit,
                    "net_profit": net_profit,
                    "depreciation": depreciation,
                    "gross_profit": gross_profit,
                    "sales_revenue": sales_revenue,
                    "requested_amount": requested_amount
                }
                
                result = submit_rating(payload)
                if result:
                    st.success("Rating generated successfully!")
                    
                    # Result Display
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Rating Class", result['rating_class'])
                    r2.metric("Z-Score", round(result['z_score'], 4))
                    r3.metric("Decision", result['decision_status'])
                    
                    st.info(f"**Risk Profile:** {result.get('risk_profile', 'N/A')}")
                    if result['decision_reason']:
                        st.write(f"**Reason:** {result['decision_reason']}")
