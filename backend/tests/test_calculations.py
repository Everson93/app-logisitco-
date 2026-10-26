from decimal import Decimal as D

from app.services.calculations import (
    AlertCode,
    allocate_shared_cost,
    budget_variance,
    round_money,
    unit_cost,
    volume_efficiency,
)


def test_custo_unitario_simples():
    result = unit_cost(D("180000"), D("15000"))
    assert result.value == D("12")
    assert result.alerts == ()


def test_custo_unitario_volume_zero_retorna_nd_e_alerta():
    result = unit_cost(D("100"), D("0"))
    assert result.value is None
    assert AlertCode.ZERO_DRIVER_QUANTITY in result.alerts


def test_custo_unitario_volume_ausente():
    assert unit_cost(D("100"), None).value is None


def test_orcamento_excedido():
    result = budget_variance(D("180000"), D("165000"))
    assert result.amount == D("15000")
    assert round_money(result.percent) == D("9.09")
    assert AlertCode.OVER_BUDGET in result.alerts


def test_abaixo_do_orcamento_tem_desvio_negativo_sem_alerta():
    result = budget_variance(D("150000"), D("165000"))
    assert result.amount == D("-15000")
    assert result.percent < 0
    assert result.alerts == ()


def test_orcamento_zero_nao_divide_por_zero():
    result = budget_variance(D("100"), D("0"))
    assert result.percent is None
    assert result.amount == D("100")
    assert AlertCode.NO_BUDGET_BASE in result.alerts


def test_rateio_proporcional():
    result = allocate_shared_cost(D("1000"), {"A": D("25"), "B": D("75")})
    assert not result.pending
    assert result.allocations == {"A": D("250.00"), "B": D("750.00")}


def test_rateio_exemplo_da_especificacao():
    # R$ 10.000 compartilhados; unidade A com 2.000 de 5.000 paletes elegíveis = 40%.
    result = allocate_shared_cost(D("10000"), {"A": D("2000"), "outras": D("3000")})
    assert result.allocations["A"] == D("4000.00")


def test_rateio_sem_driver_fica_pendente():
    result = allocate_shared_cost(D("1000"), {"A": D("0"), "B": D("0")})
    assert result.pending
    assert result.allocations == {}
    assert AlertCode.ZERO_DRIVER_TOTAL in result.alerts


def test_rateio_com_driver_negativo_fica_pendente():
    result = allocate_shared_cost(D("1000"), {"A": D("-1"), "B": D("5")})
    assert result.pending
    assert AlertCode.NEGATIVE_DRIVER in result.alerts


def test_arredondamento_fecha_com_valor_original():
    result = allocate_shared_cost(D("100"), {"A": D("1"), "B": D("1"), "C": D("1")})
    assert sum(result.allocations.values()) == D("100.00")
    # Maior resto empatado: o centavo extra vai para o primeiro, de forma determinística.
    assert result.allocations == {"A": D("33.34"), "B": D("33.33"), "C": D("33.33")}


def test_arredondamento_maior_resto():
    # 10,00 em 1/6, 2/6, 3/6 -> 1,666.. / 3,333.. / 5,00: o centavo vai para A (maior resto).
    result = allocate_shared_cost(D("10"), {"A": D("1"), "B": D("2"), "C": D("3")})
    assert result.allocations == {"A": D("1.67"), "B": D("3.33"), "C": D("5.00")}
    assert sum(result.allocations.values()) == D("10.00")


def test_efeito_volume_e_eficiencia():
    # Base: R$ 100.000 para 10.000 paletes (R$ 10/palete). Real: R$ 130.000 para 12.000.
    result = volume_efficiency(D("100000"), D("10000"), D("130000"), D("12000"))
    assert result.expected_cost_at_actual_volume == D("120000")
    assert result.volume_effect == D("20000")
    assert result.efficiency_effect == D("10000")


def test_efeito_volume_sem_base():
    assert volume_efficiency(D("100"), D("0"), D("100"), D("10")) is None
