import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (
    get_portfolio_summary,
    get_company_history,
    submit_rating,
    init_session_state,
    generate_mock_data
)

st.set_page_config(
    page_title="IRB Credit Rating Engine",
    page_icon="🏦",
    layout="wide"
)

# Initialize session state for persistent form data
init_session_state()

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
    
    if st.button("✨ Fill with Mock Data"):
        generate_mock_data()
        st.rerun()
    
    with st.form("rating_form"):
        data = st.session_state.saved_form_data
        st.subheader("Company Information")
        c1, c2 = st.columns(2)
        with c1:
            company_nip = st.text_input("NIP (Required)", max_chars=10, value=data["company_nip"])
            company_name = st.text_input("Company Name", value=data["company_name"])
        with c2:
            company_krs = st.text_input("KRS (Optional)", max_chars=10, value=data["company_krs"])
            industry_list = ["Manufacturing", "Services", "Trade", "Construction", "Other"]
            industry_idx = industry_list.index(data["company_industry"]) if data["company_industry"] in industry_list else 0
            company_industry = st.selectbox("Industry", industry_list, index=industry_idx)
            
        st.subheader("Financial Statement Data")
        f1, f2, f3 = st.columns(3)
        with f1:
            fiscal_year = st.number_input("Fiscal Year", min_value=2000, max_value=2026, value=data["fiscal_year"])
            total_assets = st.number_input("Total Assets", min_value=0.0, format="%.2f", value=data["total_assets"])
            total_liabilities = st.number_input("Total Liabilities", min_value=0.0, format="%.2f", value=data["total_liabilities"])
        with f2:
            equity = st.number_input("Equity", format="%.2f", value=data["equity"])
            current_assets = st.number_input("Current Assets", min_value=0.0, format="%.2f", value=data["current_assets"])
            current_liabilities = st.number_input("Current Liabilities", min_value=0.0, format="%.2f", value=data["current_liabilities"])
        with f3:
            operating_profit = st.number_input("Operating Profit (EBIT)", format="%.2f", value=data["operating_profit"])
            net_profit = st.number_input("Net Profit", format="%.2f", value=data["net_profit"])
            sales_revenue = st.number_input("Sales Revenue", min_value=0.0, format="%.2f", value=data["sales_revenue"])

        st.subheader("Loan Request")
        requested_amount = st.number_input("Requested Loan Amount (PLN)", min_value=0.0, step=1000.0, value=data["requested_amount"])
        
        # Hidden fields for model compatibility
        gross_profit = operating_profit # Approximation
        depreciation = 0.0

        submit_btn = st.form_submit_button("Generate Rating")
        
        if submit_btn:
            # Persistent storage update
            st.session_state.saved_form_data = {
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
                "sales_revenue": sales_revenue,
                "requested_amount": requested_amount
            }

            if not company_nip or len(company_nip) != 10:
                st.error("Valid NIP is required.")
            else:
                payload = st.session_state.saved_form_data.copy()
                payload["depreciation"] = depreciation
                payload["gross_profit"] = gross_profit
                
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
