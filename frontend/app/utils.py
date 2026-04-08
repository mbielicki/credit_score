import streamlit as st
import os
import requests
import random

# Configuration
BACKEND_URL = (os.getenv("BACKEND_URL") or "http://localhost:8000").strip().rstrip("/")

def get_portfolio_summary():
    try:
        response = requests.get(f"{BACKEND_URL}/portfolio/summary", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching portfolio summary: {e}")
        return []

def get_company_history(nip: str):
    try:
        response = requests.get(f"{BACKEND_URL}/companies/{nip}/history", timeout=30)
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
            
        requests.post(f"{BACKEND_URL}/companies", json=company_payload, timeout=30).raise_for_status()
        
        # Then submit statement
        # Remove frontend-only fields
        stmt_payload = {k: v for k, v in payload.items() if not k.startswith("company_")}
        stmt_payload["company_nip"] = payload["company_nip"]
        
        response = requests.post(f"{BACKEND_URL}/statements", json=stmt_payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error submitting rating: {e}")
        return None

def init_session_state():
    if "saved_form_data" not in st.session_state:
        st.session_state.saved_form_data = {
            "company_nip": "",
            "company_name": "Auto-generated Name",
            "company_krs": "",
            "company_industry": "Manufacturing",
            "fiscal_year": 2024,
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "equity": 0.0,
            "current_assets": 0.0,
            "current_liabilities": 0.0,
            "operating_profit": 0.0,
            "net_profit": 0.0,
            "sales_revenue": 0.0,
            "requested_amount": 0.0
        }

def generate_valid_nip():
    """Generates a valid Polish NIP with correct checksum."""
    while True:
        digits = [random.randint(0, 9) for _ in range(9)]
        weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
        checksum = sum(w * d for w, d in zip(weights, digits)) % 11
        if checksum < 10:
            return "".join(map(str, digits)) + str(checksum)

def generate_mock_data():
    # Generate round assets (nearest 10,000)
    assets = round(random.uniform(1000000, 50000000), -4)
    # Liabilities around 40-60% of assets (nearest 1,000)
    liabilities = round(assets * random.uniform(0.4, 0.6), -3)
    
    data = st.session_state.saved_form_data
    data["company_nip"] = generate_valid_nip()
    data["company_name"] = f"Mock Company {random.randint(100, 999)} Sp. z o.o."
    data["company_industry"] = random.choice(["Manufacturing", "Services", "Trade", "Construction", "Other"])
    data["total_assets"] = assets
    data["total_liabilities"] = liabilities
    data["equity"] = round(assets - liabilities, -3)
    data["current_assets"] = round(assets * random.uniform(0.3, 0.5), -3)
    data["current_liabilities"] = round(liabilities * random.uniform(0.5, 0.7), -3)
    data["operating_profit"] = round(assets * random.uniform(0.1, 0.2), -3)
    data["net_profit"] = round(data["operating_profit"] * 0.81, -3)
    data["sales_revenue"] = round(assets * random.uniform(1.2, 2.0), -4)
    data["requested_amount"] = round(random.uniform(500000, 5000000), -4)
    st.session_state.saved_form_data = data
