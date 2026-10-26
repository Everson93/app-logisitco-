"""Motor de execução mensal (seções 5.2 a 5.5 e Apêndice A).

Funções puras sobre dados já carregados: para um mês de competência, soma custos
diretos, rateia custos compartilhados pela regra aplicável, repassa em cascata o custo
dos processos de apoio, calcula custo unitário pelo direcionador padrão do processo e
compara com o orçamento.

Cascata (step-down): regras com processo de origem rodam depois do rateio das despesas,
em ordem de prioridade. Cada uma repassa o custo total do processo de apoio (direto,
rateado e o que ele já recebeu de cascatas anteriores) aos destinos, pelo direcionador.
Um processo que já repassou seu custo não recebe mais repasses, o que impede ciclos.
"""

import calendar
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.services.calculations import (
    AlertCode,
    allocate_shared_cost,
    budget_variance,
    unit_cost,
)

ENGINE_VERSION = "calc-v2"
ZERO = Decimal(0)

Target = tuple[int, int | None]  # (unit_id, process_id)


class IssueCode(StrEnum):
    NO_ALLOCATION_RULE = "NO_ALLOCATION_RULE"
    ZERO_DRIVER_TOTAL = "ZERO_DRIVER_TOTAL"
    NEGATIVE_DRIVER = "NEGATIVE_DRIVER"
    PENDING_CLASSIFICATION = "PENDING_CLASSIFICATION"
    CASCADE_NOT_TRANSFERRED = "CASCADE_NOT_TRANSFERRED"


class RowAlert(StrEnum):
    OVER_BUDGET = AlertCode.OVER_BUDGET.value
    NO_BUDGET_BASE = AlertCode.NO_BUDGET_BASE.value
    ZERO_DRIVER_QUANTITY = AlertCode.ZERO_DRIVER_QUANTITY.value
    MISSING_BUDGET = "MISSING_BUDGET"
    NO_DRIVER = "NO_DRIVER"


@dataclass(frozen=True)
class ExpenseFact:
    id: int
    competence_date: date
    unit_id: int | None
    process_id: int | None
    account_id: int | None
    amount: Decimal
    nature: str


@dataclass(frozen=True)
class ActivityFact:
    unit_id: int
    process_id: int
    driver_id: int
    quantity: Decimal


@dataclass(frozen=True)
class RuleSpec:
    """Regra de rateio já resolvida para IDs. `None` em um filtro significa "qualquer"."""

    id: int
    driver_id: int
    valid_from: date
    valid_to: date | None
    priority: int
    source_unit_ids: frozenset[int] | None = None
    source_account_ids: frozenset[int] | None = None
    target_unit_ids: frozenset[int] | None = None
    target_process_ids: frozenset[int] | None = None
    # Regra de cascata: repassa o custo desses processos em vez de ratear despesas.
    source_process_ids: frozenset[int] | None = None

    @property
    def is_cascade(self) -> bool:
        return self.source_process_ids is not None

    def valid_in(self, period_start: date, period_end: date) -> bool:
        return self.valid_from <= period_end and (
            self.valid_to is None or self.valid_to >= period_start
        )

    def covers(self, expense: ExpenseFact) -> bool:
        if self.is_cascade:
            return False
        day = expense.competence_date
        if day < self.valid_from or (self.valid_to is not None and day > self.valid_to):
            return False
        if self.source_unit_ids is not None and expense.unit_id not in self.source_unit_ids:
            return False
        if (
            self.source_account_ids is not None
            and expense.account_id not in self.source_account_ids
        ):
            return False
        return True

    def eligible(self, activity: ActivityFact) -> bool:
        return (
            activity.driver_id == self.driver_id
            and (self.target_unit_ids is None or activity.unit_id in self.target_unit_ids)
            and (self.target_process_ids is None or activity.process_id in self.target_process_ids)
        )


@dataclass(frozen=True)
class Allocation:
    expense_id: int | None
    rule_id: int
    target: Target
    driver_quantity: Decimal
    amount: Decimal
    source: Target | None = None  # na cascata, o processo de apoio de origem


@dataclass(frozen=True)
class Issue:
    code: IssueCode
    message: str
    expense_id: int | None = None
    amount: Decimal | None = None
    severity: str = "warning"


