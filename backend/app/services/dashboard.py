"""Consultas do dashboard e do relatório (seção 11.1; RF-009 a RF-011).

Os números vêm sempre do resultado vigente de cada mês, ou seja, da execução de
cálculo mais recente que cobre o mês. O frontend não calcula indicadores.
"""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CalculationIssue, CostResult, Driver, Expense, Process, Unit
from app.services.calculation_service import current_run_by_month, month_end, months_between
from app.services.calculations import budget_variance, round_money

MAX_MONTHS = 36
ZERO = Decimal(0)


@dataclass(frozen=True)
class Filters:
    date_from: date
    date_to: date
    unit_id: int | None = None
    process_id: int | None = None

    @property
    def months(self) -> list[date]:
        return months_between(self.date_from.replace(day=1), self.date_to)


@dataclass
class Aggregate:
    actual: Decimal = ZERO
    direct: Decimal = ZERO
    allocated: Decimal = ZERO
    budget: Decimal | None = None
    driver_ids: set[int | None] = field(default_factory=set)
    uoms: set[str | None] = field(default_factory=set)
    quantity: Decimal | None = None

    def add(self, row: CostResult) -> None:
        self.actual += row.total_cost
        self.direct += row.direct_cost
        self.allocated += row.allocated_cost
        if row.budget_amount is not None:
            self.budget = (self.budget or ZERO) + row.budget_amount
        self.driver_ids.add(row.driver_id)
        self.uoms.add(row.unit_of_measure)
        if row.driver_quantity is not None:
            self.quantity = (self.quantity or ZERO) + row.driver_quantity

    def indicators(self) -> dict:
        """Desvio e custo unitário. Unitário só quando há um único direcionador (seção 5.4)."""
        variance = budget_variance(self.actual, self.budget) if self.budget is not None else None
        single_driver = len(self.driver_ids) == 1 and None not in self.driver_ids
        unit_cost = None
        if single_driver and self.quantity:
            unit_cost = self.actual / self.quantity
        return {
            "actual_cost": round_money(self.actual),
            "direct_cost": round_money(self.direct),
            "allocated_cost": round_money(self.allocated),
            "budget_cost": round_money(self.budget) if self.budget is not None else None,
            "variance_amount": round_money(variance.amount) if variance else None,
            "variance_percent": (
                variance.percent.quantize(Decimal("0.01"))
                if variance and variance.percent is not None
                else None
            ),
            "driver_quantity": self.quantity if single_driver else None,
            "driver_uom": next(iter(self.uoms)) if single_driver else None,
            "unit_cost": unit_cost.quantize(Decimal("0.0001")) if unit_cost is not None else None,
            "single_driver": single_driver,
        }


def check_filters(filters: Filters) -> None:
    if filters.date_to < filters.date_from:
        raise AppError(
            422,
            "INVALID_PERIOD",
            "A data final é anterior à inicial.",
            [{"field": "to", "code": "BEFORE_FROM"}],
        )
    if len(filters.months) > MAX_MONTHS:
        raise AppError(422, "INVALID_PERIOD", f"O período pode ter no máximo {MAX_MONTHS} meses.")


def _current(db: Session, filters: Filters) -> dict[date, int]:
    check_filters(filters)
    return current_run_by_month(db, filters.date_from.replace(day=1), month_end(filters.date_to))


def _results(db: Session, filters: Filters, current: dict[date, int]) -> list[CostResult]:
    if not current:
        return []
    stmt = select(CostResult).where(
        tuple_(CostResult.calculation_run_id, CostResult.period_start).in_(
            [(run_id, month) for month, run_id in current.items()]
        )
    )
    if filters.unit_id is not None:
        stmt = stmt.where(CostResult.unit_id == filters.unit_id)
    if filters.process_id is not None:
        stmt = stmt.where(CostResult.process_id == filters.process_id)
    return list(db.scalars(stmt.order_by(CostResult.period_start, CostResult.unit_id)))


def _pending(db: Session, filters: Filters, current: dict[date, int]) -> tuple[Decimal, int]:
    if not current:
        return ZERO, 0
    stmt = select(func.coalesce(func.sum(CalculationIssue.amount), 0), func.count()).where(
        tuple_(CalculationIssue.calculation_run_id, CalculationIssue.period_start).in_(
            [(run_id, month) for month, run_id in current.items()]
        )
    )
    if filters.unit_id is not None:
        stmt = stmt.join(Expense, Expense.id == CalculationIssue.expense_id).where(
            Expense.unit_id == filters.unit_id
        )
    if filters.process_id is not None:
        # Pendências não têm processo de destino definido: não pertencem a um processo.
        return ZERO, 0
    amount, count = db.execute(stmt).one()
    return Decimal(amount), count


def _excluded(db: Session, filters: Filters) -> Decimal:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.nature == "excluded",
        Expense.competence_date.between(
            filters.date_from.replace(day=1), month_end(filters.date_to)
        ),
    )
    if filters.unit_id is not None:
        stmt = stmt.where(Expense.unit_id == filters.unit_id)
    if filters.process_id is not None:
        stmt = stmt.where(Expense.process_id == filters.process_id)
    return Decimal(db.scalar(stmt))


