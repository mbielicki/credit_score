from __future__ import annotations
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import List, Any, cast
from sqlmodel import Session, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .database import get_session
from .models import (
    Company, CompanyCreate, FinancialStatementCreate, FinancialStatement,
    CreditDecision, PortfolioSummary, RatingModelParams, RatingBand, EnrichedCreditDecision
)

app = FastAPI(title="IRB Credit Rating Engine API")

@app.get("/")
async def root():
    return {
        "message": "IRB Credit Rating Engine API is active", 
        "version": "0.1.2",
        "orm": "SQLModel"
    }

@app.get("/health")
async def health_check(session: Session = Depends(get_session)) -> dict[str, str]:
    session.connection().execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}

@app.post("/companies", response_model=Company)
async def create_company(
    company_in: CompanyCreate, 
    request: Request,
    session: Session = Depends(get_session)
):
    user_id = request.headers.get("X-User-ID", "anonymous_analyst")
    session.connection().execute(text("SELECT set_config('app.current_user', :u, true)"), {"u": user_id})
    
    insert_stmt = pg_insert(Company).values(**company_in.model_dump())
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[Company.nip],
        set_={
            "krs": insert_stmt.excluded.krs,
            "name": insert_stmt.excluded.name,
            "industry": insert_stmt.excluded.industry,
        }
    )
    
    session.connection().execute(upsert_stmt)
    res = session.exec(select(Company).where(Company.nip == company_in.nip)).first()
    if not res:
        raise HTTPException(status_code=500, detail="Failed to create or update company.")
    session.commit()
    session.refresh(res)
    return res

@app.post("/statements", response_model=EnrichedCreditDecision)
async def submit_statement(
    stmt_in: FinancialStatementCreate,
    request: Request,
    session: Session = Depends(get_session)
):
    user_id = request.headers.get("X-User-ID", "anonymous_analyst")
    session.connection().execute(text("SELECT set_config('app.current_user', :u, true)"), {"u": user_id})

    # Find company ID
    company = session.exec(select(Company).where(Company.nip == stmt_in.company_nip)).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    try:
        data = stmt_in.model_dump(exclude={"company_nip", "requested_amount"})
        data["company_id"] = company.id
        
        insert_stmt = pg_insert(FinancialStatement).values(**data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["company_id", "fiscal_year"],
            set_={
                "total_assets": insert_stmt.excluded.total_assets,
                "total_liabilities": insert_stmt.excluded.total_liabilities,
                "equity": insert_stmt.excluded.equity,
                "current_assets": insert_stmt.excluded.current_assets,
                "current_liabilities": insert_stmt.excluded.current_liabilities,
                "operating_profit": insert_stmt.excluded.operating_profit,
                "net_profit": insert_stmt.excluded.net_profit,
                "depreciation": insert_stmt.excluded.depreciation,
                "gross_profit": insert_stmt.excluded.gross_profit,
                "sales_revenue": insert_stmt.excluded.sales_revenue,
            }
        )
        session.connection().execute(upsert_stmt)
        
        # Fetch back to get ID (satisfies mypy)
        db_stmt = session.exec(
            select(FinancialStatement)
            .where(FinancialStatement.company_id == company.id)
            .where(FinancialStatement.fiscal_year == stmt_in.fiscal_year)
        ).first()
        
        if not db_stmt or not db_stmt.id:
            raise HTTPException(status_code=500, detail="Failed to find statement after upsert.")
        
        stmt_id = db_stmt.id
        
        # Call rating function
        decision_id = session.connection().execute(
            text("SELECT fn_generate_rating(:stmt_id, :amount) as decision_id"),
            {"stmt_id": stmt_id, "amount": stmt_in.requested_amount}
        ).scalar()
        
        if not decision_id:
            raise HTTPException(status_code=500, detail="Failed to generate rating.")

        session.commit()

        stmt = (
            select(
                CreditDecision,
                RatingModelParams.model_name,
                RatingModelParams.version,
                RatingBand.risk_profile
            )
            .join(RatingModelParams, cast(Any, CreditDecision.rating_model_id == RatingModelParams.id))
            .outerjoin(
                RatingBand,
                cast(Any, (CreditDecision.rating_model_id == RatingBand.rating_model_id)
                & (CreditDecision.rating_class == RatingBand.rating_class))
            )
            .where(CreditDecision.id == decision_id)
        )
        result = session.exec(stmt).first()

        if not result:
            raise HTTPException(status_code=404, detail="Decision not found after generation.")
            
        cd, rmp_name, rmp_version, rb_profile = result
        return EnrichedCreditDecision(
            **cd.model_dump(),
            model_name=rmp_name,
            version=rmp_version,
            risk_profile=rb_profile
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/companies/{nip}/history", response_model=List[EnrichedCreditDecision])
async def get_company_history(nip: str, session: Session = Depends(get_session)):
    stmt = (
        select(
            CreditDecision,
            RatingModelParams.model_name,
            RatingModelParams.version,
            RatingBand.risk_profile
        )
        .join(FinancialStatement, cast(Any, CreditDecision.statement_id == FinancialStatement.id))
        .join(Company, cast(Any, FinancialStatement.company_id == Company.id))
        .join(RatingModelParams, cast(Any, CreditDecision.rating_model_id == RatingModelParams.id))
        .outerjoin(
            RatingBand,
            cast(Any, (CreditDecision.rating_model_id == RatingBand.rating_model_id)
            & (CreditDecision.rating_class == RatingBand.rating_class))
        )
        .where(Company.nip == nip)
        .order_by(text("credit_decisions.created_at DESC"))
    )

    results = session.exec(stmt).all()
    return [
        EnrichedCreditDecision(
            **cd.model_dump(),
            model_name=rmp_name,
            version=rmp_version,
            risk_profile=rb_profile
        )
        for cd, rmp_name, rmp_version, rb_profile in results
    ]

@app.get("/portfolio/summary", response_model=List[PortfolioSummary])
async def get_portfolio_summary(session: Session = Depends(get_session)):
    results = session.connection().execute(text("SELECT * FROM vw_portfolio_risk_summary")).mappings().all()
    return [PortfolioSummary.model_validate(r) for r in results]