@dataclass
class CostRow:
    unit_id: int
    process_id: int | None
    direct_cost: Decimal = ZERO
    allocated_cost: Decimal = ZERO
    transferred_cost: Decimal = ZERO
    driver_id: int | None = None
    driver_quantity: Decimal | None = None
    unit_of_measure: str | None = None
    unit_cost: Decimal | None = None
    budget_amount: Decimal | None = None
    variance_amount: Decimal | None = None
    variance_percent: Decimal | None = None
    alerts: list[str] = field(default_factory=list)

    @property
    def total_cost(self) -> Decimal:
        return self.direct_cost + self.allocated_cost + self.transferred_cost


@dataclass
class MonthResult:
    period_start: date
    rows: list[CostRow]
    allocations: list[Allocation]
    issues: list[Issue]
    composition: dict[str, Decimal]


def pick_rule(expense: ExpenseFact, rules: Iterable[RuleSpec]) -> RuleSpec | None:
    """A regra de menor prioridade numérica vence; empate é decidido pelo menor id."""
    candidates = sorted((r for r in rules if r.covers(expense)), key=lambda r: (r.priority, r.id))
    return candidates[0] if candidates else None


def rule_version(rules: Iterable[Mapping]) -> str:
    """Identificador determinístico do conjunto de regras usado na execução."""
    payload = json.dumps(sorted(rules, key=lambda r: r["id"]), sort_keys=True, default=str)
    return f"{ENGINE_VERSION}:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _allocate(
    expense: ExpenseFact,
    rules: list[RuleSpec],
    activities: list[ActivityFact],
) -> tuple[list[Allocation], Issue | None]:
    rule = pick_rule(expense, rules)
    if rule is None:
        return [], Issue(
            IssueCode.NO_ALLOCATION_RULE,
            "Custo compartilhado sem regra de rateio válida; ficou pendente.",
            expense.id,
            expense.amount,
        )

    drivers: dict[Target, Decimal] = defaultdict(lambda: ZERO)
    for activity in activities:
        if rule.eligible(activity):
            drivers[(activity.unit_id, activity.process_id)] += activity.quantity
    ordered = dict(sorted(drivers.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)))

    result = allocate_shared_cost(expense.amount, ordered)
    if result.pending:
        code = (
            IssueCode.NEGATIVE_DRIVER
            if AlertCode.NEGATIVE_DRIVER in result.alerts
            else IssueCode.ZERO_DRIVER_TOTAL
        )
        return [], Issue(
            code,
            f"Regra {rule.id} sem volume de direcionador elegível no mês; custo ficou pendente.",
            expense.id,
            expense.amount,
        )
    return [
        Allocation(expense.id, rule.id, target, ordered[target], amount)
        for target, amount in result.allocations.items()
    ], None


def _cascade(
    period_start: date,
    period_end: date,
    rows: dict[Target, CostRow],
    row,
    rules: list[RuleSpec],
    activities: list[ActivityFact],
) -> tuple[list[Allocation], list[Issue]]:
    allocations: list[Allocation] = []
    issues: list[Issue] = []
    closed: set[int] = set()  # processos que já repassaram o custo
    cascade_rules = sorted(
        (r for r in rules if r.is_cascade and r.valid_in(period_start, period_end)),
        key=lambda r: (r.priority, r.id),
    )
    for rule in cascade_rules:
        sources = rule.source_process_ids or frozenset()
        closed |= sources
        drivers: dict[Target, Decimal] = defaultdict(lambda: ZERO)
        for activity in activities:
            if rule.eligible(activity) and activity.process_id not in closed:
                drivers[(activity.unit_id, activity.process_id)] += activity.quantity
        ordered = dict(sorted(drivers.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)))

        for source in sorted(rows, key=lambda t: (t[0], t[1] or 0)):
            unit_id, process_id = source
            if process_id not in sources:
                continue
            if rule.source_unit_ids is not None and unit_id not in rule.source_unit_ids:
                continue
            amount = rows[source].total_cost
            if amount == 0:
                continue
            result = allocate_shared_cost(amount, ordered) if amount > 0 else None
            if result is None or result.pending:
                issues.append(
                    Issue(
                        IssueCode.CASCADE_NOT_TRANSFERRED,
                        f"Regra {rule.id}: custo do processo de apoio não foi repassado "
                        "(sem volume elegível ou custo negativo); ficou no processo de origem.",
                        amount=amount,
                    )
                )
                continue
            rows[source].transferred_cost -= amount
            for target, part in result.allocations.items():
                row(target).transferred_cost += part
                allocations.append(
                    Allocation(None, rule.id, target, ordered[target], part, source=source)
                )
    return allocations, issues


