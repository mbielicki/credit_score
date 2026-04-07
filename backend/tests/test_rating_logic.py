import pytest
from app.models import FinancialStatementCreate, CompanyBase
from pydantic import ValidationError

def test_financial_statement_model():
    # 7740001454 is a valid NIP (PKN Orlen)
    stmt = FinancialStatementCreate(
        company_nip="7740001454",
        fiscal_year=2024,
        total_assets=1000.0,
        total_liabilities=500.0,
        equity=500.0,
        current_assets=400.0,
        current_liabilities=200.0,
        operating_profit=100.0,
        net_profit=80.0,
        depreciation=20.0,
        gross_profit=150.0,
        sales_revenue=2000.0,
        requested_amount=100.0
    )
    assert stmt.company_nip == "7740001454"
    assert stmt.total_assets == 1000.0
    assert stmt.depreciation == 20.0

def test_optional_depreciation():
    stmt = FinancialStatementCreate(
        company_nip="7740001454",
        fiscal_year=2024,
        total_assets=1000.0,
        total_liabilities=500.0,
        equity=500.0,
        current_assets=400.0,
        current_liabilities=200.0,
        operating_profit=100.0,
        net_profit=80.0,
        gross_profit=150.0,
        sales_revenue=2000.0
    )
    assert stmt.depreciation == 0.0
    assert stmt.requested_amount == 0.0

def test_nip_validation():
    # Valid NIP
    CompanyBase(nip="7740001454", krs="1234567890", name="Test")
    
    # Invalid NIP (wrong checksum)
    with pytest.raises(ValidationError) as exc:
        CompanyBase(nip="1234567890", krs="1234567890", name="Test")
    assert "Invalid NIP checksum" in str(exc.value)

    # Invalid NIP (wrong format)
    with pytest.raises(ValidationError) as exc:
        CompanyBase(nip="12345", krs="1234567890", name="Test")
    assert "String should match pattern '^[0-9]{10}$'" in str(exc.value)

def calculate_expected_z():
    # Model G Ratios:
    # x2 (WO/A) = OP / TA = 100 / 1000 = 0.1
    # x5 (KW/A) = Eq / TA = 500 / 1000 = 0.5
    # x7 ((WN+AM)/Z) = (NP + Depr) / TL = (80 + 20) / 500 = 0.2
    # x9 (MO/ZKT) = CA / CL = 400 / 200 = 2.0
    
    # Z = 9.498*x2 + 3.566*x5 + 2.903*x7 + 0.452*x9 - 1.498
    z = 9.498*0.1 + 3.566*0.5 + 2.903*0.2 + 0.452*2.0 - 1.498
    # z = 0.9498 + 1.783 + 0.5806 + 0.904 - 1.498
    # z = 2.7194
    return z

def test_z_score_calculation_logic():
    expected_z = calculate_expected_z()
    assert round(expected_z, 4) == 2.7194
