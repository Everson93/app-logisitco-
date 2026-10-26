from decimal import Decimal

from sqlalchemy import select

from app.models import AuditLog
from tests.test_imports_api import SAMPLE, full_import, upload


def import_csv(client, filename, content: str, file_type: str):
    preview = upload(client, filename, content.encode(), file_type).json()
    batch_id = preview["batch"]["id"]
    validation = client.post(
        f"/api/v1/imports/{batch_id}/validate", json={"mapping": preview["suggested_mapping"]}
    ).json()
    assert validation["issues_total"] == 0, validation["issues"]
    assert client.post(f"/api/v1/imports/{batch_id}/commit").status_code == 200


def load_spec_example(client):
    """Seções 5.3 e 5.9: valores conferidos à mão."""
    import_csv(
        client,
        "despesas.csv",
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,6101,180000.00,direct,E-1\n"
        "2026-09-30,CD-DEMO-01,,6199,10000.00,shared,E-2\n"
        "2026-09-30,CD-DEMO-01,REC,6101,999.00,excluded,E-3\n",
        "expenses",
    )
    import_csv(
        client,
        "atividades.csv",
        "activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key\n"
        "2026-09-30,CD-DEMO-01,REC,pallet_received,15000,pallet,A-1\n"
        "2026-09-30,LOJA-DEMO-01,REC,pallet_received,2000,pallet,A-2\n"
        "2026-09-30,LOJA-DEMO-02,REC,pallet_received,3000,pallet,A-3\n",
        "activities",
    )
    import_csv(
        client,
        "orcamento.csv",
        "period_start,period_end,unit_code,process_code,account_code,amount\n"
        "2026-09-01,2026-09-30,CD-DEMO-01,REC,6101,165000.00\n",
        "budgets",
    )


def create_rule(client, **overrides):
    body = {
        "name": "Compartilhados do CD por paletes recebidos",
        "driver_code": "pallet_received",
        "valid_from": "2026-01-01",
        "scope": {"source_unit_codes": ["CD-DEMO-01"], "target_process_codes": ["REC"]},
        **overrides,
    }
    return client.post("/api/v1/allocation-rules", json=body)


def run(client, start="2026-09-01", end="2026-09-30"):
    return client.post("/api/v1/calculations/run", json={"period_start": start, "period_end": end})


def dims(client):
    data = client.get("/api/v1/dimensions").json()
    return (
        {u["code"]: u["id"] for u in data["units"]},
        {p["code"]: p["id"] for p in data["processes"]},
    )


def test_sem_regra_custo_compartilhado_fica_pendente(client):
    load_spec_example(client)
    response = run(client)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed_with_pending"
    assert body["summary"]["pending"] == "10000.00"
    assert body["summary"]["excluded"] == "999.00"
    issues = client.get(f"/api/v1/calculations/{body['id']}/issues").json()
    assert [i["code"] for i in issues] == ["NO_ALLOCATION_RULE"]
    assert Decimal(issues[0]["amount"]) == Decimal(10000)


def test_execucao_completa_confere_com_calculo_manual(client, db_session):
    load_spec_example(client)
    assert create_rule(client).status_code == 201
    body = run(client).json()
    assert body["status"] == "completed"
    assert body["rule_version"].startswith("calc-v1:")

    units, processes = dims(client)
    results = {
        (r["unit_id"], r["process_id"]): r
        for r in client.get(f"/api/v1/calculations/{body['id']}/results").json()
    }
    cd = results[(units["CD-DEMO-01"], processes["REC"])]
    # 10.000 rateados por 15.000 / 2.000 / 3.000 paletes = 75% / 10% / 15%.
    assert Decimal(cd["direct_cost"]) == Decimal("180000.00")
    assert Decimal(cd["allocated_cost"]) == Decimal("7500.00")
    assert Decimal(cd["total_cost"]) == Decimal("187500.00")
    assert Decimal(cd["unit_cost"]) == Decimal("12.5")
    assert Decimal(cd["variance_amount"]) == Decimal("22500.00")
    assert round(Decimal(cd["variance_percent"]), 2) == Decimal("13.64")
    assert "OVER_BUDGET" in cd["alerts"]

    loja1 = results[(units["LOJA-DEMO-01"], processes["REC"])]
    loja2 = results[(units["LOJA-DEMO-02"], processes["REC"])]
    assert Decimal(loja1["allocated_cost"]) == Decimal("1000.00")
    assert Decimal(loja2["allocated_cost"]) == Decimal("1500.00")
    assert Decimal(loja1["unit_cost"]) == Decimal("0.5")
    assert "MISSING_BUDGET" in loja1["alerts"]

    allocations = client.get(f"/api/v1/calculations/{body['id']}/allocations").json()
    assert sum(Decimal(a["allocated_amount"]) for a in allocations) == Decimal("10000.00")

    with db_session() as db:
        actions = list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)))
    assert actions == [
        "import.commit",
        "import.commit",
        "import.commit",
        "allocation_rule.create",
        "calculation.run",
    ]


