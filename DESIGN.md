# DESIGN: IRB Credit Rating Engine

## 1. Database Schema (Source of Truth)

### Core Tables
- `rating_model_params`: Stores coefficients (JSONB) and active status for models.
- `rating_bands`: Maps Z-score ranges to Rating Classes (AAA-D) and PD percentages.
- `adjudication_rules`: Defines thresholds for Auto-Approve/Reject status.
- `companies`: Primary entity indexed by `nip` (Polish Tax ID).
- `financial_statements`: Raw financial inputs for rating calculations.
- `credit_decisions`: Stores generated ratings, Z-scores, and final adjudication.
- `audit_logs`: Transactional logs triggered by DB events.

### DB Logic
- **`vw_financial_ratios`**: Standardizes raw statement data into ratios ($x_2, x_5, x_7, x_9$).
- **`fn_generate_rating`**: Atomic stored procedure that:
  1. Fetches ratios from view.
  2. Applies coefficients from `rating_model_params`.
  3. Maps result to `rating_bands`.
  4. Applies `adjudication_rules`.
  5. Records decision and triggers audit.

## 2. Mathematical Engine: Mączyńska Model G (2006)

- **Equation**: $Z = 9.498 \cdot x_2 + 3.566 \cdot x_5 + 2.903 \cdot x_7 + 0.452 \cdot x_9 - 1.498$
- **Rating Mapping**:
  - `AAA`: $Z \ge 3.0$
  - `AA`: $2.5 \le Z < 3.0$
  - `A`: $2.0 \le Z < 2.5$
  - `BBB`: $1.0 \le Z < 2.0$ (Minimum for Auto-Approve)
  - `BB`: $0.5 \le Z < 1.0$
  - `B`: $0.0 \le Z < 0.5$
  - `CCC`: $-1.0 \le Z < 0.0$
  - `D`: $Z < -1.0$

## 3. API Contract (FastAPI)
- `POST /companies`: Upsert company metadata.
- `POST /statements`: Submit financials -> Trigger `fn_generate_rating` -> Return `EnrichedCreditDecision`.
- `GET /companies/{nip}/history`: Return historical `EnrichedCreditDecision` list.
- `GET /portfolio/summary`: Aggregated risk distribution via `vw_portfolio_risk_summary`.
