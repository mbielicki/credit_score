# IRB Credit Rating Engine: Agentic Development Guide

## Project Context
A corporate credit rating system for the Polish market using the **Mączyńska Model G (2006)**.
- **Model Equation**: $Z = 9.498x_2 + 3.566x_5 + 2.903x_7 + 0.452x_9 - 1.498$
- **Ratios**: $x_2$ (Op. Profit/Assets), $x_5$ (Equity/Assets), $x_7$ (CF/Liabilities), $x_9$ (Assets/Liabilities).

## Monorepo Architecture
- `/backend`: FastAPI + SQLModel (SQLAlchemy 2.0).
- `/frontend`: Streamlit dashboard.
- `/db`: PostgreSQL schema, stored procedures, and views.
- `/infra`: Docker/GCP deployment.

## Core Development Mandates

### 1. Verification Protocol (CRITICAL)
Every code change **MUST** pass these checks before completion:
- **FastAPI/Logic**: `uv run --project backend pytest backend/tests`
- **Linting**: `uv run --project backend ruff check backend --fix`
- **Type Safety**: `uv run --project backend mypy backend`

### 2. Contract-First & Type Integrity
- API changes must be reflected in `backend/app/models.py` (Pydantic/SQLModel) before logic updates.
- All relationships must use string forward references to avoid SQLAlchemy mapping issues.
- Use `session.execute()` for raw SQL/Commands and `session.exec()` for SQLModel Selects.

### 3. Database-Native Strategy
- Core rating math and audit logging reside in PostgreSQL (Stored Procedures/Triggers).
- Maintain transactional integrity (ACID) for all rating generation events.
- Audit logs MUST capture analyst ID via `set_config('app.current_user', user_id, true)`.

### 4. Task Tracking & State
- **Source of Truth**: The `TODO.md` file tracks the current state of development.
- **Mandate**: Agents MUST read `TODO.md` at the start of a session and update it (mark completed, add new tasks) before ending.

## Agent Guidelines
- **Surgical Edits**: Use `replace` for targeted updates; avoid full file rewrites.
- **Context Awareness**: Always check `db/init.sql` for the source of truth on stored procedures and `backend/app/models.py` for the API contract.
- **NIP Validation**: Polish Tax ID (NIP) checksum validation is mandatory in all company-related models.
- **Anonymization**: NEVER use real company names, NIPs, or KRS numbers in the codebase (tests, seed data, or documentation). Always use fictional, generated data for testing and examples.
