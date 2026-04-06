import streamlit as st
import os

st.set_page_config(page_title="IRB Credit Rating Engine", layout="wide")

st.title("🏦 IRB Credit Rating & Loan Decision Engine")
st.markdown("### Analyst Dashboard")

backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

st.info(f"Connected to Backend: {backend_url}")

st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Company History", "New Rating"])

if page == "Dashboard":
    st.write("Welcome to the Credit Rating Dashboard. Select an action from the sidebar.")
elif page == "New Rating":
    st.write("Submit financial statements to generate a new credit rating.")
elif page == "Company History":
    st.write("View historical ratings for a specific company.")
