from sqlalchemy import select

from app.models import AuditLog
from tests.test_calculations_api import create_rule
from tests.test_imports_api import upload

API = "/api/v1/dimensions"


def by_code(client, kind):
    response = client.get(f"{API}/{kind}")
    assert response.status_code == 200, response.text
    return {item["code"]: item for item in response.json()}


def test_cria_e_altera_unidade_com_auditoria(client, db_session):
    response = client.post(
        f"{API}/units",
        json={"code": "LOJA-DEMO-03", "name": "Loja Demo Leste", "unit_type": "store"},
    )
    assert response.status_code == 201, response.text
    unit = response.json()
    assert unit["active"] is True

    response = client.patch(
        f"{API}/units/{unit['id']}", json={"name": "Loja Leste", "active": None}
    )
    assert response.json()["name"] == "Loja Leste"
    assert response.json()["active"] is True  # null não altera

    with db_session() as db:
        actions = db.scalars(
            select(AuditLog.action).where(AuditLog.entity_type == "unit").order_by(AuditLog.id)
        ).all()
    assert actions == ["dimension.create", "dimension.update"]


def test_codigo_repetido_e_campos_invalidos(client):
    response = client.post(f"{API}/units", json={"code": "CD-DEMO-01", "name": "Outro"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_CODE"

    response = client.post(f"{API}/units", json={"code": "X 1", "name": "x", "unit_type": "hub"})
    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert fields == {"code", "unit_type"}


def test_processo_resolve_direcionador_por_codigo(client):
    response = client.post(
        f"{API}/processes",
        json={"code": "INV", "name": "Inventário", "default_driver_code": "productive_hour"},
    )
    assert response.status_code == 201, response.text
    process = response.json()
    assert process["default_driver_code"] == "productive_hour"

    response = client.patch(
        f"{API}/processes/{process['id']}", json={"default_driver_code": "nao_existe"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "UNKNOWN_DRIVER"

    # null limpa o direcionador padrão.
    response = client.patch(f"{API}/processes/{process['id']}", json={"default_driver_code": None})
    assert response.json()["default_driver_code"] is None


def test_direcionador_em_uso_nao_pode_ser_desativado(client):
    drivers = by_code(client, "drivers")
    response = client.patch(
        f"{API}/drivers/{drivers['pallet_received']['id']}", json={"active": False}
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert {"field": "process", "value": "REC", "code": "DEFAULT_DRIVER"} in details

    # Sem processo nem regra, pode.
    response = client.patch(f"{API}/drivers/{drivers['line_picked']['id']}", json={"active": False})
    assert response.status_code == 200
    assert response.json()["active"] is False

    # Regra ativa também prende o direcionador.
    assert create_rule(client, driver_code="productive_hour").status_code == 201
    response = client.patch(
        f"{API}/drivers/{drivers['productive_hour']['id']}", json={"active": False}
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"][0]["code"] == "RULE_DRIVER"


def test_unidade_de_medida_e_codigo_nao_mudam(client):
    drivers = by_code(client, "drivers")
    response = client.patch(
        f"{API}/drivers/{drivers['km']['id']}", json={"unit_of_measure": "mile", "code": "mi"}
    )
    assert response.status_code == 200
    assert response.json()["unit_of_measure"] == "km"
    assert response.json()["code"] == "km"


def test_inativo_some_dos_filtros_e_da_importacao(client):
    units = by_code(client, "units")
    client.patch(f"{API}/units/{units['LOJA-DEMO-02']['id']}", json={"active": False})

    assert "LOJA-DEMO-02" not in {u["code"] for u in client.get(API).json()["units"]}
    assert by_code(client, "units")["LOJA-DEMO-02"]["active"] is False

    content = (
        "competence_date,unit_code,process_code,account_code,amount,nature,source_key\n"
        "2026-09-30,LOJA-DEMO-02,PICK,6103,100.00,direct,E-1\n"
    )
    preview = upload(client, "despesas.csv", content.encode(), "expenses").json()
    validation = client.post(
        f"/api/v1/imports/{preview['batch']['id']}/validate",
        json={"mapping": preview["suggested_mapping"]},
    ).json()
    assert [i["code"] for i in validation["issues"]] == ["UNKNOWN_UNIT"]

    # Centro de custo não aceita unidade inativa.
    response = client.post(
        f"{API}/cost-centers", json={"code": "CC-1", "name": "CC", "unit_code": "LOJA-DEMO-02"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "INACTIVE_UNIT"


def test_conta_e_404(client):
    response = client.post(
        f"{API}/accounts", json={"code": "6108", "name": "Pedágio", "cost_nature": "fleet_own"}
    )
    assert response.status_code == 201
    assert response.json()["cost_nature"] == "fleet_own"
    response = client.patch(f"{API}/accounts/999999", json={"name": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DIMENSION_NOT_FOUND"
