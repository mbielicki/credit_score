import pytest
import os
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, text
from app.main import app
from app.database import get_session

# Use a separate database for tests if possible, or just use the current one if it's local
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/credit_score_db")

engine = create_engine(DATABASE_URL)

@pytest.fixture(name="db_init", scope="session", autouse=True)
def db_init_fixture():
    # Read and execute init.sql to ensure the schema, functions, and seed data are present
    init_sql_path = os.path.join(os.path.dirname(__file__), "../../db/init.sql")
    with open(init_sql_path, "r") as f:
        sql = f.read()
    
    with Session(engine) as session:
        # We need to execute the script. 
        # SQLModel doesn't have a direct "execute script" but we can use raw connection
        session.exec(text("DROP VIEW IF EXISTS vw_portfolio_risk_summary CASCADE"))
        session.exec(text("DROP VIEW IF EXISTS vw_financial_ratios CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS credit_decisions CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS financial_statements CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS companies CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS adjudication_rules CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS rating_bands CASCADE"))
        session.exec(text("DROP TABLE IF EXISTS rating_model_params CASCADE"))
        session.commit()
        
        # Now run the init script
        # Note: psycopg2 (or whatever driver) might have trouble with some SQL blocks,
        # but for this demo, we'll try to run it.
        # Splitting by common separators might be safer but let's try direct execute.
        session.exec(text(sql))
        session.commit()

@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override():
        return session
    
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