def summary(db: Session, filters: Filters) -> dict:
    current = _current(db, filters)
    rows = _results(db, filters, current)
    total = Aggregate()
    for row in rows:
        total.add(row)
    indicators = total.indicators()
    pending_amount, pending_count = _pending(db, filters, current)
    excluded = _excluded(db, filters)

    alerts = []
    missing = [m for m in filters.months if m not in current]
    if missing:
        alerts.append(
            {
                "code": "MISSING_CALCULATION",
                "severity": "warning",
                "message": f"{len(missing)} mês(es) do período ainda sem cálculo executado.",
                "months": [m.isoformat() for m in missing],
            }
        )
    if indicators["variance_amount"] is not None and indicators["variance_amount"] > 0:
        alerts.append(
            {
                "code": "OVER_BUDGET",
                "severity": "warning",
                "message": "Realizado acima do orçamento.",
            }
        )
    if total.budget is not None and total.budget == 0 and total.actual > 0:
        alerts.append(
            {
                "code": "NO_BUDGET_BASE",
                "severity": "info",
                "message": "Sem base orçamentária para o desvio percentual.",
            }
        )
    if pending_count:
        alerts.append(
            {
                "code": "PENDING_COSTS",
                "severity": "warning",
                "message": f"{pending_count} custo(s) pendente(s) de rateio ou classificação.",
            }
        )
    if rows and not indicators["single_driver"]:
        alerts.append(
            {
                "code": "MIXED_DRIVERS",
                "severity": "info",
                "message": "Filtro com mais de um direcionador: custo unitário não é somado. "
                "Filtre por processo para vê-lo.",
            }
        )
    row_alerts: dict[str, int] = defaultdict(int)
    for row in rows:
        for code in row.alerts:
            row_alerts[code] += 1
    if row_alerts.get("ZERO_DRIVER_QUANTITY"):
        alerts.append(
            {
                "code": "ZERO_DRIVER_QUANTITY",
                "severity": "warning",
                "message": f"{row_alerts['ZERO_DRIVER_QUANTITY']} linha(s) sem volume do "
                "direcionador: custo unitário N/D.",
            }
        )

    indicators.pop("single_driver")
    return {
        "period": {"from": filters.date_from, "to": filters.date_to},
        "currency": "BRL",
        **indicators,
        "composition": {
            "direct": round_money(total.direct),
            "allocated": round_money(total.allocated),
            "excluded": round_money(excluded),
            "pending": round_money(pending_amount),
        },
        "calculation_run_ids": sorted(set(current.values())),
        "alerts": alerts,
    }


def trend(db: Session, filters: Filters) -> list[dict]:
    current = _current(db, filters)
    by_month: dict[date, Aggregate] = defaultdict(Aggregate)
    for row in _results(db, filters, current):
        by_month[row.period_start].add(row)
    points = []
    for month in filters.months:
        if month not in current:
            points.append({"period": month, "calculated": False})
            continue
        indicators = by_month[month].indicators()
        indicators.pop("single_driver")
        points.append({"period": month, "calculated": True, **indicators})
    return points


def by_process(db: Session, filters: Filters) -> list[dict]:
    current = _current(db, filters)
    groups: dict[int | None, Aggregate] = defaultdict(Aggregate)
    for row in _results(db, filters, current):
        groups[row.process_id].add(row)
    processes = {p.id: p for p in db.scalars(select(Process))}
    items = []
    for process_id, agg in groups.items():
        indicators = agg.indicators()
        indicators.pop("single_driver")
        process = processes.get(process_id)
        items.append(
            {
                "process_id": process_id,
                "process_code": process.code if process else None,
                "process_name": process.name if process else "Sem processo",
                **indicators,
            }
        )
    return sorted(items, key=lambda i: i["actual_cost"], reverse=True)


REPORT_COLUMNS = [
    "periodo",
    "unidade_codigo",
    "unidade_nome",
    "processo_codigo",
    "processo_nome",
    "moeda",
    "custo_direto",
    "custo_rateado",
    "custo_total",
    "orcamento",
    "desvio",
    "desvio_percentual",
    "direcionador",
    "volume",
    "unidade_medida",
    "custo_unitario",
    "alertas",
    "execucao_calculo",
]


def report_csv(db: Session, filters: Filters, *, brazilian: bool) -> str:
    """CSV do recorte filtrado. `brazilian`: separador ';' e vírgula decimal (Excel pt-BR)."""
    current = _current(db, filters)
    rows = _results(db, filters, current)
    units = {u.id: u for u in db.scalars(select(Unit))}
    processes = {p.id: p for p in db.scalars(select(Process))}
    drivers = {d.id: d.code for d in db.scalars(select(Driver))}

    def num(value: Decimal | None, places: str = "0.01") -> str:
        if value is None:
            return ""
        text = format(value.quantize(Decimal(places)), "f")
        return text.replace(".", ",") if brazilian else text

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";" if brazilian else ",", lineterminator="\r\n")
    writer.writerow(REPORT_COLUMNS)
    for row in rows:
        unit = units[row.unit_id]
        process = processes.get(row.process_id)
        writer.writerow(
            [
                row.period_start.strftime("%Y-%m"),
                unit.code,
                unit.name,
                process.code if process else "",
                process.name if process else "Sem processo",
                "BRL",
                num(row.direct_cost),
                num(row.allocated_cost),
                num(row.total_cost),
                num(row.budget_amount),
                num(row.variance_amount),
                num(row.variance_percent),
                drivers.get(row.driver_id, ""),
                num(row.driver_quantity, "0.0001"),
                row.unit_of_measure or "",
                num(row.unit_cost, "0.0001"),
                "|".join(row.alerts),
                row.calculation_run_id,
            ]
        )
    return buffer.getvalue()
