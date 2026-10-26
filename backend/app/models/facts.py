from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Natureza da despesa: direct, shared, excluded ou pending_classification.


class Expense(Base):
    """Fato de despesa. Valores em BRL, NUMERIC(14,2)."""

    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_unit_process", "unit_id", "process_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    competence_date: Mapped[date] = mapped_column(Date, index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("processes.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    nature: Mapped[str] = mapped_column(String(32))
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Activity(Base):
    """Fato operacional (volume de um direcionador)."""

    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_unit_process", "unit_id", "process_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    unit_of_measure: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Budget(Base):
    """Orçamento por período e dimensão, na mesma convenção do realizado."""

    __tablename__ = "budgets"
    __table_args__ = (Index("ix_budgets_unit_process", "unit_id", "process_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
