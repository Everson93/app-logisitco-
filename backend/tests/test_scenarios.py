from datetime import date
from decimal import Decimal as D

from sqlalchemy import func, select

from app.models import CalculationRun
from app.services.calculation_engine import ActivityFact, ExpenseFact, RuleSpec
from app.services.scenarios import Scenario, apply_scenario
from tests.test_calculations_api import create_rule, import_csv
from tests.test_dashboard_api import decimals

SEP = {"period_start": "2026-09-01", "period_end": "2026-09-30"}


def test_apply_scenario_altera_volume_custo_variavel_e_direcionador():
    day = date(2026, 9, 30)
    expenses = [
        ExpenseFact(1, day, 1, 10, None, D("1000.00"), "direct"),
        ExpenseFact(2, day, 1, 20, None, D("500.00"), "direct"),
        ExpenseFact(3, day, 1, None, None, D("300.00"), "shared"),
    ]
    activities = [ActivityFact(1, 10, 7, D("100")), ActivityFact(1, 20, 8, D("50"))]
    rules = [
        RuleSpec(id=1, driver_id=7, valid_from=day, valid_to=None, priority=100),
        RuleSpec(
            id=2,
            driver_id=9,
            valid_from=day,
            valid_to=None,
            priority=100,
            source_process_ids=frozenset({30}),
        ),
    ]

    scenario = Scenario(
        volume_change={10: D("10")}, variable_share=D("0.6"), allocation_driver_id=8
    )
    new_expenses, new_activities, new_rules = apply_scenario(scenario, expenses, activities, rules)

    assert [e.amount for e in new_expenses] == [D("1060.00"), D("500.00"), D("300.00")]
    assert [a.quantity for a in new_activities] == [D("110"), D("50")]
    assert new_rules[0].driver_id == 8
    assert new_rules[1].driver_id == 9  # a cascata mantém o próprio direcionador
    # As entradas originais não mudam.
    assert expenses[0].amount == D("1000.00") and rules[0].driver_id == 7


def load(client):
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,6101,100000.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,PICK,6103,50000.00,direct,E-2\n"
        "2026-09-30,CD-DEMO-01,,6199,10000.00,shared,E-3\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,pallet_received,10000,pallet,A-1\n"
        "2026-09-30,CD-DEMO-01,PICK,order_picked,5000,order,A-2\n",
        "activities",
    )
    assert create_rule(client, scope={"source_unit_codes": ["CD-DEMO-01"]}).status_code == 201


def simulate(client, **body):
    response = client.post("/api/v1/scenarios/simulate", json={**SEP, **body})
    assert response.status_code == 200, response.text
    data = response.json()
    return {**decimals(data), "alerts": data["alerts"]}


def by_code(body):
    return {i["process_code"]: i for i in body["items"]}


def test_volume_maior_com_custo_parcialmente_variavel(client, db_session):
    load(client)
    body = simulate(
        client,
        volume_changes=[{"process_code": "REC", "percent": "20"}],
        variable_cost_share="0.5",
    )
    rec = by_code(body)["REC"]
    # Direto 100.000 sobe 10% (20% x 0,5); o rateio de 10.000 continua no REC.
    assert rec["base_cost"] == D("110000")
    assert rec["scenario_cost"] == D("120000")
    assert rec["base_volume"] == D("10000") and rec["scenario_volume"] == D("12000")
    assert rec["base_unit_cost"] == D("11") and rec["scenario_unit_cost"] == D("10")
    assert rec["change_percent"] == D("9.09")
    assert by_code(body)["PICK"]["change"] == D("0")
    assert body["base_cost"] == D("160000") and body["change"] == D("10000")
    assert body["alerts"] == []

    # Simular não cria execução de cálculo.
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(CalculationRun)) == 0


def test_trocar_direcionador_do_rateio(client):
    load(client)
    body = simulate(client, allocation_driver_code="order_picked")
    items = by_code(body)
    assert items["REC"]["scenario_cost"] == D("100000")
    assert items["PICK"]["scenario_cost"] == D("60000")
    assert body["change"] == D("0")

    # Direcionador sem volume: o compartilhado fica pendente e o cenário avisa.
    body = simulate(client, allocation_driver_code="trip")
    assert body["scenario_pending"] == D("10000")
    assert body["scenario_cost"] == D("150000")
    assert [a["code"] for a in body["alerts"]] == ["SCENARIO_PENDING"]


def test_cenario_invalido(client):
    response = client.post(
        "/api/v1/scenarios/simulate",
        json={**SEP, "volume_changes": [{"process_code": "XYZ", "percent": 5}]},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_SCENARIO"
    assert error["details"][0]["code"] == "UNKNOWN_PROCESS"

    response = client.post(
        "/api/v1/scenarios/simulate",
        json={**SEP, "volume_changes": [{"process_code": "REC", "percent": -150}]},
    )
    assert response.status_code == 422

    response = client.post("/api/v1/scenarios/simulate", json={**SEP, "period_start": "2026-09-15"})
    assert response.json()["error"]["code"] == "INVALID_PERIOD"
