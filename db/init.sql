-- IRB Credit Engine - Database DDL
-- Target: PostgreSQL 15+

-- 1. Extensions & Types
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'decision_status_enum') THEN
        CREATE TYPE decision_status_enum AS ENUM ('APPROVED', 'REJECTED', 'MANUAL_REVIEW');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_action_enum') THEN
        CREATE TYPE audit_action_enum AS ENUM ('INSERT', 'UPDATE', 'DELETE');
    END IF;
END $$;

-- 2. Model Configuration Tables
CREATE TABLE IF NOT EXISTS rating_model_params (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    coefficients JSONB NOT NULL, -- {intercept: -1.498, ratio_name: weight, ...}
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, version)
);

CREATE TABLE IF NOT EXISTS rating_bands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rating_model_id UUID NOT NULL REFERENCES rating_model_params(id) ON DELETE CASCADE,
    min_z_score DECIMAL(19,6) NOT NULL,
    rating_class VARCHAR(3) NOT NULL,
    pd_percentage DECIMAL(10,4) NOT NULL,
    risk_profile VARCHAR(50),
    UNIQUE(rating_model_id, min_z_score)
);

CREATE TABLE IF NOT EXISTS adjudication_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rating_model_id UUID NOT NULL REFERENCES rating_model_params(id) ON DELETE CASCADE,
    rating_class VARCHAR(3) NOT NULL,
    max_amount DECIMAL(19,4), -- NULL means any amount
    decision_status decision_status_enum NOT NULL,
    priority INT DEFAULT 0,
    UNIQUE(rating_model_id, rating_class, max_amount)
);

-- 3. Core Entities
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nip VARCHAR(10) UNIQUE NOT NULL CHECK (nip ~ '^[0-9]{10}$'),
    krs VARCHAR(10) UNIQUE CHECK (krs ~ '^[0-9]{10}$'),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS financial_statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INT NOT NULL CHECK (fiscal_year BETWEEN 1900 AND 2100),
    total_assets DECIMAL(19,4) NOT NULL CHECK (total_assets >= 0),
    total_liabilities DECIMAL(19,4) NOT NULL CHECK (total_liabilities >= 0),
    equity DECIMAL(19,4) NOT NULL,
    current_assets DECIMAL(19,4) NOT NULL CHECK (current_assets >= 0),
    current_liabilities DECIMAL(19,4) NOT NULL CHECK (current_liabilities >= 0),
    operating_profit DECIMAL(19,4) NOT NULL,
    net_profit DECIMAL(19,4) NOT NULL,
    depreciation DECIMAL(19,4) NOT NULL DEFAULT 0,
    gross_profit DECIMAL(19,4) NOT NULL,
    sales_revenue DECIMAL(19,4) NOT NULL CHECK (sales_revenue >= 0),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, fiscal_year)
);

CREATE TABLE IF NOT EXISTS credit_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id UUID NOT NULL REFERENCES financial_statements(id) ON DELETE RESTRICT,
    rating_model_id UUID NOT NULL REFERENCES rating_model_params(id),
    requested_amount DECIMAL(19,4) NOT NULL CHECK (requested_amount >= 0),
    z_score DECIMAL(19,6),
    pd_percentage DECIMAL(10,4),
    rating_class VARCHAR(3),
    decision_status decision_status_enum NOT NULL,
    decision_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Audit System
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    action audit_action_enum NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100) DEFAULT CURRENT_USER,
    changed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Scalability Indexes
