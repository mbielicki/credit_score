from __future__ import annotations
from sqlmodel import SQLModel, Field, Column, text
import sqlalchemy.dialects.postgresql as pg
from pydantic import field_validator, Field as PydanticField
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum

class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"

# --- Tables ---

class RatingModelParams(SQLModel, table=True):
    __tablename__ = "rating_model_params"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    model_name: str = Field(max_length=100)
    version: str = Field(max_length=20)
    coefficients: Dict[str, Any] = Field(sa_column=Column(pg.JSONB, nullable=False))
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )

class Company(SQLModel, table=True):
    __tablename__ = "companies"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    nip: str = Field(unique=True, index=True, regex=r"^[0-9]{10}$")
    krs: Optional[str] = Field(default=None, unique=True, regex=r"^[0-9]{10}$")
    name: str = Field(max_length=255)
    industry: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )

class FinancialStatement(SQLModel, table=True):
    __tablename__ = "financial_statements"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    company_id: UUID = Field(foreign_key="companies.id")
    fiscal_year: int = Field(ge=1900, le=2100)
    total_assets: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    equity: float
    current_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    operating_profit: float
    net_profit: float
    depreciation: float = Field(default=0.0, ge=0)
    gross_profit: float
    sales_revenue: float = Field(ge=0)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )

class RatingBand(SQLModel, table=True):
    __tablename__ = "rating_bands"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    rating_model_id: UUID = Field(foreign_key="rating_model_params.id")
    min_z_score: float
    rating_class: str = Field(max_length=3)
    pd_percentage: float
    risk_profile: Optional[str] = Field(default=None, max_length=50)

class CreditDecision(SQLModel, table=True):
    __tablename__ = "credit_decisions"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    statement_id: UUID = Field(foreign_key="financial_statements.id")
    rating_model_id: UUID = Field(foreign_key="rating_model_params.id")
    requested_amount: float = Field(ge=0)
    z_score: Optional[float] = None
    pd_percentage: Optional[float] = None
    rating_class: Optional[str] = Field(default=None, max_length=3)
    
    decision_status: DecisionStatus = Field(
        sa_column=Column(pg.ENUM(DecisionStatus, name="decision_status_enum"), nullable=False)
    )
    decision_reason: Optional[str] = None
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )

# --- API Schemas ---

class EnrichedCreditDecision(SQLModel):
    id: UUID
    statement_id: UUID
    rating_model_id: UUID
    requested_amount: float
    z_score: Optional[float] = None
    pd_percentage: Optional[float] = None
    rating_class: Optional[str] = None
    decision_status: DecisionStatus
    decision_reason: Optional[str] = None
    created_at: datetime
    model_name: str
    version: str
    risk_profile: Optional[str] = None

class CompanyBase(SQLModel):
    nip: str = PydanticField(..., pattern=r"^[0-9]{10}$")
    krs: Optional[str] = PydanticField(None, pattern=r"^[0-9]{10}$")
    name: str
    industry: Optional[str] = None

    @field_validator("nip")
    @classmethod
    def validate_nip_checksum(cls, v: str) -> str:
        if len(v) != 10:
            return v  # Let Field(regex=...) handle length validation
        weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
        digits = [int(d) for d in v]
        checksum = sum(w * d for w, d in zip(weights, digits[:9])) % 11
        if checksum != digits[9]:
            raise ValueError("Invalid NIP checksum")
        return v

class CompanyCreate(CompanyBase):
    pass

class FinancialStatementBase(SQLModel):
    fiscal_year: int = Field(..., ge=1900, le=2100)
    total_assets: float = Field(..., ge=0)
    total_liabilities: float = Field(..., ge=0)
    equity: float
    current_assets: float = Field(..., ge=0)
    current_liabilities: float = Field(..., ge=0)
    operating_profit: float
    net_profit: float
    depreciation: float = Field(0.0, ge=0)
    gross_profit: float
    sales_revenue: float = Field(..., ge=0)

class FinancialStatementCreate(FinancialStatementBase):
    company_nip: str = PydanticField(..., pattern=r"^[0-9]{10}$")
    requested_amount: float = Field(0, ge=0)

class PortfolioSummary(SQLModel):
    rating_class: str
    count: int
    percentage: float
