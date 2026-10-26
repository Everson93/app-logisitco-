"""Execução do cálculo sobre o banco (RF-007 a RF-009).

Recalcular cria uma nova execução e marca as anteriores como substituídas (Apêndice A).
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Account,
    Activity,
    AllocationResult,
    AllocationRule,
    Budget,
    CalculationIssue,
    CalculationRun,
    CostResult,
    Driver,
    Expense,
    Process,
    Unit,
)
from app.services import audit
from app.services.calculation_engine import (
    ActivityFact,
    ExpenseFact,
    RuleSpec,
    calculate_month,
    rule_version,
)
from app.services.calculations import round_money

MAX_MONTHS = 24


def month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def months_between(start: date, end: date) -> list[date]:
    months, current = [], start
    while current <= end:
        months.append(current)
        current = month_end(current) + timedelta(days=1)
    return months


def check_period(period_start: date, period_end: date) -> list[date]:
    details = []
    if period_start.day != 1:
        details.append({"field": "period_start", "code": "MUST_BE_FIRST_DAY_OF_MONTH"})
    if period_end != month_end(period_end):
        details.append({"field": "period_end", "code": "MUST_BE_LAST_DAY_OF_MONTH"})
    if period_end < period_start:
        details.append({"field": "period_end", "code": "BEFORE_PERIOD_START"})
    if details:
        raise AppError(
            422,
            "INVALID_PERIOD",
            "O período deve cobrir meses inteiros de competência (do dia 1 ao último dia).",
            details,
        )
    months = months_between(period_start, period_end)
    if len(months) > MAX_MONTHS:
        raise AppError(422, "INVALID_PERIOD", f"O período pode ter no máximo {MAX_MONTHS} meses.")
    return months


def _ids_by_code(db: Session, model, codes: list[str] | None) -> frozenset[int] | None:
    if not codes:
        return None
    return frozenset(db.scalars(select(model.id).where(model.code.in_(codes))))


def load_rules(db: Session) -> tuple[list[RuleSpec], list[dict[str, Any]]]:
    rules = db.scalars(select(AllocationRule).where(AllocationRule.active.is_(True))).all()
    specs, snapshot = [], []
    for rule in rules:
        scope = rule.scope or {}
        specs.append(
            RuleSpec(
                id=rule.id,
                driver_id=rule.driver_id,
                valid_from=rule.valid_from,
                valid_to=rule.valid_to,
                priority=rule.priority,
                source_unit_ids=_ids_by_code(db, Unit, scope.get("source_unit_codes")),
                source_account_ids=_ids_by_code(db, Account, scope.get("source_account_codes")),
                target_unit_ids=_ids_by_code(db, Unit, scope.get("target_unit_codes")),
                target_process_ids=_ids_by_code(db, Process, scope.get("target_process_codes")),
                source_process_ids=_ids_by_code(db, Process, scope.get("source_process_codes")),
            )
        )
        snapshot.append(
            {
                "id": rule.id,
                "driver_id": rule.driver_id,
                "valid_from": rule.valid_from.isoformat(),
                "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
                "priority": rule.priority,
                "rounding": rule.rounding,
                "scope": scope,
            }
        )
    return specs, snapshot


@dataclass
class PeriodInputs:
    """Entradas do motor para um período, já agrupadas por mês de competência."""

    months: list[date]
    rules: list[RuleSpec]
    rule_snapshot: list[dict[str, Any]]
    default_drivers: dict[int, tuple[int, str]]
    expenses: dict[date, list[ExpenseFact]]
    activities: dict[date, list[ActivityFact]]
    budgets: dict[date, dict]


def load_inputs(db: Session, period_start: date, period_end: date) -> PeriodInputs:
    months = check_period(period_start, period_end)
    rules, snapshot = load_rules(db)
    default_drivers = {
        process_id: (driver_id, uom)
        for process_id, driver_id, uom in db.execute(
            select(Process.id, Driver.id, Driver.unit_of_measure).join(
                Driver, Process.default_driver_id == Driver.id
            )
        )
    }

    expenses_by_month: dict[date, list[ExpenseFact]] = defaultdict(list)
    for e in db.scalars(
        select(Expense).where(Expense.competence_date.between(period_start, period_end))
    ):
        expenses_by_month[e.competence_date.replace(day=1)].append(
            ExpenseFact(
                e.id, e.competence_date, e.unit_id, e.process_id, e.account_id, e.amount, e.nature
            )
        )

    activities_by_month: dict[date, list[ActivityFact]] = defaultdict(list)
    for a in db.scalars(
        select(Activity).where(Activity.activity_date.between(period_start, period_end))
    ):
        activities_by_month[a.activity_date.replace(day=1)].append(
            ActivityFact(a.unit_id, a.process_id, a.driver_id, a.quantity)
        )

    budgets_by_month: dict[date, dict] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    for b in db.scalars(
        select(Budget).where(Budget.period_start.between(period_start, period_end))
    ):
        budgets_by_month[b.period_start.replace(day=1)][(b.unit_id, b.process_id)] += b.amount

    return PeriodInputs(
        months,
        rules,
        snapshot,
        default_drivers,
        expenses_by_month,
        activities_by_month,
        budgets_by_month,
    )


def run_calculation(
    db: Session, *, period_start: date, period_end: date, actor: str | None
) -> CalculationRun:
    inputs = load_inputs(db, period_start, period_end)
    months, rules, snapshot = inputs.months, inputs.rules, inputs.rule_snapshot

    run = CalculationRun(
        period_start=period_start,
        period_end=period_end,
        rule_version=rule_version(snapshot),
        status="completed",
        created_by=actor,
    )
    db.add(run)
    db.flush()

    totals = defaultdict(lambda: Decimal(0))
    issues_count = 0
    for month in months:
        result = calculate_month(
            month,
            inputs.expenses.get(month, []),
            inputs.activities.get(month, []),
            inputs.budgets.get(month, {}),
            rules,
            inputs.default_drivers,
        )
        db.add_all(
            CostResult(
                calculation_run_id=run.id,
                period_start=month,
                unit_id=r.unit_id,
                process_id=r.process_id,
                direct_cost=r.direct_cost,
                allocated_cost=r.allocated_cost,
                transferred_cost=r.transferred_cost,
                total_cost=r.total_cost,
                driver_id=r.driver_id,
                driver_quantity=r.driver_quantity,
                unit_of_measure=r.unit_of_measure,
                unit_cost=r.unit_cost,
                budget_amount=r.budget_amount,
                variance_amount=r.variance_amount,
                variance_percent=r.variance_percent,
                alerts=[str(a) for a in r.alerts],
            )
            for r in result.rows
        )
        db.add_all(
            AllocationResult(
                calculation_run_id=run.id,
                expense_id=a.expense_id,
                source_unit_id=a.source[0] if a.source else None,
                source_process_id=a.source[1] if a.source else None,
                rule_id=a.rule_id,
                target_unit_id=a.target[0],
                target_process_id=a.target[1],
                driver_quantity=a.driver_quantity,
                allocated_amount=a.amount,
            )
            for a in result.allocations
        )
        db.add_all(
            CalculationIssue(
                calculation_run_id=run.id,
                period_start=month,
                code=i.code.value,
                severity=i.severity,
                expense_id=i.expense_id,
                amount=i.amount,
                message=i.message,
            )
            for i in result.issues
        )
        for key, value in result.composition.items():
            totals[key] += value
        issues_count += len(result.issues)

    run.status = "completed_with_pending" if totals["pending"] > 0 else "completed"
    run.summary = {
        "months": len(months),
        "direct": str(round_money(totals["direct"])),
        "allocated": str(round_money(totals["allocated"])),
        "transferred": str(round_money(totals["transferred"])),
        "excluded": str(round_money(totals["excluded"])),
        "pending": str(round_money(totals["pending"])),
        "issues": issues_count,
        "rules": [r["id"] for r in snapshot],
    }

    # Execuções anteriores totalmente cobertas por esta continuam no histórico, mas deixam
    # de valer. Uma execução só parcialmente coberta segue vigente nos meses restantes:
    # em cada mês vale a execução mais recente que o cobre (ver current_run_by_month).
    db.execute(
        update(CalculationRun)
        .where(
            CalculationRun.id != run.id,
            CalculationRun.status != "superseded",
            and_(
                CalculationRun.period_start >= period_start,
                CalculationRun.period_end <= period_end,
            ),
        )
        .values(status="superseded")
    )
    audit.record(
        db,
        actor=actor,
        action="calculation.run",
        entity_type="calculation_run",
        entity_id=run.id,
        details={
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "rule_version": run.rule_version,
            "status": run.status,
        },
    )
    db.commit()
    return run


def get_run(db: Session, run_id: int) -> CalculationRun:
    run = db.get(CalculationRun, run_id)
    if run is None:
        raise AppError(404, "RUN_NOT_FOUND", "Execução de cálculo não encontrada.")
    return run


def list_runs(db: Session, *, page: int, page_size: int) -> tuple[list[CalculationRun], int]:
    total = db.scalar(select(func.count()).select_from(CalculationRun)) or 0
    items = db.scalars(
        select(CalculationRun)
        .order_by(CalculationRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def run_results(db: Session, run_id: int) -> list[CostResult]:
    get_run(db, run_id)
    return list(
        db.scalars(
            select(CostResult)
            .where(CostResult.calculation_run_id == run_id)
            .order_by(CostResult.period_start, CostResult.unit_id, CostResult.process_id)
        )
    )


def run_issues(db: Session, run_id: int) -> list[CalculationIssue]:
    get_run(db, run_id)
    return list(
        db.scalars(
            select(CalculationIssue)
            .where(CalculationIssue.calculation_run_id == run_id)
            .order_by(CalculationIssue.period_start, CalculationIssue.id)
        )
    )


def run_allocations(db: Session, run_id: int) -> list[AllocationResult]:
    get_run(db, run_id)
    return list(
        db.scalars(
            select(AllocationResult)
            .where(AllocationResult.calculation_run_id == run_id)
            .order_by(AllocationResult.id)
        )
    )


def current_run_by_month(db: Session, period_start: date, period_end: date) -> dict[date, int]:
    """Para cada mês do intervalo, a execução mais recente que o cobre."""
    runs = db.execute(
        select(CalculationRun.id, CalculationRun.period_start, CalculationRun.period_end)
        .where(
            CalculationRun.status != "superseded",
            CalculationRun.period_start <= period_end,
            CalculationRun.period_end >= period_start,
        )
        .order_by(CalculationRun.id)
    )
    current: dict[date, int] = {}
    first_month = period_start.replace(day=1)
    for run_id, start, end in runs:
        for month in months_between(max(start, first_month), min(end, month_end(period_end))):
            current[month] = run_id  # ordenado por id: o mais recente sobrescreve
    return current
