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
    coefficients JSONB NOT NULL, -- {w1: 9.478, ..., intercept: -2.478}
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

-- 5. Business Logic Function
CREATE OR REPLACE FUNCTION fn_generate_rating(p_stmt_id UUID, p_requested_amount DECIMAL DEFAULT 0)
RETURNS UUID AS $$
DECLARE
    v_total_assets DECIMAL; v_equity DECIMAL; v_current_assets DECIMAL; 
    v_current_liabilities DECIMAL; v_operating_profit DECIMAL; 
    v_net_profit DECIMAL; v_gross_profit DECIMAL; v_sales_revenue DECIMAL;
    
    v_rating_model_id UUID; v_coeffs JSONB; v_ratios JSONB;
    v_x1 DECIMAL; v_x2 DECIMAL; v_x3 DECIMAL; v_x4 DECIMAL; v_x5 DECIMAL;
    v_z DECIMAL; v_rating VARCHAR(3); v_pd DECIMAL; v_status decision_status_enum; v_reason TEXT;
    v_decision_id UUID;
    v_key TEXT; v_val TEXT; v_ratio_val DECIMAL;
BEGIN
    -- 1. Fetch active model parameters (latest version)
    SELECT id, coefficients INTO v_rating_model_id, v_coeffs 
    FROM rating_model_params 
    WHERE is_active = TRUE 
    ORDER BY version DESC LIMIT 1;

    IF v_rating_model_id IS NULL THEN
        RAISE EXCEPTION 'No active rating model found.';
    END IF;

    -- 2. Fetch financial data
    SELECT total_assets, equity, current_assets, current_liabilities,
           operating_profit, net_profit, gross_profit, sales_revenue
    INTO v_total_assets, v_equity, v_current_assets, v_current_liabilities,
         v_operating_profit, v_net_profit, v_gross_profit, v_sales_revenue
    FROM financial_statements WHERE id = p_stmt_id;

    IF v_total_assets IS NULL THEN
        RAISE EXCEPTION 'Financial statement with ID % not found.', p_stmt_id;
    END IF;

    -- 3. Calculate Ratios with edge case handling
    v_x1 := COALESCE(v_operating_profit / NULLIF(v_total_assets, 0), 0);
    v_x2 := COALESCE(v_equity / NULLIF(v_total_assets, 0), 0);
    v_x3 := COALESCE(v_net_profit / NULLIF(v_total_assets, 0), 0);
    v_x4 := COALESCE(v_gross_profit / NULLIF(v_sales_revenue, 0), 0);
    
    IF v_current_liabilities = 0 THEN
        IF v_current_assets > 0 THEN v_x5 := 99.99; ELSE v_x5 := 0; END IF;
    ELSE
        v_x5 := v_current_assets / v_current_liabilities;
    END IF;

    -- Store ratios in JSONB for dynamic calculation
    v_ratios := jsonb_build_object('w1', v_x1, 'w2', v_x2, 'w3', v_x3, 'w4', v_x4, 'w5', v_x5);

    -- 4. Robust Dynamic Z-score calculation
    IF NOT (v_coeffs ? 'intercept') THEN
        RAISE EXCEPTION 'Model configuration error: Missing intercept coefficient.';
    END IF;
    
    v_z := (v_coeffs->>'intercept')::DECIMAL;

    FOR v_key, v_val IN SELECT * FROM jsonb_each_text(v_coeffs) LOOP
        IF v_key = 'intercept' THEN CONTINUE; END IF;
        
        v_ratio_val := (v_ratios->>v_key)::DECIMAL;
        IF v_ratio_val IS NULL THEN
            RAISE EXCEPTION 'Model requires coefficient % but corresponding ratio is not defined or calculated.', v_key;
        END IF;

        IF v_val IS NULL THEN
            RAISE EXCEPTION 'NULL coefficient detected for weight %.', v_key;
        END IF;

        v_z := v_z + (v_val::DECIMAL * v_ratio_val);
    END LOOP;

    -- 5. Rating Mapping (De-hardcoded from rating_bands)
    -- Using >= for inclusive lower bounds
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

    -- 6. Adjudication (De-hardcoded from adjudication_rules)
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

    -- 7. Insert & Return
    INSERT INTO credit_decisions (statement_id, rating_model_id, requested_amount, z_score, pd_percentage, rating_class, decision_status, decision_reason)
    VALUES (p_stmt_id, v_rating_model_id, p_requested_amount, v_z, v_pd, v_rating, v_status, v_reason)
    RETURNING id INTO v_decision_id;

    RETURN v_decision_id;
END;
$$ LANGUAGE plpgsql;

-- 6. Audit Trigger Function
CREATE OR REPLACE FUNCTION fn_audit_generic() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(100);
BEGIN
    -- Attempt to get application-level user, fallback to DB user
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

-- 7. Apply Triggers
CREATE TRIGGER trg_audit_credit_decisions AFTER INSERT OR UPDATE OR DELETE ON credit_decisions FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();
CREATE TRIGGER trg_audit_companies AFTER INSERT OR UPDATE OR DELETE ON companies FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();

-- 8. Seed Data
DO $$
DECLARE
    v_mid UUID;
BEGIN
    -- Seed Model
    INSERT INTO rating_model_params (model_name, version, coefficients)
    VALUES ('Maczynska_Zawadzki', '2006_Model_1', '{"w1": 9.478, "w2": 3.613, "w3": 3.256, "w4": 0.454, "w5": 0.802, "intercept": -2.478}'::jsonb)
    RETURNING id INTO v_mid;

    -- Seed Rating Bands
    INSERT INTO rating_bands (rating_model_id, min_z_score, rating_class, pd_percentage, risk_profile) VALUES
    (v_mid, 3.0,  'AAA', 0.0001, 'Exceptional'),
    (v_mid, 2.5,  'AA',  0.0002, 'Very Strong'),
    (v_mid, 2.0,  'A',   0.0005, 'Strong'),
    (v_mid, 1.0,  'BBB', 0.0020, 'Good'),
    (v_mid, 0.5,  'BB',  0.0100, 'Speculative'),
    (v_mid, 0.0,  'B',   0.0500, 'Highly Speculative'),
    (v_mid, -1.0, 'CCC', 0.2000, 'Substantial Risk'),
    (v_mid, -999, 'D',   0.5000, 'Default');

    -- Seed Adjudication Rules
    INSERT INTO adjudication_rules (rating_model_id, rating_class, max_amount, decision_status) VALUES
    (v_mid, 'AAA', 1000000, 'APPROVED'),
    (v_mid, 'AA',  1000000, 'APPROVED'),
    (v_mid, 'A',   1000000, 'APPROVED'),
    (v_mid, 'BBB', 1000000, 'APPROVED'),
    (v_mid, 'CCC', NULL,    'REJECTED'),
    (v_mid, 'D',   NULL,    'REJECTED');
END $$;

-- 9. Views
CREATE OR REPLACE VIEW vw_portfolio_risk_summary AS
SELECT rating_class, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) as percentage
FROM credit_decisions GROUP BY rating_class;
