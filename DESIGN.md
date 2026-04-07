# DESIGN: IRB Credit Rating & Loan Decision Engine

## 1. System Architecture
- **Monorepo**: `/backend` (FastAPI), `/frontend` (Streamlit), `/db` (Postgres migrations), `/infra` (GCP/External).
- **Primary Model**: Mączyńska & Zawadzki (2006) - Model 1 (INE PAN).
- **Database**: External Managed PostgreSQL (Neon or Supabase) for an always-free $0 tier.

## 2. Database Schema (PostgreSQL)

### 2.1. Model Configuration
- `rating_model_params`
  - `id` (UUID, PK)
  - `model_name` (VARCHAR(100))
  - `version` (VARCHAR(20))
  - `coefficients` (JSONB) - Dynamic weights (e.g., w1, intercept).
  - `is_active` (BOOLEAN)
  - `created_at` (TIMESTAMPTZ)

- `rating_bands`
  - `id` (UUID, PK)
  - `rating_model_id` (UUID, FK -> rating_model_params.id)
  - `min_z_score` (DECIMAL) - Inclusive lower bound.
  - `rating_class` (VARCHAR(3))
  - `pd_percentage` (DECIMAL)
  - `risk_profile` (VARCHAR(50))

- `adjudication_rules`
  - `id` (UUID, PK)
  - `rating_model_id` (UUID, FK -> rating_model_params.id)
  - `rating_class` (VARCHAR(3))
  - `max_amount` (DECIMAL) - NULL for any amount.
  - `decision_status` (ENUM: APPROVED, REJECTED, MANUAL_REVIEW)
  - `priority` (INT)

### 2.2. Core Entities
- `companies`
  - `id` (UUID, PK)
  - `nip` (VARCHAR(10), UNIQUE, INDEX) - Polish Tax ID.
  - `krs` (VARCHAR(10), UNIQUE) - National Court Register number.
  - `name` (VARCHAR(255))
  - `industry` (VARCHAR(100))
  - `created_at` (TIMESTAMPTZ)

- `financial_statements`
  - `id` (UUID, PK)
  - `company_id` (UUID, FK -> companies.id)
  - `fiscal_year` (INT)
  - `total_assets` (DECIMAL)
  - `total_liabilities` (DECIMAL)
  - `equity` (DECIMAL)
  - `current_assets` (DECIMAL)
  - `current_liabilities` (DECIMAL)
  - `operating_profit` (DECIMAL)
  - `net_profit` (DECIMAL)
  - `depreciation` (DECIMAL)
  - `gross_profit` (DECIMAL)
  - `sales_revenue` (DECIMAL)
  - `created_at` (TIMESTAMPTZ)

- `credit_decisions`
  - `id` (UUID, PK)
  - `statement_id` (UUID, FK -> financial_statements.id, ON DELETE RESTRICT)
  - `rating_model_id` (UUID, FK -> rating_model_params.id)
  - `requested_amount` (DECIMAL)
  - `z_score` (DECIMAL)
  - `pd_percentage` (DECIMAL)
  - `rating_class` (VARCHAR(3))
  - `decision_status` (ENUM: APPROVED, REJECTED, MANUAL_REVIEW)
  - `decision_reason` (TEXT)
  - `created_at` (TIMESTAMPTZ)

- `audit_logs`
  - `id` (UUID, PK)
  - `table_name` (VARCHAR(50))
  - `record_id` (UUID)
  - `action` (ENUM: INSERT, UPDATE, DELETE)
  - `old_values` (JSONB)
  - `new_values` (JSONB)
  - `changed_by` (VARCHAR(100))
  - `changed_at` (TIMESTAMPTZ)

## 3. Mathematical Engine: Mączyńska Model G (2006)

### 3.1. Ratios (Model G)
1.  **$x_2$ (Operating Profitability of Assets)** = Operating Profit / Total Assets
2.  **$x_5$ (Equity Ratio)** = Equity / Total Assets
3.  **$x_7$ (Debt Service Coverage)** = (Net Profit + Depreciation) / Total Liabilities
4.  **$x_9$ (Current Liquidity)** = Current Assets / Current Liabilities

### 3.2. Formula (Model G)
$Z = 9.498 \cdot x_2 + 3.566 \cdot x_5 + 2.903 \cdot x_7 + 0.452 \cdot x_9 - 1.498$

The engine dynamically iterates through `rating_model_params.coefficients`. 
It calculates $Z$ as a weighted sum of available ratios plus an `intercept`.
Checks for missing coefficients or NULL values to prevent calculation errors.

### 3.3. Rating Mapping
Thresholds are **inclusive at the lower bound** ($Z \ge min\_z\_score$).

| Z-Score Range | Rating Class | Risk Profile | PD (Est.) |
| :--- | :--- | :--- | :--- |
| $Z \ge 3.0$ | **AAA** | Exceptional | < 0.01% |
| $2.5 \le Z < 3.0$ | **AA** | Very Strong | 0.02% |
| $2.0 \le Z < 2.5$ | **A** | Strong | 0.05% |
| $1.0 \le Z < 2.0$ | **BBB** | Good | 0.20% |
| $0.5 \le Z < 1.0$ | **BB** | Speculative | 1.00% |
| $0.0 \le Z < 0.5$ | **B** | Highly Speculative | 5.00% |
| $-1.0 \le Z < 0.0$ | **CCC** | Substantial Risk | 20.00% |
| $Z < -1.0$ | **D** | Default | > 50.00% |

## 8. Roadmap & Future Improvements
- **Application User Context**: Implement `SET LOCAL app.current_user` in the FastAPI backend to ensure `audit_logs` capture the actual analyst's ID instead of the generic database user.
- **Dynamic Ratio Definitions**: Move ratio calculation logic from SQL into a configurable metadata table if non-standard models are added.
- **Bulk Import**: Support CSV/Excel uploads for financial statements.

## 4. Loan Adjudication Rules
1.  **Auto-Reject**: If `rating_class` is **D** or **CCC**.
2.  **Auto-Approve**: If `rating_class` $\ge$ **BBB** AND `requested_amount` < 1,000,000 PLN.
3.  **Manual Review**: All other cases (e.g., BB rating or high amount).

## 5. API Specification (FastAPI)

### 5.1. Endpoints
- `POST /companies`: Create/Update company.
- `POST /statements`: Submit financials and trigger `fn_generate_rating`.
- `GET /companies/{nip}/history`: View historical ratings.
- `GET /portfolio/summary`: Aggregated risk views.

## 6. Advanced SQL Implementation
- **Procedure**: `fn_generate_rating(stmt_id UUID)`
  - Calculates ratios, $Z$, and mapping in one transaction.
  - Inserts into `credit_decisions`.
- **Trigger**: `trg_audit_rating`
  - Automatically logs every rating event.
- **View**: `vw_portfolio_risk_summary`
  - Monthly distribution of ratings using `GROUP BY` and `COUNT`.

## 7. Deployment Strategy ($0 Cost)
- **Cloud Run**: Stateless containers for API and Streamlit (GCP Always Free tier allows up to 2 million requests/month).
- **Database**: External Managed PostgreSQL (Neon or Supabase always-free tier).
- **Artifact Registry**: Docker image storage (Free up to 500MB on GCP).