CREATE INDEX IF NOT EXISTS idx_financial_statements_company_id ON financial_statements(company_id);
CREATE INDEX IF NOT EXISTS idx_credit_decisions_statement_id ON credit_decisions(statement_id);
CREATE INDEX IF NOT EXISTS idx_credit_decisions_rating_model_id ON credit_decisions(rating_model_id);
CREATE INDEX IF NOT EXISTS idx_rating_bands_rating_model_id ON rating_bands(rating_model_id);
CREATE INDEX IF NOT EXISTS idx_adjudication_rules_rating_model_id ON adjudication_rules(rating_model_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_record_id ON audit_logs(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table_name ON audit_logs(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_logs_new_values ON audit_logs USING GIN (new_values);

-- 6. Calculation Layer (Descriptive Ratios)
CREATE OR REPLACE VIEW vw_financial_ratios AS
SELECT 
    id AS statement_id,
    company_id,
    -- Mączyńska Model G Ratios (Descriptive)
    COALESCE(operating_profit / NULLIF(total_assets, 0), 0) AS operating_profit_to_total_assets,
    COALESCE(equity / NULLIF(total_assets, 0), 0) AS equity_to_total_assets,
    COALESCE((net_profit + depreciation) / NULLIF(total_liabilities, 0), 0) AS net_profit_plus_depreciation_to_total_liabilities,
    COALESCE(current_assets / NULLIF(current_liabilities, 0), 0) AS current_assets_to_current_liabilities,
    -- Future Altman Ratios (Example)
    COALESCE((current_assets - current_liabilities) / NULLIF(total_assets, 0), 0) AS working_capital_to_total_assets,
    COALESCE(sales_revenue / NULLIF(total_assets, 0), 0) AS asset_turnover
FROM financial_statements;

-- 7. Dynamic Model-Agnostic Rating Function
CREATE OR REPLACE FUNCTION fn_generate_rating(p_stmt_id UUID, p_requested_amount DECIMAL DEFAULT 0)
RETURNS UUID AS $$
DECLARE
    v_rating_model_id UUID; 
    v_coeffs JSONB; 
    v_ratios JSONB;
    v_z DECIMAL; 
    v_rating VARCHAR(3); 
    v_pd DECIMAL; 
    v_status decision_status_enum; 
    v_reason TEXT;
    v_decision_id UUID;
    v_key TEXT; 
    v_weight TEXT; 
    v_ratio_val DECIMAL;
BEGIN
    -- 1. Fetch active model parameters
    SELECT id, coefficients INTO v_rating_model_id, v_coeffs 
    FROM rating_model_params 
    WHERE is_active = TRUE 
    ORDER BY version DESC LIMIT 1;

    IF v_rating_model_id IS NULL THEN
        RAISE EXCEPTION 'No active rating model found.';
    END IF;

    -- 2. Fetch all calculated ratios for this statement from the View
    SELECT to_jsonb(r) INTO v_ratios
    FROM vw_financial_ratios r
    WHERE r.statement_id = p_stmt_id;

    IF v_ratios IS NULL THEN
        RAISE EXCEPTION 'Financial statement with ID % not found.', p_stmt_id;
    END IF;

    -- 3. Dynamic Z-score calculation
    IF NOT (v_coeffs ? 'intercept') THEN
        RAISE EXCEPTION 'Model configuration error: Missing intercept coefficient.';
    END IF;
    
    v_z := (v_coeffs->>'intercept')::DECIMAL;

    FOR v_key, v_weight IN SELECT * FROM jsonb_each_text(v_coeffs) LOOP
        IF v_key = 'intercept' THEN CONTINUE; END IF;
        
        -- Look up the ratio value by its descriptive key name
        v_ratio_val := (v_ratios->>v_key)::DECIMAL;
        
        IF v_ratio_val IS NULL THEN
            RAISE EXCEPTION 'Model requires ratio "%" but it is not defined in vw_financial_ratios.', v_key;
        END IF;

        v_z := v_z + (v_weight::DECIMAL * v_ratio_val);
    END LOOP;

    -- 4. Rating Mapping
    SELECT rating_class, pd_percentage INTO v_rating, v_pd
    FROM rating_bands
    WHERE rating_model_id = v_rating_model_id AND v_z >= min_z_score
    ORDER BY min_z_score DESC LIMIT 1;

    IF v_rating IS NULL THEN
        SELECT rating_class, pd_percentage INTO v_rating, v_pd
        FROM rating_bands
        WHERE rating_model_id = v_rating_model_id
        ORDER BY min_z_score ASC LIMIT 1;
    END IF;

    -- 5. Adjudication
    SELECT decision_status INTO v_status
    FROM adjudication_rules
    WHERE rating_model_id = v_rating_model_id 
      AND rating_class = v_rating
      AND (max_amount IS NULL OR p_requested_amount <= max_amount)
    ORDER BY max_amount ASC NULLS LAST, priority DESC
    LIMIT 1;

    IF v_status IS NULL THEN
        v_status := 'MANUAL_REVIEW';
        v_reason := 'No matching adjudication rule found for rating ' || v_rating || '.';
    ELSE
        v_reason := 'Automated decision based on rating ' || v_rating || '.';
    END IF;

    -- 6. Insert & Return
    INSERT INTO credit_decisions (statement_id, rating_model_id, requested_amount, z_score, pd_percentage, rating_class, decision_status, decision_reason)
    VALUES (p_stmt_id, v_rating_model_id, p_requested_amount, v_z, v_pd, v_rating, v_status, v_reason)
    RETURNING id INTO v_decision_id;

    RETURN v_decision_id;
END;
$$ LANGUAGE plpgsql;

-- 8. Audit Trigger Function
CREATE OR REPLACE FUNCTION fn_audit_generic() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(100);
BEGIN
    v_user := COALESCE(current_setting('app.current_user', true), CURRENT_USER);

    IF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_logs (table_name, record_id, action, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', row_to_json(NEW), v_user);
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_logs (table_name, record_id, action, old_values, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW), v_user);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_logs (table_name, record_id, action, old_values, changed_by)
        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', row_to_json(OLD), v_user);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 9. Apply Triggers
CREATE TRIGGER trg_audit_credit_decisions AFTER INSERT OR UPDATE OR DELETE ON credit_decisions FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();
CREATE TRIGGER trg_audit_companies AFTER INSERT OR UPDATE OR DELETE ON companies FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();

-- 10. Seed Data
DO $$
DECLARE
    v_mid UUID;
BEGIN
    -- Seed Model G (Mączyńska & Zawadzki 2006)
    INSERT INTO rating_model_params (model_name, version, coefficients)
    VALUES ('Maczynska_Zawadzki_Model_G', '2006_G', '{
        "intercept": -1.498,
        "operating_profit_to_total_assets": 9.498,
        "equity_to_total_assets": 3.566,
        "net_profit_plus_depreciation_to_total_liabilities": 2.903,
        "current_assets_to_current_liabilities": 0.452
    }'::jsonb)
    ON CONFLICT (model_name, version) DO UPDATE SET is_active = TRUE
    RETURNING id INTO v_mid;

    -- If v_mid is NULL (because of a conflict where we didn't update or RETURNING didn't fire as expected)
    -- let's fetch it.
    IF v_mid IS NULL THEN
        SELECT id INTO v_mid FROM rating_model_params WHERE model_name = 'Maczynska_Zawadzki_Model_G' AND version = '2006_G';
    END IF;

    -- Seed Rating Bands
    INSERT INTO rating_bands (rating_model_id, min_z_score, rating_class, pd_percentage, risk_profile) VALUES
    (v_mid, 3.0,  'AAA', 0.0001, 'Exceptional'),
    (v_mid, 2.5,  'AA',  0.0002, 'Very Strong'),
    (v_mid, 2.0,  'A',   0.0005, 'Strong'),
    (v_mid, 1.0,  'BBB', 0.0020, 'Good'),
    (v_mid, 0.5,  'BB',  0.0100, 'Speculative'),
    (v_mid, 0.0,  'B',   0.0500, 'Highly Speculative'),
    (v_mid, -1.0, 'CCC', 0.2000, 'Substantial Risk'),
    (v_mid, -999, 'D',   0.5000, 'Default')
    ON CONFLICT (rating_model_id, min_z_score) DO NOTHING;

    -- Seed Adjudication Rules
    INSERT INTO adjudication_rules (rating_model_id, rating_class, max_amount, decision_status) VALUES
    (v_mid, 'AAA', 1000000, 'APPROVED'),
    (v_mid, 'AA',  1000000, 'APPROVED'),
    (v_mid, 'A',   1000000, 'APPROVED'),
    (v_mid, 'BBB', 1000000, 'APPROVED'),
    (v_mid, 'CCC', NULL,    'REJECTED'),
    (v_mid, 'D',   NULL,    'REJECTED')
    ON CONFLICT (rating_model_id, rating_class, max_amount) DO NOTHING;
END $$;

-- 11. Views
CREATE OR REPLACE VIEW vw_portfolio_risk_summary AS
SELECT rating_class, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) as percentage
FROM credit_decisions GROUP BY rating_class;
