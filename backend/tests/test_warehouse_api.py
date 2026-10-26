from decimal import Decimal as D

from tests.test_calculations_api import create_rule, dims, import_csv, run
from tests.test_dashboard_api import decimals

SEP = {"from": "2026-09-01", "to": "2026-09-30"}


def load(client):
    """Setembro, valores conferidos à mão.

    REC: 20.000 direto + 10.000 rateado, 5.000 paletes e 400 horas.
    PICK: CD com 50.000, 5.000 pedidos, 1.000 horas e 15.000 linhas;
          loja com 10.000 e 1.000 pedidos, sem horas apontadas.
    ARM: 9.000 e 3.000 posições-dia, sem horas.
    """
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,6101,20000.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,,6199,10000.00,shared,E-2\n"
        "2026-09-30,CD-DEMO-01,PICK,6103,50000.00,direct,E-3\n"
        "2026-09-30,LOJA-DEMO-01,PICK,6103,10000.00,direct,E-4\n"
        "2026-09-30,CD-DEMO-01,ARM,6102,9000.00,direct,E-5\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,pallet_received,5000,pallet,A-1\n"
        "2026-09-30,CD-DEMO-01,REC,productive_hour,400,hour,A-2\n"
        "2026-09-30,CD-DEMO-01,PICK,order_picked,5000,order,A-3\n"
        "2026-09-30,CD-DEMO-01,PICK,productive_hour,1000,hour,A-4\n"
        "2026-09-30,CD-DEMO-01,PICK,line_picked,15000,line,A-5\n"
        "2026-09-30,LOJA-DEMO-01,PICK,order_picked,1000,order,A-6\n"
        "2026-09-30,CD-DEMO-01,ARM,position_day,3000,position_day,A-7\n",
        "activities",
    )
    assert create_rule(client).status_code == 201
    assert run(client).status_code == 201


def warehouse(client, **params):
    response = client.get("/api/v1/dashboard/warehouse", params={**SEP, **params})
    assert response.status_code == 200, response.text
    body = response.json()
    items = {i["process_code"]: decimals(i) for i in body["items"]}
    return items, body["alerts"]


def test_indicadores_de_armazem_conferidos_a_mao(client):
    load(client)
    items, alerts = warehouse(client)
    assert list(items) == ["REC", "ARM", "PICK"]

    rec = items["REC"]
    assert rec["unit_cost"] == D("6")
    assert rec["direct_unit_cost"] == D("4")
    assert rec["allocated_unit_cost"] == D("2")
    assert rec["productivity_per_hour"] == D("12.5")
    assert rec["cost_per_hour"] == D("75")
    assert rec["lines_per_hour"] is None

    # A loja entra no custo unitário, mas não na produtividade: ela não apontou horas.
    pick = items["PICK"]
    assert pick["total_cost"] == D("60000")
    assert pick["volume"] == D("6000")
    assert pick["unit_cost"] == D("10")
    assert pick["productive_hours"] == D("1000")
    assert pick["productivity_per_hour"] == D("5")
    assert pick["cost_per_hour"] == D("50")
    assert pick["lines"] == D("15000")
    assert pick["lines_per_hour"] == D("15")
    assert pick["lines_per_order"] == D("3")
    assert pick["months"][0]["calculated"] is True

    arm = items["ARM"]
    assert arm["unit_cost"] == D("3")
    assert arm["productivity_per_hour"] is None
    assert arm["cost_per_hour"] is None

    assert [a["code"] for a in alerts] == ["NO_PRODUCTIVE_HOURS"]
    assert "ARM" in alerts[0]["message"]


def test_filtros_de_unidade_e_processo(client):
    load(client)
    units, processes = dims(client)
    items, _ = warehouse(client, unit_id=units["LOJA-DEMO-01"])
    assert list(items) == ["PICK"]
    assert items["PICK"]["unit_cost"] == D("10")
    assert items["PICK"]["productive_hours"] is None

    items, alerts = warehouse(client, process_id=processes["PICK"])
    assert list(items) == ["PICK"]
    assert alerts == []

    # TRANS não é processo de armazém.
    items, _ = warehouse(client, process_id=processes["TRANS"])
    assert items == {}


def test_mes_sem_calculo(client):
    load(client)
    response = client.get(
        "/api/v1/dashboard/warehouse", params={"from": "2026-08-01", "to": "2026-09-30"}
    )
    body = response.json()
    missing = [a for a in body["alerts"] if a["code"] == "MISSING_CALCULATION"]
    assert missing and missing[0]["months"] == ["2026-08-01"]
    pick = next(i for i in body["items"] if i["process_code"] == "PICK")
    assert [(m["period"], m["calculated"]) for m in pick["months"]] == [
        ("2026-08-01", False),
        ("2026-09-01", True),
    ]
