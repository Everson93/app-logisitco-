from datetime import date
from decimal import Decimal as D

from app.services.calculation_engine import (
    ActivityFact,
    ExpenseFact,
    IssueCode,
    RowAlert,
    RuleSpec,
    calculate_month,
    pick_rule,
    rule_version,
)

SEP = date(2026, 9, 1)
DAY = date(2026, 9, 30)
CD, LOJA = 1, 2
REC, PICK = 10, 11
PALLET, ORDER = 100, 101
DEFAULT_DRIVERS = {REC: (PALLET, "pallet"), PICK: (ORDER, "order")}


def expense(id_, amount, nature="direct", unit=CD, process=REC, account=None, day=DAY):
    return ExpenseFact(id_, day, unit, process, account, D(amount), nature)


def activity(unit, process, driver, qty):
    return ActivityFact(unit, process, driver, D(qty))


def rule(id_=1, driver=PALLET, priority=100, **kwargs):
    return RuleSpec(
        id=id_,
        driver_id=driver,
        valid_from=kwargs.pop("valid_from", date(2026, 1, 1)),
        valid_to=kwargs.pop("valid_to", None),
        priority=priority,
        **kwargs,
    )


def by_target(result):
    return {(r.unit_id, r.process_id): r for r in result.rows}


def test_exemplo_de_conferencia_da_especificacao():
    # Seção 5.9: R$ 180.000, 15.000 paletes, orçamento R$ 165.000.
    result = calculate_month(
        SEP,
        [expense(1, "180000")],
        [activity(CD, REC, PALLET, "15000")],
        {(CD, REC): D("165000")},
        [],
        DEFAULT_DRIVERS,
    )
    (row,) = result.rows
    assert row.total_cost == D("180000")
    assert row.unit_cost == D(12)
    assert row.driver_quantity == D(15000)
    assert row.unit_of_measure == "pallet"
    assert row.variance_amount == D(15000)
    assert round(row.variance_percent, 2) == D("9.09")
    assert row.alerts == [RowAlert.OVER_BUDGET]


def test_rateio_do_exemplo_da_especificacao():
    # Seção 5.3: R$ 10.000; unidade A com 2.000 de 5.000 paletes -> R$ 4.000.
    result = calculate_month(
        SEP,
        [expense(1, "10000", nature="shared", process=None)],
        [activity(CD, REC, PALLET, "2000"), activity(LOJA, REC, PALLET, "3000")],
        {},
        [rule()],
        DEFAULT_DRIVERS,
    )
    rows = by_target(result)
    assert rows[(CD, REC)].allocated_cost == D("4000.00")
    assert rows[(LOJA, REC)].allocated_cost == D("6000.00")
    assert [a.amount for a in result.allocations] == [D("4000.00"), D("6000.00")]
    assert result.composition["allocated"] == D("10000.00")
    assert result.issues == []


def test_soma_alocada_fecha_com_o_valor_compartilhado():
    result = calculate_month(
        SEP,
        [expense(1, "100", nature="shared", process=None)],
        [activity(u, REC, PALLET, "1") for u in (1, 2, 3)],
        {},
        [rule()],
        DEFAULT_DRIVERS,
    )
    assert sum(a.amount for a in result.allocations) == D("100.00")


def test_custo_compartilhado_sem_regra_fica_pendente():
    result = calculate_month(
        SEP,
        [expense(1, "5000", nature="shared", process=None)],
        [activity(CD, REC, PALLET, "10")],
        {},
        [],
        DEFAULT_DRIVERS,
    )
    assert result.allocations == []
    assert result.rows == []
    (issue,) = result.issues
    assert issue.code is IssueCode.NO_ALLOCATION_RULE
    assert issue.amount == D(5000)
    assert result.composition["pending"] == D(5000)