def test_recalcular_cria_nova_execucao_e_preserva_historico(client):
    load_spec_example(client)
    first = run(client).json()
    rule = create_rule(client).json()
    second = run(client).json()
    assert second["id"] != first["id"]
    assert second["rule_version"] != first["rule_version"]

    runs = {r["id"]: r for r in client.get("/api/v1/calculations").json()["items"]}
    assert runs[first["id"]]["status"] == "superseded"
    assert runs[second["id"]]["status"] == "completed"
    # O histórico da primeira execução continua consultável.
    assert client.get(f"/api/v1/calculations/{first['id']}/issues").json()

    # Desativar a regra muda a versão e volta a deixar o custo pendente.
    client.patch(f"/api/v1/allocation-rules/{rule['id']}", json={"active": False})
    third = run(client).json()
    assert third["status"] == "completed_with_pending"
    assert third["rule_version"] == first["rule_version"]


def test_periodo_precisa_ser_de_meses_inteiros(client):
    response = run(client, start="2026-09-15", end="2026-09-20")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_PERIOD"
    assert {d["code"] for d in error["details"]} == {
        "MUST_BE_FIRST_DAY_OF_MONTH",
        "MUST_BE_LAST_DAY_OF_MONTH",
    }
    assert run(client, start="2026-09-01", end="2026-08-31").status_code == 422


def test_dados_de_demonstracao_em_tres_meses(client):
    for name, file_type in (
        ("despesas_demo.csv", "expenses"),
        ("atividades_demo.csv", "activities"),
        ("orcamento_demo.csv", "budgets"),
    ):
        full_import(client, SAMPLE / name, file_type)
    create_rule(client, scope={"source_unit_codes": ["CD-DEMO-01"]})
    body = run(client, "2026-07-01", "2026-09-30").json()
    assert body["status"] == "completed"
    assert body["summary"]["months"] == 3
    assert body["summary"]["allocated"] == "90000.00"  # 3 x R$ 30.000
    results = client.get(f"/api/v1/calculations/{body['id']}/results").json()
    assert {r["period_start"] for r in results} == {"2026-07-01", "2026-08-01", "2026-09-01"}


def test_validacao_e_conflito_de_regras(client):
    response = create_rule(
        client,
        driver_code="nao_existe",
        valid_to="2025-01-01",
        scope={"target_unit_codes": ["X"]},
    )
    assert response.status_code == 422
    codes = {(d["field"], d["code"]) for d in response.json()["error"]["details"]}
    assert codes == {
        ("driver_code", "UNKNOWN_DRIVER"),
        ("valid_to", "BEFORE_VALID_FROM"),
        ("scope.target_unit_codes", "UNKNOWN_CODE"),
    }

    first = create_rule(client, priority=10).json()
    second = create_rule(client, name="Outra", priority=10).json()
    assert second["conflicts_with"] == [first["id"]]
    other_scope = create_rule(
        client, name="Loja", priority=10, scope={"source_unit_codes": ["LOJA-DEMO-01"]}
    ).json()
    assert other_scope["conflicts_with"] == []

    updated = client.patch(
        f"/api/v1/allocation-rules/{second['id']}", json={"priority": 20, "name": None}
    ).json()
    assert updated["priority"] == 20
    assert updated["name"] == "Outra"
    assert updated["conflicts_with"] == []
    assert client.get("/api/v1/allocation-rules/999").status_code == 404
