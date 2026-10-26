import csv
import io
from decimal import Decimal as D

from tests.test_calculations_api import create_rule, dims, load_spec_example, run
from tests.test_imports_api import SAMPLE, full_import

SEP = {"from": "2026-09-01", "to": "2026-09-30"}


def decimals(value):
    """Valores monetários chegam como texto decimal; converte para comparar sem float."""
    if isinstance(value, dict):
        return {k: decimals(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decimals(v) for v in value]
    if isinstance(value, str):
        try:
            return D(value)
        except ArithmeticError:
            return value
    return value


def summary(client, **params):
    response = client.get("/api/v1/dashboard/summary", params={**SEP, **params})
    assert response.status_code == 200, response.text
    body = response.json()
    return {**decimals(body), "alerts": body["alerts"], "period": body["period"]}


def codes(body):
    return {a["code"] for a in body["alerts"]}


def test_resumo_do_exemplo_da_especificacao(client):
    load_spec_example(client)
    create_rule(client)
    run(client)
    units, processes = dims(client)

    cd = summary(client, unit_id=units["CD-DEMO-01"], process_id=processes["REC"])
    assert cd["currency"] == "BRL"
    assert cd["actual_cost"] == D("187500.0")
    assert cd["budget_cost"] == D("165000.0")
    assert cd["variance_amount"] == D("22500.0")
    assert cd["variance_percent"] == D("13.64")
    assert cd["driver_quantity"] == D("15000.0")
    assert cd["driver_uom"] == "pallet"
    assert cd["unit_cost"] == D("12.5")
    assert cd["composition"] == {
        "direct": D("180000.0"),
        "allocated": D("7500.0"),
        "transferred": D("0"),
        "excluded": D("999.0"),
        "pending": D("0.0"),
    }
    assert "OVER_BUDGET" in codes(cd)

    # Toda a operação: um só direcionador (REC), então o unitário ainda pode ser somado.
    everything = summary(client)
    assert everything["actual_cost"] == D("190000.0")
    assert everything["driver_quantity"] == D("20000.0")
    assert everything["unit_cost"] == D("9.5")


def test_custo_unitario_nao_mistura_direcionadores(client):
    for name, file_type in (
        ("despesas_demo.csv", "expenses"),
        ("atividades_demo.csv", "activities"),
        ("orcamento_demo.csv", "budgets"),
    ):
        full_import(client, SAMPLE / name, file_type)
    create_rule(client, scope={"source_unit_codes": ["CD-DEMO-01"]})
    run(client, "2026-07-01", "2026-09-30")
    body = summary(client)
    assert body["unit_cost"] is None
    assert body["driver_quantity"] is None
    assert "MIXED_DRIVERS" in codes(body)

    _, processes = dims(client)
    pick = summary(client, process_id=processes["PICK"])
    assert pick["driver_uom"] == "order"
    assert pick["unit_cost"] is not None


def test_mes_sem_calculo_e_pendencias_viram_alerta(client):
    load_spec_example(client)
    run(client)  # sem regra: R$ 10.000 pendentes
    body = summary(client, **{"from": "2026-08-01", "to": "2026-09-30"})
    assert {"MISSING_CALCULATION", "PENDING_COSTS"} <= codes(body)
    missing = next(a for a in body["alerts"] if a["code"] == "MISSING_CALCULATION")
    assert missing["months"] == ["2026-08-01"]
    assert body["composition"]["pending"] == D("10000.0")


def test_tendencia_e_por_processo(client):
    load_spec_example(client)
    create_rule(client)
    run(client)
    points = client.get(
        "/api/v1/dashboard/trend", params={"from": "2026-08-01", "to": "2026-09-30"}
    ).json()
    assert points[0] == {"period": "2026-08-01", "calculated": False}
    assert points[1]["calculated"] is True
    assert D(points[1]["actual_cost"]) == D("190000.0")

    items = client.get("/api/v1/dashboard/by-process", params=SEP).json()
    assert [i["process_code"] for i in items] == ["REC"]
    assert D(items[0]["budget_cost"]) == D("165000.0")


def test_recalcular_um_mes_nao_esconde_os_outros(client):
    for name, file_type in (
        ("despesas_demo.csv", "expenses"),
        ("atividades_demo.csv", "activities"),
        ("orcamento_demo.csv", "budgets"),
    ):
        full_import(client, SAMPLE / name, file_type)
    first = run(client, "2026-07-01", "2026-09-30").json()
    create_rule(client, scope={"source_unit_codes": ["CD-DEMO-01"]})
    second = run(client).json()  # só setembro, agora com regra

    runs = {r["id"]: r["status"] for r in client.get("/api/v1/calculations").json()["items"]}
    assert runs[first["id"]] == "completed_with_pending"  # julho e agosto seguem valendo
    body = summary(client, **{"from": "2026-07-01", "to": "2026-09-30"})
    assert body["calculation_run_ids"] == [first["id"], second["id"]]
    assert body["composition"]["pending"] == D("60000.0")  # julho e agosto sem regra
    assert body["composition"]["allocated"] == D("30000.0")  # setembro rateado

    # Uma execução que cobre todo o período substitui as anteriores.
    third = run(client, "2026-07-01", "2026-09-30").json()
    runs = {r["id"]: r["status"] for r in client.get("/api/v1/calculations").json()["items"]}
    assert runs[first["id"]] == runs[second["id"]] == "superseded"
    assert summary(client, **{"from": "2026-07-01", "to": "2026-09-30"})["calculation_run_ids"] == [
        third["id"]
    ]


def test_filtros_invalidos(client):
    response = client.get(
        "/api/v1/dashboard/summary", params={"from": "2026-09-30", "to": "2026-09-01"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PERIOD"
    assert client.get("/api/v1/dashboard/summary").status_code == 422


def test_exportacao_csv_respeita_filtros(client):
    load_spec_example(client)
    create_rule(client)
    run(client)
    units, _ = dims(client)

    response = client.get(
        "/api/v1/reports/costs.csv", params={**SEP, "unit_id": units["LOJA-DEMO-01"]}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "custos_202609_202609.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))
    assert len(rows) == 1
    assert rows[0]["unidade_codigo"] == "LOJA-DEMO-01"
    assert rows[0]["periodo"] == "2026-09"
    assert rows[0]["moeda"] == "BRL"
    assert rows[0]["custo_rateado"] == "1000,00"

    intl = client.get("/api/v1/reports/costs.csv", params={**SEP, "format": "intl"})
    rows = list(csv.DictReader(io.StringIO(intl.content.decode("utf-8-sig"))))
    assert len(rows) == 3
    assert {r["custo_total"] for r in rows} >= {"187500.00"}
