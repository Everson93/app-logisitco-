"""Indicadores de transporte (seção 5.7).

O custo vem do resultado vigente de cada mês, como no dashboard, e inclui o rateio. Os
volumes vêm das atividades do processo de transporte, por direcionador:

- `trip`: viagens concluídas;
- `km`: km total rodado (não só carregado);
- `pallet_transported`: paletes transportados;
- `pallet_capacity`: capacidade nominal em paletes, somada por viagem e tipo de veículo.

Frota própria e frete terceirizado são separados pela natureza da conta (`cost_nature`).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, func, select, tuple_
from sqlalchemy.orm import Session

from app.models import Account, Activity, CostResult, Driver, Expense, Process
from app.services.calculation_service import current_run_by_month, month_end
from app.services.calculations import round_money
from app.services.dashboard import Filters, check_filters

TRANSPORT_PROCESS = "TRANS"
OWN_FLEET = "fleet_own"
THIRD_PARTY = "freight_third_party"
VOLUME_DRIVERS = {
    "trip": "trips",
    "km": "km",
    "pallet_transported": "pallets",
    "pallet_capacity": "capacity",
}
ZERO = Decimal(0)


def _month(column):
    return func.date_trunc("month", column).cast(Date)


def _ratio(num: Decimal, den: Decimal | None, places: str = "0.0001") -> Decimal | None:
    return (num / den).quantize(Decimal(places)) if den else None


@dataclass
class TransportAgg:
    total: Decimal = ZERO
    direct: Decimal = ZERO
    allocated: Decimal = ZERO
    own: Decimal = ZERO
    third_party: Decimal = ZERO
    volumes: dict[str, Decimal] = field(default_factory=dict)

    def merge(self, other: "TransportAgg") -> None:
        self.total += other.total
        self.direct += other.direct
        self.allocated += other.allocated
        self.own += other.own
        self.third_party += other.third_party
        for key, value in other.volumes.items():
            self.volumes[key] = self.volumes.get(key, ZERO) + value

    def indicators(self) -> dict:
        trips = self.volumes.get("trips")
        km = self.volumes.get("km")
        pallets = self.volumes.get("pallets")
        capacity = self.volumes.get("capacity")
        occupancy = _ratio(pallets * 100, capacity, "0.01") if pallets is not None else None
        return {
            "total_cost": round_money(self.total),
            "direct_cost": round_money(self.direct),
            "allocated_cost": round_money(self.allocated),
            "own_fleet_cost": round_money(self.own),
            "third_party_cost": round_money(self.third_party),
            # Direto que não é nem frota própria nem frete (por exemplo, pessoal).
            "other_direct_cost": round_money(self.direct - self.own - self.third_party),
            "trips": trips,
            "km": km,
            "pallets": pallets,
            "capacity_pallets": capacity,
            "cost_per_trip": _ratio(self.total, trips),
            "cost_per_km": _ratio(self.total, km),
            "cost_per_pallet": _ratio(self.total, pallets),
            "km_per_trip": _ratio(km, trips, "0.01") if km is not None else None,
            "occupancy_percent": occupancy,
        }


def transport(db: Session, filters: Filters) -> dict:
    check_filters(filters)
    start, end = filters.date_from.replace(day=1), month_end(filters.date_to)
    current = current_run_by_month(db, start, end)
    process_id = db.scalar(select(Process.id).where(Process.code == TRANSPORT_PROCESS))

    by_month: dict[date, TransportAgg] = defaultdict(TransportAgg)
    if process_id is not None and current:
        costs = select(
            CostResult.period_start,
            func.sum(CostResult.total_cost),
            func.sum(CostResult.direct_cost),
            func.sum(CostResult.allocated_cost),
        ).where(
            CostResult.process_id == process_id,
            tuple_(CostResult.calculation_run_id, CostResult.period_start).in_(
                [(run_id, month) for month, run_id in current.items()]
            ),
        )
        if filters.unit_id is not None:
            costs = costs.where(CostResult.unit_id == filters.unit_id)
        for month, total, direct, allocated in db.execute(costs.group_by(CostResult.period_start)):
            agg = by_month[month]
            agg.total, agg.direct, agg.allocated = total, direct, allocated

        month_col = func.date_trunc("month", Expense.competence_date).cast(
            Expense.competence_date.type
        )
        split = (
            select(month_col, Account.cost_nature, func.sum(Expense.amount))
            .join(Account, Account.id == Expense.account_id)
            .where(
                Expense.process_id == process_id,
                Expense.nature == "direct",
                Expense.competence_date.between(start, end),
                Account.cost_nature.in_([OWN_FLEET, THIRD_PARTY]),
            )
            .group_by(month_col, Account.cost_nature)
        )
        if filters.unit_id is not None:
            split = split.where(Expense.unit_id == filters.unit_id)
        for month, nature, amount in db.execute(split):
            if month not in current:
                continue
            if nature == OWN_FLEET:
                by_month[month].own += amount
            else:
                by_month[month].third_party += amount

    if process_id is not None:
        activity_month = _month(Activity.activity_date)
        volumes = (
            select(activity_month, Driver.code, func.sum(Activity.quantity))
            .join(Driver, Driver.id == Activity.driver_id)
            .where(
                Activity.process_id == process_id,
                Activity.activity_date.between(start, end),
                Driver.code.in_(list(VOLUME_DRIVERS)),
            )
            .group_by(activity_month, Driver.code)
        )
        if filters.unit_id is not None:
            volumes = volumes.where(Activity.unit_id == filters.unit_id)
        for month, code, quantity in db.execute(volumes):
            by_month[month].volumes[VOLUME_DRIVERS[code]] = quantity

    total = TransportAgg()
    months = []
    for month in filters.months:
        if month not in current:
            months.append({"period": month, "calculated": False})
            continue
        agg = by_month[month]
        total.merge(agg)
        months.append({"period": month, "calculated": True, **agg.indicators()})

    indicators = total.indicators()
    return {
        "period": {"from": filters.date_from, "to": filters.date_to},
        "currency": "BRL",
        **indicators,
        "months": months,
        "alerts": _alerts(filters, current, indicators),
    }


def _alerts(filters: Filters, current: dict[date, int], indicators: dict) -> list[dict]:
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
    for key, code, label in (
        ("km", "NO_KM", "km rodado"),
        ("pallets", "NO_PALLETS", "paletes transportados"),
        ("capacity_pallets", "NO_CAPACITY", "capacidade nominal"),
    ):
        if indicators[key] is None and current:
            alerts.append(
                {
                    "code": code,
                    "severity": "info",
                    "message": f"Sem {label} importado no período: indicadores que dependem "
                    "dele ficam N/D.",
                }
            )
    occupancy = indicators["occupancy_percent"]
    if occupancy is not None and occupancy > 100:
        alerts.append(
            {
                "code": "OCCUPANCY_OVER_100",
                "severity": "warning",
                "message": "Paletes transportados acima da capacidade nominal: confira se a "
                "capacidade corresponde ao tipo de veículo.",
            }
        )
    return alerts
