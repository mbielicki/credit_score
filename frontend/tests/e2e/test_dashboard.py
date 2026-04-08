import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
    }

def test_dashboard_navigation(page: Page):
    # Streamlit running on 8501
    page.goto("http://localhost:8501")
    
    # Check title
    expect(page).to_have_title("IRB Credit Rating Engine")
    expect(page.get_by_text("IRB Credit Rating & Loan Decision Engine")).to_be_visible()

    # Check Sidebar
    expect(page.get_by_text("Navigation")).to_be_visible()
    
    # Go to Company History
    page.get_by_text("Company History", exact=True).click()
    expect(page.get_by_text("Company Rating History")).to_be_visible()
    
    # Go to Dashboard
    page.get_by_text("Dashboard", exact=True).click()
    expect(page.get_by_text("Portfolio Risk Dashboard")).to_be_visible()
    
    # Go to New Rating
    page.get_by_text("New Rating", exact=True).click()
    expect(page.get_by_text("Submit New Financial Statement")).to_be_visible()

def test_submit_new_rating_flow(page: Page):
    page.goto("http://localhost:8501")
    page.get_by_text("New Rating").click()
    
    # Fill form (Valid NIP 1234563218)
    page.get_by_label("NIP (Required)").fill("1234563218")
    page.get_by_label("Company Name").fill("Playwright Test Corp")
    
    # Financials
    page.get_by_label("Fiscal Year").fill("2024")
    page.get_by_label("Total Assets").fill("1000")
    page.get_by_label("Total Liabilities").fill("500")
    page.get_by_label("Equity").fill("500")
    page.get_by_label("Current Assets").fill("400")
    page.get_by_label("Current Liabilities").fill("200")
    page.get_by_label("Operating Profit (EBIT)").fill("100")
    page.get_by_label("Net Profit").fill("80")
    page.get_by_label("Sales Revenue").fill("2000")
    
    page.get_by_role("button", name="Generate Rating").click()
    
    # Expect success
    expect(page.get_by_text("Rating generated successfully!")).to_be_visible()
    expect(page.get_by_text("Rating Class")).to_be_visible()
    expect(page.get_by_text("Z-Score")).to_be_visible()
