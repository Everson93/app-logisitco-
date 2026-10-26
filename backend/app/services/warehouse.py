"""Indicadores de armazenagem e separação (seção 5.8).

Para cada processo do armazém (REC, ARM, PICK, EXP):

- custo unitário pelo direcionador padrão, separado em direto, rateado e repassado em cascata;
- produtividade: volume do direcionador padrão por hora produtiva (`productive_hour`);
- no picking, linhas separadas (`line_picked`) por hora e por pedido.

Produtividade e custo por hora usam só as unidades e meses que têm horas apontadas, para
não dividir o volume de lojas sem apontamento pelas horas do CD.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, func, select, tuple_
from sqlalchemy.orm import Session

from app.models import Activity, CostResult, Driver, Process
from app.services.calculation_service import current_run_by_month, month_end
from app.services.calculations import round_money
from app.services.dashboard import Filters, check_filters

WAREHOUSE_PROCESSES = ("REC", "ARM", "PICK", "EXP")
HOURS = "productive_hour"
LINES = "line_picked"
ZERO = Decimal(0)

Key = tuple[int, int, date]  # (processo, unidade, mês)


def _ratio(num: Decimal | None, den: Decimal | None, places: str = "0.0001") -> Decimal | None:
    if num is None or not den:
        return None
    return (num / den).quantize(Decimal(places))


@dataclass
class Cell:
    """Custo e volumes de um processo numa unidade e num mês."""

    total: Decimal = ZERO
    direct: Decimal = ZERO
    allocated: Decimal = ZERO
    transferred: Decimal = ZERO
    volume: Decimal | None = None
    uom: str | None = None
    hours: Decimal | None = None
    lines: Decimal | None = None


@dataclass
class ProcessAgg:
    total: Decimal = ZERO
    direct: Decimal = ZERO
    allocated: Decimal = ZERO
    transferred: Decimal = ZERO
    volume: Decimal = ZERO
    has_volume: bool = False
    uom: str | None = None
    hours: Decimal = ZERO
    volume_with_hours: Decimal = ZERO
    cost_with_hours: Decimal = ZERO
    lines: Decimal = ZERO
    lines_hours: Decimal = ZERO
    orders_with_lines: Decimal = ZERO
    months: dict[date, "ProcessAgg"] = field(default_factory=dict)

    def add(self, cell: Cell) -> None:
        self.total += cell.total
        self.direct += cell.direct
        self.allocated += cell.allocated
        self.transferred += cell.transferred
        self.uom = self.uom or cell.uom
        if cell.volume is not None:
            self.volume += cell.volume
            self.has_volume = True
        if cell.hours:
            self.hours += cell.hours
            self.volume_with_hours += cell.volume or ZERO
            self.cost_with_hours += cell.total
            if cell.lines is not None:
                self.lines_hours += cell.hours
        if cell.lines is not None:
            self.lines += cell.lines
            self.orders_with_lines += cell.volume or ZERO

    def indicators(self) -> dict:
        volume = self.volume if self.has_volume else None
        hours = self.hours or None
        return {
            "total_cost": round_money(self.total),
            "direct_cost": round_money(self.direct),
            "allocated_cost": round_money(self.allocated),
            "transferred_cost": round_money(self.transferred),
            "volume": volume,
            "driver_uom": self.uom,
            "unit_cost": _ratio(self.total, volume),
            "direct_unit_cost": _ratio(self.direct, volume),
            "allocated_unit_cost": _ratio(self.allocated, volume),
            "transferred_unit_cost": _ratio(self.transferred, volume),
            "productive_hours": hours,
            "productivity_per_hour": _ratio(self.volume_with_hours, hours, "0.01"),
            "cost_per_hour": _ratio(self.cost_with_hours, hours, "0.01"),
            "lines": self.lines or None,
            "lines_per_hour": _ratio(self.lines or None, self.lines_hours, "0.01"),
            "lines_per_order": _ratio(self.lines or None, self.orders_with_lines, "0.01"),
        }


def _month(column):
    return func.date_trunc("month", column).cast(Date)


def warehouse(db: Session, filters: Filters) -> dict:
    check_filters(filters)
    start, end = filters.date_from.replace(day=1), month_end(filters.date_to)
    current = current_run_by_month(db, start, end)
    processes = {
        p.id: p for p in db.scalars(select(Process).where(Process.code.in_(WAREHOUSE_PROCESSES)))
    }
    if filters.process_id is not None:
        processes = {k: v for k, v in processes.items() if k == filters.process_id}

    cells: dict[Key, Cell] = defaultdict(Cell)
    if processes and current:
        costs = select(CostResult).where(
            CostResult.process_id.in_(list(processes)),
            tuple_(CostResult.calculation_run_id, CostResult.period_start).in_(
                [(run_id, month) for month, run_id in current.items()]
            ),
        )
        if filters.unit_id is not None:
            costs = costs.where(CostResult.unit_id == filters.unit_id)
        for row in db.scalars(costs):
            cell = cells[(row.process_id, row.unit_id, row.period_start)]
            cell.total, cell.direct, cell.allocated, cell.transferred = (
                row.total_cost,
                row.direct_cost,
                row.allocated_cost,
                row.transferred_cost,
            )
            cell.volume, cell.uom = row.driver_quantity, row.unit_of_measure

        month_col = _month(Activity.activity_date)
        extras = (
            select(
                Activity.process_id,
                Activity.unit_id,
                month_col,
                Driver.code,
                func.sum(Activity.quantity),
            )
            .join(Driver, Driver.id == Activity.driver_id)
            .where(
                Activity.process_id.in_(list(processes)),
                Activity.activity_date.between(start, end),
                Driver.code.in_([HOURS, LINES]),
            )
            .group_by(Activity.process_id, Activity.unit_id, month_col, Driver.code)
        )
        if filters.unit_id is not None:
            extras = extras.where(Activity.unit_id == filters.unit_id)
        for process_id, unit_id, month, code, quantity in db.execute(extras):
            if month not in current:
                continue
            cell = cells[(process_id, unit_id, month)]
            if code == HOURS:
                cell.hours = quantity
            else:
                cell.lines = quantity

    aggs: dict[int, ProcessAgg] = defaultdict(ProcessAgg)
    for (process_id, _, month), cell in cells.items():
        aggs[process_id].add(cell)
        aggs[process_id].months.setdefault(month, ProcessAgg()).add(cell)

    items = []
    for process_id, agg in aggs.items():
        process = processes[process_id]
        items.append(
            {
                "process_id": process_id,
                "process_code": process.code,
                "process_name": process.name,
                **agg.indicators(),
                "months": [
                    {
                        "period": month,
                        "calculated": True,
                        **agg.months.get(month, ProcessAgg()).indicators(),
                    }
                    if month in current
                    else {"period": month, "calculated": False}
                    for month in filters.months
                ],
            }
        )
    order = {code: i for i, code in enumerate(WAREHOUSE_PROCESSES)}
    items.sort(key=lambda i: order[i["process_code"]])
    return {
        "period": {"from": filters.date_from, "to": filters.date_to},
        "currency": "BRL",
        "items": items,
        "alerts": _alerts(filters, current, items),
    }


def _alerts(filters: Filters, current: dict[date, int], items: list[dict]) -> list[dict]:
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
    without_hours = [i["process_code"] for i in items if i["productive_hours"] is None]
    if without_hours:
        alerts.append(
            {
                "code": "NO_PRODUCTIVE_HOURS",
                "severity": "info",
                "message": "Sem horas produtivas para "
                f"{', '.join(without_hours)}: produtividade e custo por hora ficam N/D.",
            }
        )
    return alerts
