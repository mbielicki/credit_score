# DESIGN: IRB Credit Rating & Loan Decision Engine

## 1. System Architecture
- **Monorepo**: `/backend` (FastAPI), `/frontend` (Streamlit), `/db` (Postgres migrations), `/infra` (GCP/External).
- **Primary Model**: Mączyńska & Zawadzki (2006) - Model 1 (INE PAN).
- **Database**: External Managed PostgreSQL (Neon or Supabase) for an always-free $0 tier.

## 2. Database Schema (PostgreSQL)

### 2.1. Tables
- `companies`
  - `id` (UUID, PK)
  - `nip` (VARCHAR(10), UNIQUE, INDEX) - Polish Tax ID.
  - `krs` (VARCHAR(10), UNIQUE) - National Court Register number.
  - `name` (VARCHAR(255))
  - `industry` (VARCHAR(100))
  - `created_at` (TIMESTAMP)

- `financial_statements`
  - `id` (UUID, PK)
  - `company_id` (UUID, FK -> companies.id)
  - `fiscal_year` (INT)
  - `total_assets` (DECIMAL)
  - `total_liabilities` (DECIMAL)
  - `equity` (DECIMAL)
  - `current_assets` (DECIMAL)
  - `current_liabilities` (DECIMAL)
  - `operating_profit` (DECIMAL) - EBIT.
  - `net_profit` (DECIMAL)
  - `gross_profit` (DECIMAL)
  - `sales_revenue` (DECIMAL)
  - `created_at` (TIMESTAMP)

- `credit_decisions`
  - `id` (UUID, PK)
  - `statement_id` (UUID, FK -> financial_statements.id)
  - `requested_amount` (DECIMAL)
  - `z_score` (DECIMAL)
  - `pd_percentage` (DECIMAL) - Probability of Default.
  - `rating_class` (VARCHAR(3)) - AAA, AA, A, BBB, BB, B, CCC, D.
  - `decision_status` (VARCHAR(20)) - APPROVED, REJECTED, MANUAL_REVIEW.
  - `decision_reason` (TEXT)
  - `created_at` (TIMESTAMP)

- `audit_logs`
  - `id` (UUID, PK)
  - `table_name` (VARCHAR(50))
  - `record_id` (UUID)
  - `action` (VARCHAR(10)) - INSERT, UPDATE, DELETE.
  - `old_values` (JSONB)
  - `new_values` (JSONB)
  - `changed_at` (TIMESTAMP)

## 3. Mathematical Engine: Mączyńska (2006)

### 3.1. Ratios ($X_1$ to $X_5$)
1.  **$X_1$ (Basic Earnings Power)** = Operating Profit / Total Assets
2.  **$X_2$ (Equity Coverage)** = Equity / Total Assets
3.  **$X_3$ (ROA)** = Net Profit / Total Assets
4.  **$X_4$ (Gross Margin)** = Gross Profit / Sales Revenue
5.  **$X_5$ (Current Liquidity)** = Current Assets / Current Liabilities

### 3.2. Formula
$$Z = 9.478 \cdot X_1 + 3.613 \cdot X_2 + 3.256 \cdot X_3 + 0.454 \cdot X_4 + 0.802 \cdot X_5 - 2.478$$

### 3.3. Rating Mapping
| Z-Score Range | Rating Class | Risk Profile | PD (Est.) |
| :--- | :--- | :--- | :--- |
| $Z > 3.0$ | **AAA** | Exceptional | < 0.01% |
| $2.5 < Z \le 3.0$ | **AA** | Very Strong | 0.02% |
| $2.0 < Z \le 2.5$ | **A** | Strong | 0.05% |
| $1.0 < Z \le 2.0$ | **BBB** | Good | 0.20% |
| $0.5 < Z \le 1.0$ | **BB** | Speculative | 1.00% |
| $0.0 < Z \le 0.5$ | **B** | Highly Speculative | 5.00% |
| $-1.0 < Z \le 0.0$ | **CCC** | Substantial Risk | 20.00% |
| $Z \le -1.0$ | **D** | Default | > 50.00% |

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
