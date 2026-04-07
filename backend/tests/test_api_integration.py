from fastapi.testclient import TestClient
from sqlmodel import Session, select, text
from app.models import Company

def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "IRB Credit Rating Engine API is active"

def test_create_company_integration(client: TestClient, session: Session):
    nip = "1234563218"
    data = {
        "nip": nip,
        "krs": "0000123456",
        "name": "Lumina-Vortex Solutions Sp. z o.o.",
        "industry": "Oil & Gas"
    }
    
    # 1. Test initial creation
    response = client.post("/companies", json=data)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["nip"] == nip
    assert res_json["name"] == "Lumina-Vortex Solutions Sp. z o.o."
    
    # Verify in DB
    company = session.exec(select(Company).where(Company.nip == nip)).first()
    assert company is not None
    if company:
        assert company.name == "Lumina-Vortex Solutions Sp. z o.o."
    
    # 2. Test upsert (ON CONFLICT)
    data["name"] = "Lumina-Vortex SA"
    response = client.post("/companies", json=data)
    assert response.status_code == 200
    assert response.json()["name"] == "Lumina-Vortex SA"
    
    session.expire_all() # Refresh session
    company_updated = session.exec(select(Company).where(Company.nip == nip)).first()
    assert company_updated is not None
    if company_updated:
        assert company_updated.name == "Lumina-Vortex SA"

def test_submit_statement_and_get_rating_integration(client: TestClient, session: Session):
    nip = "1234563218"
    # Ensure company exists
    client.post("/companies", json={
        "nip": nip,
        "krs": "0000123456",
        "name": "Lumina-Vortex SA",
        "industry": "Oil & Gas"
    })
    
    # Submit financial statement
    # Data derived from calculate_expected_z() in unit test:
    # Expected Z: 2.7194 (Rating A based on rating_bands in init.sql)
    stmt_data = {
        "company_nip": nip,
        "fiscal_year": 2024,
        "total_assets": 1000.0,
        "total_liabilities": 500.0,
        "equity": 500.0,
        "current_assets": 400.0,
        "current_liabilities": 200.0,
        "operating_profit": 100.0,
        "net_profit": 80.0,
        "depreciation": 20.0,
        "gross_profit": 150.0,
        "sales_revenue": 2000.0,
        "requested_amount": 500000.0
    }
    
    response = client.post("/statements", json=stmt_data)
    assert response.status_code == 200
    res_json = response.json()
    
    # Verify rating results from stored procedure
    assert "z_score" in res_json
    assert round(res_json["z_score"], 4) == 2.7194
    assert res_json["rating_class"] == "AA" # Z=2.71 is between 2.5 and 3.0 (AA)
    assert res_json["decision_status"] == "APPROVED"
    assert "model_name" in res_json
    assert res_json["model_name"] == "Maczynska_Zawadzki_Model_G"
    
    # Check audit logs (triggered by DB)
    audit_res = session.connection().execute(text("SELECT * FROM audit_logs WHERE table_name = 'credit_decisions'")).mappings().first()
    assert audit_res is not None
    assert audit_res["action"] == "INSERT"

def test_portfolio_summary_integration(client: TestClient):
    # This assumes previous tests inserted some data
    # or we can insert fresh data here. 
    # Since db_init is session scoped, we have ORLEN data from previous test.
    
    response = client.get("/portfolio/summary")
    assert response.status_code == 200
    summary = response.json()
    assert len(summary) > 0
    # At least one AA rating should exist from the previous test
    assert any(item["rating_class"] == "AA" for item in summary)
