# IRB Credit Rating & Loan Decision Engine

A corporate credit rating system for the Polish market using the Hołda/Mączyńska model to predict bankruptcy probability (PD) for SMEs.

## Project Structure
- `/backend`: FastAPI (Python) - Calculation engine and API.
- `/frontend`: Streamlit (Python) - Analyst dashboard.
- `/db`: PostgreSQL - Advanced schema with dynamic calculation engine, audit triggers, and de-hardcoded business rules.
- `/infra`: GCP configuration for containerized deployment.

## Key Features
- **Dynamic Rating Engine**: Z-score calculation based on configurable coefficients in `rating_model_params`.
- **De-hardcoded Rules**: Rating bands and adjudication logic stored in database tables for easy adjustment without code changes.
- **Robust Audit Trail**: Automated logging of all data changes, including user context and value diffs.
- **Financial Ratios**: Implementation of Polish-specific bankruptcy models (Mączyńska 2006).

## Documentation
- [GEMINI.md](./GEMINI.md): Project mandates, development workflow, and coding standards.
