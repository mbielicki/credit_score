from __future__ import annotations
import os
from sqlmodel import create_engine, Session
from typing import Generator

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback or raising error for development
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

engine = create_engine(
    DATABASE_URL,
    # Pool configuration similar to what was in main.py
    pool_size=5,
    max_overflow=15
)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
