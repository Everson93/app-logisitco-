"""Funções puras do motor de cálculo (seção 5 da especificação).

Sem dependência de banco ou HTTP, para que possam ser testadas isoladamente.
Valores monetários usam Decimal; o arredondamento para centavos acontece apenas
no fechamento da alocação ou na apresentação.
"""

from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import StrEnum

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


class AlertCode(StrEnum):
    OVER_BUDGET = "OVER_BUDGET"
    NO_BUDGET_BASE = "NO_BUDGET_BASE"
    ZERO_DRIVER_QUANTITY = "ZERO_DRIVER_QUANTITY"
    ZERO_DRIVER_TOTAL = "ZERO_DRIVER_TOTAL"
    NEGATIVE_DRIVER = "NEGATIVE_DRIVER"


@dataclass(frozen=True)
class UnitCostResult:
    """Custo unitário; `value` é None (N/D) quando não há volume válido."""

    value: Decimal | None
    alerts: tuple[AlertCode, ...] = ()


@dataclass(frozen=True)
class VarianceResult:
    """Realizado versus orçamento. Desvio positivo = gasto acima do orçado."""

    actual: Decimal
    budget: Decimal
    amount: Decimal
    percent: Decimal | None
    alerts: tuple[AlertCode, ...] = ()


@dataclass(frozen=True)
class AllocationResult:
    """Resultado de um rateio. Se `pending`, nada foi alocado."""

    shared_amount: Decimal
    allocations: dict[Hashable, Decimal] = field(default_factory=dict)
    pending: bool = False
    alerts: tuple[AlertCode, ...] = ()


@dataclass(frozen=True)
class VolumeEfficiencyResult:
    expected_cost_at_actual_volume: Decimal
    volume_effect: Decimal
    efficiency_effect: Decimal


def unit_cost(total_cost: Decimal, driver_quantity: Decimal | None) -> UnitCostResult:
    """custo_unitario = custo_total_do_escopo / quantidade_do_direcionador (RF-008)."""
    if driver_quantity is None or driver_quantity <= 0:
        return UnitCostResult(value=None, alerts=(AlertCode.ZERO_DRIVER_QUANTITY,))
    return UnitCostResult(value=total_cost / driver_quantity)


def budget_variance(actual: Decimal, budget: Decimal) -> VarianceResult:
    """desvio_absoluto = realizado - orcado; percentual só quando orcado != 0 (RF-009)."""
    amount = actual - budget
    alerts: list[AlertCode] = []
    percent: Decimal | None = None

    if budget == 0:
        if actual != 0:
            alerts.append(AlertCode.NO_BUDGET_BASE)
    else:
        percent = amount / budget * HUNDRED
        if amount > 0:
            alerts.append(AlertCode.OVER_BUDGET)

    return VarianceResult(
        actual=actual, budget=budget, amount=amount, percent=percent, alerts=tuple(alerts)
    )


def allocate_shared_cost(
    shared_amount: Decimal, drivers: Mapping[Hashable, Decimal]
) -> AllocationResult:
    """Rateia um custo compartilhado proporcionalmente aos direcionadores elegíveis.

    participacao = direcionador_do_destino / soma_direcionadores_elegiveis
    custo_rateado = custo_compartilhado * participacao

    Os valores são fechados em centavos e o resíduo é distribuído pelo método do
    maior resto (desempate pela ordem de entrada), de forma que a soma alocada seja
    sempre igual ao valor compartilhado. Se o total for zero, nada é rateado e o
    resultado fica pendente.
    """
    if any(qty < 0 for qty in drivers.values()):
        return AllocationResult(
            shared_amount=shared_amount, pending=True, alerts=(AlertCode.NEGATIVE_DRIVER,)
        )

    total = sum(drivers.values(), Decimal(0))
    if total == 0:
        return AllocationResult(
            shared_amount=shared_amount, pending=True, alerts=(AlertCode.ZERO_DRIVER_TOTAL,)
        )

    target_cents = (shared_amount / CENT).to_integral_value(rounding=ROUND_HALF_UP)
    exact = {key: shared_amount * qty / total / CENT for key, qty in drivers.items()}
    floored = {key: value.to_integral_value(rounding=ROUND_DOWN) for key, value in exact.items()}

    residual = int(target_cents - sum(floored.values(), Decimal(0)))
    order = list(drivers)
    by_remainder = sorted(order, key=lambda k: (-(exact[k] - floored[k]), order.index(k)))
    for key in by_remainder[:residual]:
        floored[key] += 1

    return AllocationResult(
        shared_amount=shared_amount,
        allocations={key: (floored[key] * CENT).quantize(CENT) for key in order},
    )


def volume_efficiency(
    base_cost: Decimal,
    base_volume: Decimal,
    actual_cost: Decimal,
    actual_volume: Decimal,
) -> VolumeEfficiencyResult | None:
    """Decompõe a variação de custo em efeito volume e efeito eficiência (seção 5.6).

    Retorna None quando o volume base não permite calcular o custo unitário base.
    """
    base_unit = unit_cost(base_cost, base_volume).value
    if base_unit is None:
        return None
    expected = actual_volume * base_unit
    return VolumeEfficiencyResult(
        expected_cost_at_actual_volume=expected,
        volume_effect=expected - base_cost,
        efficiency_effect=actual_cost - expected,
    )


def round_money(value: Decimal) -> Decimal:
    """Arredondamento de apresentação para centavos."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
