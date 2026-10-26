from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AllocationRule(Base):
    """Regra explícita para distribuir custos compartilhados (seção 5.3).

    `scope` define quais despesas a regra cobre e quais destinos são elegíveis:
    {"source_unit_codes": [...], "source_account_codes": [...],
     "target_unit_codes": [...], "target_process_codes": [...]}.
    Lista vazia ou ausente significa "qualquer".

    Com `source_process_codes`, a regra é de cascata: em vez de despesas compartilhadas,
    repassa o custo total desses processos (de apoio) aos processos de destino.
    """

    __tablename__ = "allocation_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, server_default="100")
    rounding: Mapped[str] = mapped_column(String(40), server_default="largest_remainder")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CalculationRun(Base):
    """Uma execução do motor; recalcular cria outra execução e preserva o histórico."""

    __tablename__ = "calculation_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    rule_version: Mapped[str] = mapped_column(String(80))
    # completed, completed_with_pending ou superseded (substituída por execução mais nova)
    status: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CostResult(Base):
    """Resultado agregado por mês, unidade e processo dentro de uma execução."""

    __tablename__ = "cost_results"
    __table_args__ = (Index("ix_cost_results_run_period", "calculation_run_id", "period_start"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calculation_run_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="CASCADE")
    )
    period_start: Mapped[date] = mapped_column(Date)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("processes.id"))
    direct_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    allocated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Rateio em cascata: positivo no destino, negativo no processo de apoio que repassou.
    transferred_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default="0")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    driver_quantity: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    unit_of_measure: Mapped[str | None] = mapped_column(String(40))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    variance_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    alerts: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")


class AllocationResult(Base):
    """Detalhe do rateio: de qual despesa (ou, na cascata, de qual processo de apoio), por qual
    regra, para qual destino."""

    __tablename__ = "allocation_results"
    __table_args__ = (
        CheckConstraint(
            "(expense_id IS NOT NULL) <> (source_process_id IS NOT NULL)",
            name="ck_allocation_results_origin",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calculation_run_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="CASCADE"), index=True
    )
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), index=True)
    source_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    source_process_id: Mapped[int | None] = mapped_column(ForeignKey("processes.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("allocation_rules.id"))
    target_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    target_process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    driver_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class CalculationIssue(Base):
    """Pendências e alertas de uma execução (ex.: custo compartilhado sem regra)."""

    __tablename__ = "calculation_issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calculation_run_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    code: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    message: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    """Ações críticas (seção 13). Guarda IDs e contagens, nunca o conteúdo dos arquivos."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
