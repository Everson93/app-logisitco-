from decimal import Decimal as D

from tests.test_calculations_api import create_rule, import_csv, run
from tests.test_dashboard_api import decimals

ADM_RULE = {
    "name": "ADM do CD por horas produtivas",
    "driver_code": "productive_hour",
    "scope": {"source_process_codes": ["ADM"], "target_unit_codes": ["CD-DEMO-01"]},
}


def load(client):
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,CD-DEMO-01,ADM,6101,1200.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,REC,6101,10000.00,direct,E-2\n"
        "2026-09-30,CD-DEMO-01,PICK,6103,20000.00,direct,E-3\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,pallet_received,1000,pallet,A-1\n"
        "2026-09-30,CD-DEMO-01,PICK,order_picked,2000,order,A-2\n"
        "2026-09-30,CD-DEMO-01,REC,productive_hour,100,hour,A-3\n"
        "2026-09-30,CD-DEMO-01,PICK,productive_hour,200,hour,A-4\n",
        "activities",
    )


def test_cascata_de_ponta_a_ponta(client):
    load(client)
    response = create_rule(client, **ADM_RULE)
    assert response.status_code == 201, response.text
    rule_id = response.json()["id"]
    body = run(client).json()
    assert body["status"] == "completed"
    assert body["summary"]["transferred"] == "1200.00"

    results = client.get(f"/api/v1/calculations/{body['id']}/results").json()
    processes = {p["id"]: p["code"] for p in client.get("/api/v1/dimensions").json()["processes"]}
    by_code = {processes[r["process_id"]]: decimals(r) for r in results}
    assert by_code["ADM"]["total_cost"] == D(0)
    assert by_code["ADM"]["transferred_cost"] == D(-1200)
    assert by_code["ADM"]["alerts"] == []
    assert by_code["REC"]["transferred_cost"] == D(400)
    assert by_code["REC"]["unit_cost"] == D("10.4")
    assert by_code["PICK"]["transferred_cost"] == D(800)

    allocations = client.get(f"/api/v1/calculations/{body['id']}/allocations").json()
    assert {(processes[a["source_process_id"]], a["rule_id"]) for a in allocations} == {
        ("ADM", rule_id)
    }
    assert all(a["expense_id"] is None for a in allocations)

    summary = decimals(
        client.get(
            "/api/v1/dashboard/summary", params={"from": "2026-09-01", "to": "2026-09-30"}
        ).json()
    )
    assert summary["actual_cost"] == D(31200)
    assert summary["composition"]["transferred"] == D(0)  # repasse dentro do recorte se anula

    csv = client.get(
        "/api/v1/reports/costs.csv", params={"from": "2026-09-01", "to": "2026-09-30"}
    ).text
    assert "custo_repassado" in csv.splitlines()[0]


def test_validacao_da_regra_de_cascata(client):
    response = create_rule(
        client,
        **{
            **ADM_RULE,
            "scope": {
                "source_process_codes": ["ADM"],
                "source_account_codes": ["6101"],
                "target_process_codes": ["ADM", "REC"],
            },
        },
    )
    assert response.status_code == 422
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert codes == {"NOT_ALLOWED_IN_CASCADE", "SOURCE_IS_TARGET"}


def test_cascata_nao_conflita_com_rateio_de_despesas(client):
    expense_rule = create_rule(client, priority=100).json()
    cascade = create_rule(client, priority=100, **ADM_RULE).json()
    assert expense_rule["conflicts_with"] == []
    assert cascade["conflicts_with"] == []
