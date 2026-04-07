# IRB Credit Rating Engine: Task Tracker

## 🟢 Active / Next Up
- [ ] **Implement Frontend**:
    - [ ] Review existing `frontend/` logic and Streamlit patterns.
    - [ ] Implement Analyst Dashboard with Company search and historical trends.
    - [ ] Create submission forms for Financial Statements with real-time validation.
    - [ ] Integrate `EnrichedCreditDecision` views and Portfolio risk charts.
- [ ] **Infra & CI/CD ($0 Budget Stack)**:
    - [ ] **Infrastructure**: Setup Terraform for GCP (Cloud Run, Artifact Registry).
    - [ ] **Database**: Configure Neon/Supabase integration and migration runner.
    - [ ] **CI/CD**: implement GitHub Actions for automated testing and deployment to Cloud Run.

## 🟡 Backlog
- [ ] **Rating Edge Cases**: Add backend tests for division by zero or NULL values in financial statements.
- [ ] **Bulk Import**: Support CSV/Excel uploads for financial statements.
- [ ] **Security**: Implement analyst authentication and role-based access.

## ✅ Completed
- [x] Refactor backend to SQLModel/SQLAlchemy 2.0.
- [x] Implement API Integration Testing suite.
- [x] Add automated database initialization for tests.
- [x] Streamline documentation for agentic efficiency.
- [x] Establish persistent task tracking (`TODO.md`).
- [x] Anonymize company data (remove real NIPs/KRS/Names).