def calculate_month(
    period_start: date,
    expenses: list[ExpenseFact],
    activities: list[ActivityFact],
    budgets: Mapping[Target, Decimal],
    rules: list[RuleSpec],
    default_drivers: Mapping[int, tuple[int, str]],
) -> MonthResult:
    """Calcula um mês. `default_drivers`: processo -> (direcionador, unidade de medida)."""
    rows: dict[Target, CostRow] = {}

    def row(target: Target) -> CostRow:
        if target not in rows:
            rows[target] = CostRow(unit_id=target[0], process_id=target[1])
        return rows[target]

    allocations: list[Allocation] = []
    issues: list[Issue] = []
    composition = {"direct": ZERO, "allocated": ZERO, "excluded": ZERO, "pending": ZERO}

    for expense in sorted(expenses, key=lambda e: e.id):
        if expense.nature == "direct":
            row((expense.unit_id, expense.process_id)).direct_cost += expense.amount
            composition["direct"] += expense.amount
        elif expense.nature == "shared":
            allocated, issue = _allocate(expense, rules, activities)
            if issue:
                issues.append(issue)
                composition["pending"] += expense.amount
            for allocation in allocated:
                row(allocation.target).allocated_cost += allocation.amount
                composition["allocated"] += allocation.amount
            allocations.extend(allocated)
        elif expense.nature == "excluded":
            composition["excluded"] += expense.amount
        else:
            issues.append(
                Issue(
                    IssueCode.PENDING_CLASSIFICATION,
                    "Despesa sem classificação (direta, compartilhada ou excluída).",
                    expense.id,
                    expense.amount,
                )
            )
            composition["pending"] += expense.amount

    for target in budgets:
        row(target)

    period_end = period_start.replace(
        day=calendar.monthrange(period_start.year, period_start.month)[1]
    )
    transfers, cascade_issues = _cascade(period_start, period_end, rows, row, rules, activities)
    allocations.extend(transfers)
    issues.extend(cascade_issues)
    composition["transferred"] = sum((t.amount for t in transfers), ZERO)

    volumes: dict[tuple[int, int, int], Decimal] = defaultdict(lambda: ZERO)
    for activity in activities:
        volumes[(activity.unit_id, activity.process_id, activity.driver_id)] += activity.quantity

    for (unit_id, process_id), cost_row in rows.items():
        # Processo de apoio que repassou todo o custo: não tem unitário nem orçamento próprios.
        transferred_out = cost_row.transferred_cost < 0 and cost_row.total_cost == 0
        driver = default_drivers.get(process_id) if process_id is not None else None
        if transferred_out:
            pass
        elif driver is None:
            cost_row.alerts.append(RowAlert.NO_DRIVER)
        else:
            cost_row.driver_id, cost_row.unit_of_measure = driver
            quantity = volumes.get((unit_id, process_id, driver[0]))
            cost_row.driver_quantity = quantity
            uc = unit_cost(cost_row.total_cost, quantity)
            cost_row.unit_cost = uc.value
            cost_row.alerts.extend(uc.alerts)

        budget = budgets.get((unit_id, process_id))
        if budget is None:
            if not transferred_out:
                cost_row.alerts.append(RowAlert.MISSING_BUDGET)
        else:
            variance = budget_variance(cost_row.total_cost, budget)
            cost_row.budget_amount = budget
            cost_row.variance_amount = variance.amount
            cost_row.variance_percent = variance.percent
            cost_row.alerts.extend(variance.alerts)

    ordered_rows = sorted(rows.values(), key=lambda r: (r.unit_id, r.process_id or 0))
    return MonthResult(period_start, ordered_rows, allocations, issues, composition)
