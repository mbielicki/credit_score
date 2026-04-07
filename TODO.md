# IRB Credit Rating Engine: Task Tracker

## 🟢 Active / Next Up
- [ ] **Infra & CI/CD ($0 Budget Stack)**:
    - [ ] **Infrastructure**: Setup Terraform for GCP (Cloud Run, Artifact Registry).
    - [ ] **Database**: Configure Neon/Supabase integration and migration runner.
    - [ ] **CI/CD**: implement GitHub Actions for automated testing and deployment to Cloud Run.

## 🟡 Backlog
- [ ] **Rating Edge Cases**: Add backend tests for division by zero or NULL values in financial statements.
- [ ] **Fix percentages**: Change percentage format in frontend dashboard.
- [ ] **Mock data**: The app is a demo, so generate mock data in all forms so that anyone can see how the app works without having to make up the numbers themselves.
- [ ] **Intuitive frontend**: Add some instructions and explanations in the UI about the z-score and how the system works.

## ✅ Completed
- [x] Implement Frontend (Dashboard, Company Analysis, New Rating forms).
- [x] Add automated E2E tests for Frontend (Playwright).
- [x] Refactor backend to SQLModel/SQLAlchemy 2.0.
- [x] Establish persistent task tracking (`TODO.md`).
