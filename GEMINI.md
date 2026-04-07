# IRB Credit Rating & Loan Decision Engine

## Project Overview
A demo corporate credit rating system for the Polish market using the **Mączyńska Model G (2006)** to predict bankruptcy probability (PD) for SMEs. This model utilizes 4 financial indicators: operating profitability, equity ratio, debt service coverage (cash flow based), and current liquidity.

## Architecture
- **Monorepo Structure**:
  - `/backend`: FastAPI (Python) - Calculation engine and API.
  - `/frontend`: Streamlit (Python) - Analyst dashboard.
  - `/db`: PostgreSQL (External Managed like Neon/Supabase) - ACID-compliant schema, triggers, and stored procedures.
  - `/infra`: GCP configuration (Docker, Cloud Run, Cloud Build).
- **Core Technology**:
  - Language: Python (Type Hints, Pydantic, Pytest).
  - Database: PostgreSQL (Normalized schema, Triggers, CTEs).
  - Environment: Containerized with Docker and deployed to GCP.

## Development Workflow & Mandates
### 1. Research -> Strategy -> Execution
For every feature or bug, follow the full lifecycle:
1.  **Research**: Use `grep_search`, `glob`, and `read_file` to understand dependencies.
2.  **Strategy**: Share a concise plan before implementation.
3.  **Execution**: Apply changes using a **Plan -> Act -> Validate** cycle.

### 2. The "Contract-First" Rule
- Major changes must update the project's design document (once created).
- All API changes must be reflected in Pydantic models first.

### 3. Verification Protocol (Mandatory)
- Every code change **MUST** be verified by running:
  - `pytest`: `uv run --project backend pytest backend/tests`
  - `ruff`: `uv run --project backend ruff check backend`
  - `mypy`: `uv run --project backend mypy backend`
- No change is complete without an accompanying test or a successful test run.

### 4. Database Integrity
- All database operations for a single rating generation must be transactional (ACID).
- Use `db/migrations` for schema changes.

## Agent Guidelines
- ** Hallucination Mitigation**: Always check `GEMINI.md` and `DESIGN.md` (to be created) before suggesting implementations.
- **Surgical Updates**: Prefer small, focused updates via `replace` rather than rewriting entire files.
- **Proactive Questioning**: If a business rule (e.g., bankruptcy math) is ambiguous, stop and ask the user for clarification.
