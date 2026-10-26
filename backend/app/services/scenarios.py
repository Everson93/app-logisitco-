"""Simulação de cenários "e se" (Fase 4).

Recalcula um período com as mesmas regras do motor, mas com entradas alteradas: volume
por processo, parcela variável do custo direto e, opcionalmente, outro direcionador para
os custos compartilhados. Nada é gravado: a simulação não cria execução de cálculo.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Driver, Process
from app.services.calculation_engine import (
    ActivityFact,
    ExpenseFact,
    MonthResult,
    RuleSpec,
    calculate_month,
)
from app.services.calculation_service import load_inputs
from app.services.calculations import round_money

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Scenario:
    """`volume_change`: processo -> variação % do volume. `variable_share`: de 0 a 1, quanto
    do custo direto do processo acompanha o volume (1 = totalmente variável, 0 = fixo)."""

    volume_change: Mapping[int, Decimal] = field(default_factory=dict)
    variable_share: Decimal = Decimal(1)
    allocation_driver_id: int | None = None


def apply_scenario(
    scenario: Scenario,
    expenses: Iterable[ExpenseFact],
    activities: Iterable[ActivityFact],
    rules: Iterable[RuleSpec],
) -> tuple[list[ExpenseFact], list[ActivityFact], list[RuleSpec]]:
    """Entradas alteradas pelo cenário. Custos compartilhados não mudam: só o rateio deles."""

    def factor(process_id: int | None, share: Decimal = Decimal(1)) -> Decimal:
        pct = scenario.volume_change.get(process_id) if process_id is not None else None
        return Decimal(1) + pct / HUNDRED * share if pct is not None else Decimal(1)

    new_activities = [replace(a, quantity=a.quantity * factor(a.process_id)) for a in activities]
    new_expenses = [
        replace(e, amount=round_money(e.amount * factor(e.process_id, scenario.variable_share)))
        if e.nature == "direct"
        else e
        for e in expenses
    ]
    new_rules = [
        replace(r, driver_id=scenario.allocation_driver_id)
        if scenario.allocation_driver_id is not None
        else r
        for r in rules
    ]
    return new_expenses, new_activities, new_rules


@dataclass
class _Totals:
    cost: Decimal = ZERO
    quantity: Decimal | None = None
    uom: str | None = None

    def add_month(self, result: MonthResult, process_id: int) -> None:
        for row in result.rows:
            if row.process_id != process_id:
                continue
            self.cost += row.total_cost
            self.uom = row.unit_of_measure or self.uom
            if row.driver_quantity is not None:
                self.quantity = (self.quantity or ZERO) + row.driver_quantity

    @property
    def unit_cost(self) -> Decimal | None:
        if not self.quantity:
            return None
        return (self.cost / self.quantity).quantize(Decimal("0.0001"))


def _percent(change: Decimal, base: Decimal) -> Decimal | None:
    return (change / base * HUNDRED).quantize(Decimal("0.01")) if base else None


def simulate(db: Session, period_start: date, period_end: date, scenario: Scenario) -> dict:
    inputs = load_inputs(db, period_start, period_end)
    base_results: list[MonthResult] = []
    scenario_results: list[MonthResult] = []
    for month in inputs.months:
        expenses = inputs.expenses.get(month, [])
        activities = inputs.activities.get(month, [])
        budgets = inputs.budgets.get(month, {})
        base_results.append(
            calculate_month(
                month, expenses, activities, budgets, inputs.rules, inputs.default_drivers
            )
        )
        new_expenses, new_activities, new_rules = apply_scenario(
            scenario, expenses, activities, inputs.rules
        )
        scenario_results.append(
            calculate_month(
                month, new_expenses, new_activities, budgets, new_rules, inputs.default_drivers
            )
        )

    process_ids = {
        row.process_id for result in base_results + scenario_results for row in result.rows
    }
    processes = {p.id: p for p in db.scalars(select(Process))}
    items = []
    for process_id in process_ids:
        before, after = _Totals(), _Totals()
        for result in base_results:
            before.add_month(result, process_id)
        for result in scenario_results:
            after.add_month(result, process_id)
        if before.cost == 0 and after.cost == 0:
            continue
        change = after.cost - before.cost
        process = processes.get(process_id)
        items.append(
            {
                "process_id": process_id,
                "process_code": process.code if process else None,
                "process_name": process.name if process else "Sem processo",
                "volume_change_percent": scenario.volume_change.get(process_id, ZERO),
                "driver_uom": before.uom or after.uom,
                "base_cost": round_money(before.cost),
                "scenario_cost": round_money(after.cost),
                "change": round_money(change),
                "change_percent": _percent(change, before.cost),
                "base_volume": before.quantity,
                "scenario_volume": after.quantity,
                "base_unit_cost": before.unit_cost,
                "scenario_unit_cost": after.unit_cost,
            }
        )

    def total(results: list[MonthResult], key: str) -> Decimal:
        return sum((r.composition[key] for r in results), ZERO)

    base_cost = total(base_results, "direct") + total(base_results, "allocated")
    scenario_cost = total(scenario_results, "direct") + total(scenario_results, "allocated")
    base_pending = total(base_results, "pending")
    scenario_pending = total(scenario_results, "pending")

    alerts = []
    if scenario_pending > base_pending:
        alerts.append(
            {
                "code": "SCENARIO_PENDING",
                "severity": "warning",
                "message": "No cenário, "
                f"R$ {round_money(scenario_pending - base_pending)} de custo compartilhado "
                "ficam sem rateio por falta de volume do direcionador escolhido.",
            }
        )
    if not any(r.rows for r in base_results):
        alerts.append(
            {
                "code": "NO_DATA",
                "severity": "info",
                "message": "Não há despesas nem atividades no período escolhido.",
            }
        )

    return {
        "period": {"from": period_start, "to": period_end},
        "currency": "BRL",
        "base_cost": round_money(base_cost),
        "scenario_cost": round_money(scenario_cost),
        "change": round_money(scenario_cost - base_cost),
        "change_percent": _percent(scenario_cost - base_cost, base_cost),
        "base_pending": round_money(base_pending),
        "scenario_pending": round_money(scenario_pending),
        "items": sorted(items, key=lambda i: abs(i["change"]), reverse=True),
        "alerts": alerts,
    }


def resolve(
    db: Session,
    volume_changes: Mapping[str, Decimal],
    variable_share: Decimal,
    allocation_driver_code: str | None,
) -> Scenario:
    """Troca códigos por IDs; código desconhecido é erro, não é ignorado."""
    processes = dict(db.execute(select(Process.code, Process.id)).all())
    details = [
        {"field": "volume_changes", "code": "UNKNOWN_PROCESS", "value": code}
        for code in volume_changes
        if code not in processes
    ]
    driver_id = None
    if allocation_driver_code is not None:
        driver_id = db.scalar(select(Driver.id).where(Driver.code == allocation_driver_code))
        if driver_id is None:
            details.append(
                {
                    "field": "allocation_driver_code",
                    "code": "UNKNOWN_DRIVER",
                    "value": allocation_driver_code,
                }
            )
    if details:
        raise AppError(422, "INVALID_SCENARIO", "O cenário tem campos inválidos.", details)
    return Scenario(
        volume_change={processes[code]: pct for code, pct in volume_changes.items()},
        variable_share=variable_share,
        allocation_driver_id=driver_id,
    )