def test_regra_sem_volume_elegivel_fica_pendente():
    result = calculate_month(
        SEP,
        [expense(1, "5000", nature="shared", process=None)],
        [activity(CD, PICK, ORDER, "10")],  # direcionador diferente do da regra
        {},
        [rule()],
        DEFAULT_DRIVERS,
    )
    assert [i.code for i in result.issues] == [IssueCode.ZERO_DRIVER_TOTAL]


def test_destinos_elegiveis_restringem_o_denominador():
    result = calculate_month(
        SEP,
        [expense(1, "1000", nature="shared", process=None)],
        [activity(CD, REC, PALLET, "25"), activity(LOJA, REC, PALLET, "75")],
        {},
        [rule(target_unit_ids=frozenset({LOJA}))],
        DEFAULT_DRIVERS,
    )
    assert {a.target: a.amount for a in result.allocations} == {(LOJA, REC): D("1000.00")}


def test_prioridade_vigencia_e_escopo_da_regra():
    exp = expense(1, "1", nature="shared", account=6199)
    old = rule(1, priority=1, valid_to=date(2026, 8, 31))
    other_account = rule(2, priority=1, source_account_ids=frozenset({6101}))
    low = rule(3, priority=50)
    high = rule(4, priority=10)
    assert pick_rule(exp, [old, other_account, low, high]) is high
    assert pick_rule(exp, [old, other_account]) is None
    # Empate de prioridade: vence o menor id, de forma determinística.
    assert pick_rule(exp, [rule(9, priority=5), rule(7, priority=5)]).id == 7


def test_excluidas_e_sem_classificacao_entram_na_composicao():
    result = calculate_month(
        SEP,
        [
            expense(1, "100"),
            expense(2, "30", nature="excluded"),
            expense(3, "20", nature="pending_classification"),
        ],
        [],
        {},
        [],
        DEFAULT_DRIVERS,
    )
    assert result.composition == {
        "direct": D(100),
        "allocated": D(0),
        "transferred": D(0),
        "excluded": D(30),
        "pending": D(20),
    }
    assert [i.code for i in result.issues] == [IssueCode.PENDING_CLASSIFICATION]


def test_volume_zero_ausente_orcamento_zero_e_sem_orcamento():
    result = calculate_month(
        SEP,
        [expense(1, "100"), expense(2, "50", process=PICK), expense(3, "10", process=None)],
        [activity(CD, REC, PALLET, "0")],
        {(CD, REC): D(0)},
        [],
        DEFAULT_DRIVERS,
    )
    rows = by_target(result)
    rec, pick, none = rows[(CD, REC)], rows[(CD, PICK)], rows[(CD, None)]
    assert rec.unit_cost is None
    assert rec.variance_percent is None
    assert set(rec.alerts) == {RowAlert.ZERO_DRIVER_QUANTITY, RowAlert.NO_BUDGET_BASE}
    assert pick.unit_cost is None
    assert set(pick.alerts) == {RowAlert.ZERO_DRIVER_QUANTITY, RowAlert.MISSING_BUDGET}
    assert set(none.alerts) == {RowAlert.NO_DRIVER, RowAlert.MISSING_BUDGET}


def test_orcamento_sem_custo_aparece_com_desvio_negativo():
    result = calculate_month(SEP, [], [], {(CD, REC): D(500)}, [], DEFAULT_DRIVERS)
    (row,) = result.rows
    assert row.total_cost == 0
    assert row.variance_amount == D(-500)


def test_versao_da_regra_e_deterministica():
    a = [{"id": 2, "priority": 1}, {"id": 1, "priority": 5}]
    assert rule_version(a) == rule_version(list(reversed(a)))
    assert rule_version(a) != rule_version([{"id": 1, "priority": 6}, {"id": 2, "priority": 1}])
    assert rule_version([]).startswith("calc-v2:")


# Rateio em cascata: ADM e MAN são processos de apoio, sem direcionador padrão.
ADM, MAN = 12, 14
HOUR = 102


