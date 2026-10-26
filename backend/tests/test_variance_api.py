from decimal import Decimal as D

from tests.test_calculations_api import import_csv, run
from tests.test_dashboard_api import decimals

BASE = {"base_from": "2026-08-01", "base_to": "2026-08-31"}
SEP = {"from": "2026-09-01", "to": "2026-09-30"}


def load_two_months(client):
    """Agosto é a base; setembro é o período analisado. Valores conferidos à mão."""
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-08-31,CD-DEMO-01,REC,6101,100000.00,direct,E-1\n"
        "2026-08-31,CD-DEMO-01,PICK,6103,50000.00,direct,E-2\n"
        "2026-09-30,CD-DEMO-01,REC,6101,132000.00,direct,E-3\n"
        "2026-09-30,CD-DEMO-01,PICK,6103,52000.00,direct,E-4\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-08-31,CD-DEMO-01,REC,pallet_received,10000,pallet,A-1\n"
        "2026-09-30,CD-DEMO-01,REC,pallet_received,12000,pallet,A-2\n"
        "2026-09-30,CD-DEMO-01,PICK,order_picked,4000,order,A-3\n",
        "activities",
    )
    assert run(client, "2026-08-01", "2026-09-30").status_code == 201


def variance(client, **params):
    response = client.get("/api/v1/dashboard/variance", params={**BASE, **SEP, **params})
    assert response.status_code == 200, response.text
    body = response.json()
    return {**decimals(body), "alerts": body["alerts"]}


def test_decompoe_volume_e_eficiencia(client):
    load_two_months(client)
    body = variance(client)
    items = {i["process_code"]: i for i in body["items"]}

    # REC: custo unitário base 10,00; 12.000 paletes deveriam custar 120.000.
    rec = items["REC"]
    assert rec["comparable"] is True
    assert rec["driver_uom"] == "pallet"
    assert rec["base_unit_cost"] == D("10")
    assert rec["actual_unit_cost"] == D("11")
    assert rec["expected_cost"] == D("120000")
    assert rec["volume_effect"] == D("20000")
    assert rec["efficiency_effect"] == D("12000")
    assert rec["total_change"] == D("32000")

    # PICK não tinha volume em agosto: a variação não é decomposta.
    pick = items["PICK"]
    assert pick["comparable"] is False
    assert pick["reason"] == "NO_BASE_VOLUME"
    assert pick["volume_effect"] is None
    assert pick["total_change"] == D("2000")

    assert body["base_cost"] == D("150000")
    assert body["actual_cost"] == D("184000")
    assert body["total_change"] == D("34000")
    assert body["volume_effect"] == D("20000")
    assert body["efficiency_effect"] == D("12000")
    assert body["not_comparable"] == D("2000")
    assert {a["code"] for a in body["alerts"]} == {"NOT_COMPARABLE"}


def test_partes_somam_a_variacao_mesmo_com_dizima(client):
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-08-31,CD-DEMO-01,ARM,6102,100000.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,ARM,6102,100000.00,direct,E-2\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-08-31,CD-DEMO-01,ARM,position_day,3000,position_day,A-1\n"
        "2026-09-30,CD-DEMO-01,ARM,position_day,3001,position_day,A-2\n",
        "activities",
    )
    run(client, "2026-08-01", "2026-09-30")
    arm = variance(client)["items"][0]
    # 3001 x 33,333... = 100.033,33: volume +33,33 e eficiência -33,33.
    assert arm["volume_effect"] == D("33.33")
    assert arm["efficiency_effect"] == D("-33.33")
    assert arm["volume_effect"] + arm["efficiency_effect"] == arm["total_change"] == D("0")


def test_filtro_de_processo_e_periodo_base_sem_calculo(client):
    load_two_months(client)
    processes = {p["code"]: p["id"] for p in client.get("/api/v1/dimensions").json()["processes"]}
    body = variance(client, process_id=processes["REC"])
    assert [i["process_code"] for i in body["items"]] == ["REC"]
    assert body["not_comparable"] == D("0")

    body = variance(client, base_from="2026-07-01", base_to="2026-07-31")
    missing = [a for a in body["alerts"] if a["code"] == "MISSING_BASE_CALCULATION"]
    assert missing and missing[0]["months"] == ["2026-07-01"]
    assert body["base_cost"] == D("0")


def test_periodo_base_invalido(client):
    response = client.get(
        "/api/v1/dashboard/variance",
        params={**SEP, "base_from": "2026-08-31", "base_to": "2026-08-01"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PERIOD"
