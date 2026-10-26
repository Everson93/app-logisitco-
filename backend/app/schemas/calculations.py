from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleScope(BaseModel):
    """Filtros por código; lista vazia ou ausente significa "qualquer"."""

    source_unit_codes: list[str] = Field(default_factory=list)
    source_account_codes: list[str] = Field(default_factory=list)
    target_unit_codes: list[str] = Field(default_factory=list)
    target_process_codes: list[str] = Field(default_factory=list)

    def compact(self) -> dict[str, list[str]]:
        return {k: v for k, v in self.model_dump().items() if v}


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    driver_code: str
    valid_from: date
    valid_to: date | None = None
    scope: RuleScope = Field(default_factory=RuleScope)
    priority: int = Field(default=100, ge=1, le=10_000)
    active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    driver_code: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    scope: RuleScope | None = None
    priority: int | None = Field(default=None, ge=1, le=10_000)
    active: bool | None = None


class RuleOut(BaseModel):
    id: int
    name: str
    driver_code: str
    valid_from: date
    valid_to: date | None
    scope: dict[str, list[str]]
    priority: int
    rounding: str
    active: bool
    conflicts_with: list[int] = Field(
        default_factory=list,
        description="Regras ativas de mesma prioridade que podem cobrir as mesmas despesas.",
    )


class RunIn(BaseModel):
    period_start: date = Field(examples=["2026-09-01"])
    period_end: date = Field(examples=["2026-09-30"])


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_start: date
    period_end: date
    rule_version: str
    status: str
    created_by: str | None
    summary: dict[str, Any] | None
    created_at: datetime


class RunPage(BaseModel):
    items: list[RunOut]
    page: int
    page_size: int
    total: int


class CostResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    unit_id: int
    process_id: int | None
    direct_cost: Decimal
    allocated_cost: Decimal
    total_cost: Decimal
    driver_id: int | None
    driver_quantity: Decimal | None
    unit_of_measure: str | None
    unit_cost: Decimal | None
    budget_amount: Decimal | None
    variance_amount: Decimal | None
    variance_percent: Decimal | None
    alerts: list[str]


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_id: int
    rule_id: int
    target_unit_id: int
    target_process_id: int
    driver_quantity: Decimal
    allocated_amount: Decimal


class CalculationIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    code: str
    severity: str
    expense_id: int | None
    amount: Decimal | None
    message: str