def test_cascata_repassa_o_processo_de_apoio_por_horas():
    result = calculate_month(
        SEP,
        [
            expense(1, "1000", process=ADM),
            expense(2, "5000", process=REC),
            expense(3, "3000", process=PICK),
            expense(4, "600", nature="shared", process=None),
        ],
        [
            activity(CD, REC, PALLET, "1000"),
            activity(CD, PICK, ORDER, "500"),
            activity(CD, REC, HOUR, "100"),
            activity(CD, PICK, HOUR, "300"),
        ],
        {},
        [rule(1, PALLET), rule(2, HOUR, source_process_ids=frozenset({ADM}))],
        DEFAULT_DRIVERS,
    )
    rows = by_target(result)
    adm, rec, pick = rows[(CD, ADM)], rows[(CD, REC)], rows[(CD, PICK)]
    assert (adm.direct_cost, adm.transferred_cost, adm.total_cost) == (D(1000), D(-1000), D(0))
    assert adm.alerts == []  # sem NO_DRIVER nem MISSING_BUDGET: repassou tudo
    # O rateio das despesas vem antes; a cascata soma por cima.
    assert (rec.allocated_cost, rec.transferred_cost, rec.total_cost) == (D(600), D(250), D(5850))
    assert rec.unit_cost == D("5.85")
    assert (pick.transferred_cost, pick.total_cost) == (D(750), D(3750))
    assert result.composition["transferred"] == D(1000)

    transfers = [a for a in result.allocations if a.expense_id is None]
    assert {(a.source, a.target, a.amount) for a in transfers} == {
        ((CD, ADM), (CD, REC), D(250)),
        ((CD, ADM), (CD, PICK), D(750)),
    }
    assert sum(r.total_cost for r in result.rows) == D(9600)


def test_cascata_em_degraus_nao_volta_para_quem_ja_repassou():
    result = calculate_month(
        SEP,
        [expense(1, "1000", process=ADM), expense(2, "500", process=MAN)],
        [
            activity(CD, ADM, HOUR, "999"),  # ignorado: ADM já repassou
            activity(CD, MAN, HOUR, "100"),
            activity(CD, REC, HOUR, "100"),
            activity(CD, PICK, HOUR, "200"),
        ],
        {},
        [
            rule(1, HOUR, priority=10, source_process_ids=frozenset({ADM})),
            rule(2, HOUR, priority=20, source_process_ids=frozenset({MAN})),
        ],
        DEFAULT_DRIVERS,
    )
    rows = by_target(result)
    # ADM: 1000 por 100/100/200 h -> MAN 250, REC 250, PICK 500.
    # MAN: 500 + 250 = 750 por 100/200 h -> REC 250, PICK 500.
    assert rows[(CD, ADM)].total_cost == D(0)
    assert rows[(CD, MAN)].total_cost == D(0)
    assert rows[(CD, REC)].transferred_cost == D(500)
    assert rows[(CD, PICK)].transferred_cost == D(1000)
    assert result.composition["transferred"] == D(1750)


def test_cascata_sem_volume_mantem_custo_na_origem():
    result = calculate_month(
        SEP,
        [expense(1, "1000", process=ADM)],
        [activity(CD, REC, PALLET, "10")],
        {},
        [rule(2, HOUR, source_process_ids=frozenset({ADM}))],
        DEFAULT_DRIVERS,
    )
    adm = by_target(result)[(CD, ADM)]
    assert adm.total_cost == D(1000)
    assert RowAlert.NO_DRIVER in adm.alerts
    assert [i.code for i in result.issues] == [IssueCode.CASCADE_NOT_TRANSFERRED]
    assert result.composition["pending"] == D(0)


def test_regra_de_cascata_nao_rateia_despesa_compartilhada():
    cascade = rule(2, HOUR, source_process_ids=frozenset({ADM}))
    assert pick_rule(expense(1, "100", nature="shared", process=None), [cascade]) is None
