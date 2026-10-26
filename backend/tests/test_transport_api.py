from decimal import Decimal as D

from tests.test_calculations_api import dims, import_csv, run
from tests.test_dashboard_api import decimals

SEP = {"from": "2026-09-01", "to": "2026-09-30"}


def load(client, capacity="2500"):
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,CD-DEMO-01,TRANS,6105,30000.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,TRANS,6106,10000.00,direct,E-2\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-09-30,CD-DEMO-01,TRANS,trip,100,trip,A-1\n"
        "2026-09-30,CD-DEMO-01,TRANS,km,8000,km,A-2\n"
        "2026-09-30,CD-DEMO-01,TRANS,pallet_transported,2000,pallet,A-3\n"
        f"2026-09-30,CD-DEMO-01,TRANS,pallet_capacity,{capacity},pallet,A-4\n",
        "activities",
    )
    assert run(client).status_code == 201


def transport(client, **params):
    response = client.get("/api/v1/dashboard/transport", params={**SEP, **params})
    assert response.status_code == 200, response.text
    body = response.json()
    return {**decimals(body), "alerts": body["alerts"]}


def test_indicadores_de_transporte_conferidos_a_mao(client):
    load(client)
    body = transport(client)
    assert body["total_cost"] == D("40000")
    assert body["own_fleet_cost"] == D("10000")
    assert body["third_party_cost"] == D("30000")
    assert body["other_direct_cost"] == D("0")
    assert body["cost_per_trip"] == D("400")
    assert body["cost_per_km"] == D("5")
    assert body["cost_per_pallet"] == D("20")
    assert body["km_per_trip"] == D("80")
    assert body["occupancy_percent"] == D("80")
    assert body["alerts"] == []
    assert body["months"][0]["calculated"] is True


def test_mes_sem_calculo_e_unidade_sem_dados(client):
    load(client)
    body = transport(client, **{"from": "2026-08-01"})
    assert [m["calculated"] for m in body["months"]] == [False, True]
    assert {a["code"] for a in body["alerts"]} == {"MISSING_CALCULATION"}
    # Os totais só somam meses calculados.
    assert body["total_cost"] == D("40000")

    units, _ = dims(client)
    body = transport(client, unit_id=units["LOJA-DEMO-01"])
    assert body["total_cost"] == D("0")
    assert body["cost_per_km"] is None and body["occupancy_percent"] is None
    assert {"NO_KM", "NO_PALLETS", "NO_CAPACITY"} <= {a["code"] for a in body["alerts"]}


def test_ocupacao_acima_da_capacidade_vira_alerta(client):
    load(client, capacity="1800")
    body = transport(client)
    assert body["occupancy_percent"] == D("111.11")
    assert "OCCUPANCY_OVER_100" in {a["code"] for a in body["alerts"]}
