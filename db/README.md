# Database Setup & Migrations

This directory contains the database schema and logic for the IRB Credit Engine.

## Tech Stack
- **Database**: PostgreSQL 15+
- **Extensions**: `pgcrypto` (for UUID generation)

## Applying the Schema

To apply the schema to a new database (e.g., Neon, Supabase, or local Postgres), follow these steps:

### 1. Connection
Connect to your PostgreSQL instance using `psql` or any SQL client (DBeaver, pgAdmin, etc.).

### 2. Execution
Run the `init.sql` script:

```bash
psql -h <host> -U <user> -d <database> -f db/init.sql
```

Or copy-paste the contents of `db/init.sql` into your SQL editor and execute all statements.

### 3. Verification
Verify that the tables and views were created:

```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
SELECT view_name FROM information_schema.views WHERE table_schema = 'public';
```

## Features Included
- **Dynamic Rating Engine**: 
  - `fn_generate_rating(stmt_id UUID, requested_amount DECIMAL)`:
    - Calculates the Z-score dynamically using coefficients from `rating_model_params`.
    - Handles edge cases like zero-liability (capped current ratio).
    - Robust error handling for missing coefficients or NULL values.
- **De-hardcoded Business Logic**: 
  - `rating_bands`: Configurable Z-score thresholds and PD mappings (inclusive lower bounds).
  - `adjudication_rules`: Configurable auto-approval/rejection logic based on rating and amount.
- **Generic Audit System**: 
  - `fn_audit_generic()`: A centralized trigger function that logs `INSERT`, `UPDATE`, and `DELETE` operations.
  - Captures `old_values`, `new_values`, and `changed_by` (supports application user context).
- **Risk View**: `vw_portfolio_risk_summary` provides an aggregated view of the portfolio risk distribution.
