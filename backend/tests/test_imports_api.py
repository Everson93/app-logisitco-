from pathlib import Path

from sqlalchemy import func, select

from app.models import Activity, Budget, Expense, ImportStagingRow

SAMPLE = Path(__file__).resolve().parents[2] / "sample-data"

EXPENSE_FIELDS = (
    "competence_date",
    "unit_code",
    "process_code",
    "account_code",
    "description",
    "amount",
    "nature",
    "source_key",
)


def upload(client, filename, content: bytes, file_type="expenses"):
    return client.post(
        "/api/v1/imports/preview",
        files={"file": (filename, content, "text/csv")},
        data={"file_type": file_type},
    )


def full_import(client, path: Path, file_type: str):
    preview = upload(client, path.name, path.read_bytes(), file_type).json()
    batch_id = preview["batch"]["id"]
    validation = client.post(
        f"/api/v1/imports/{batch_id}/validate", json={"mapping": preview["suggested_mapping"]}
    )
    assert validation.status_code == 200, validation.text
    return batch_id, validation.json(), client.post(f"/api/v1/imports/{batch_id}/commit")


def count(db_session, model):
    with db_session() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_preview_nao_grava_fatos(client, db_session):
    path = SAMPLE / "despesas_demo.csv"
    response = upload(client, path.name, path.read_bytes())
    assert response.status_code == 201
    body = response.json()
    assert body["batch"]["status"] == "uploaded"
    assert body["batch"]["rows_total"] == 30
    assert len(body["rows"]) == 20
    assert set(body["suggested_mapping"]) == set(EXPENSE_FIELDS)
    assert count(db_session, Expense) == 0
    assert count(db_session, ImportStagingRow) == 30


def test_formato_nao_suportado(client):
    response = upload(client, "dados.xlsx", b"qualquer")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_tipo_de_arquivo_invalido(client):
    response = upload(client, "dados.csv", b"a\n1\n", file_type="outro")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_mapeamento_incompleto_e_recusado(client):
    path = SAMPLE / "despesas_demo.csv"
    preview = upload(client, path.name, path.read_bytes()).json()
    mapping = {k: v for k, v in preview["suggested_mapping"].items() if k != "amount"}
    response = client.post(
        f"/api/v1/imports/{preview['batch']['id']}/validate", json={"mapping": mapping}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MAPPING_INCOMPLETE"
    assert {"field": "amount", "code": "REQUIRED_FIELD_NOT_MAPPED"} in error["details"]


def test_commit_sem_validar_e_recusado(client):
    path = SAMPLE / "despesas_demo.csv"
    preview = upload(client, path.name, path.read_bytes()).json()
    response = client.post(f"/api/v1/imports/{preview['batch']['id']}/commit")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BATCH_NOT_READY"


def test_importacao_completa_e_reimportacao_nao_duplica(client, db_session):
    path = SAMPLE / "despesas_demo.csv"
    batch_id, validation, commit = full_import(client, path, "expenses")
    assert validation["batch"]["rows_valid"] == 30
    assert validation["issues_total"] == 0
    assert commit.status_code == 200
    assert commit.json()["status"] == "committed"
    assert commit.json()["rows_committed"] == 30
    assert count(db_session, Expense) == 30

    with db_session() as db:
        origins = set(db.scalars(select(Expense.source_batch_id)))
    assert origins == {batch_id}  # rastreável ao lote de origem (RF-012)

    # Mesmo arquivo de novo: a prévia avisa e nada é duplicado.
    preview = upload(client, path.name, path.read_bytes()).json()
    assert preview["warnings"]
    response = client.post(
        f"/api/v1/imports/{preview['batch']['id']}/validate",
        json={"mapping": preview["suggested_mapping"]},
    ).json()
    assert response["batch"]["rows_ignored"] == 30
    assert response["batch"]["status"] == "failed"  # nada novo para gravar
    assert {i["code"] for i in response["issues"]} == {"ALREADY_IMPORTED"}
    assert count(db_session, Expense) == 30


def test_casos_invalidos_mostram_linha_coluna_e_codigo(client, db_session):
    path = SAMPLE / "casos_invalidos" / "despesas_invalidas.csv"
    batch_id, validation, commit = full_import(client, path, "expenses")
    issues = {(i["row"], i["code"]) for i in validation["issues"]}
    assert (2, "MISSING_REQUIRED_FIELD") in issues
    assert (3, "INVALID_DATE") in issues
    assert (4, "UNKNOWN_UNIT") in issues
    assert (6, "DUPLICATE_SOURCE_KEY") in issues
    assert validation["batch"]["rows_rejected"] == 4
    assert validation["batch"]["rows_valid"] == 3

    # Somente as linhas válidas são gravadas.
    assert commit.json()["rows_committed"] == 3
    assert count(db_session, Expense) == 3

    errors = client.get(f"/api/v1/imports/{batch_id}/errors", params={"severity": "error"}).json()
    assert errors["total"] == 4
    assert errors["items"][0] == {
        "row": 2,
        "column": "amount",
        "code": "MISSING_REQUIRED_FIELD",
        "severity": "error",
        "message": "Campo obrigatório 'amount' está vazio.",
    }


def test_atividades_e_orcamento(client, db_session):
    _, _, commit = full_import(client, SAMPLE / "atividades_demo.csv", "activities")
    assert commit.json()["rows_committed"] == 27
    _, _, commit = full_import(client, SAMPLE / "orcamento_demo.csv", "budgets")
    assert commit.json()["rows_committed"] == 27
    assert count(db_session, Activity) == 27
    assert count(db_session, Budget) == 27

    # Reimportar orçamento não duplica (chave de período + dimensão).
    _, validation, _ = full_import(client, SAMPLE / "orcamento_demo.csv", "budgets")
    assert validation["batch"]["rows_ignored"] == 27
    assert count(db_session, Budget) == 27


def test_csv_brasileiro_com_valor_padrao(client, db_session):
    content = (
        "Data;Processo;Valor;Natureza;Documento\n"
        "30/09/2026;REC;1.234,56;direct;NF-1\n"
        "30/09/2026;PICK;R$ 10,00;direct;NF-2\n"
    ).encode("cp1252")
    preview = upload(client, "brasil.csv", content).json()
    mapping = preview["suggested_mapping"]
    assert mapping == {
        "competence_date": "Data",
        "process_code": "Processo",
        "amount": "Valor",
        "nature": "Natureza",
        "source_key": "Documento",
    }
    batch_id = preview["batch"]["id"]
    validation = client.post(
        f"/api/v1/imports/{batch_id}/validate",
        json={
            "mapping": mapping,
            "defaults": {"unit_code": "LOJA-DEMO-01"},
            "date_format": "dmy",
            "decimal_separator": ",",
        },
    ).json()
    assert validation["issues_total"] == 0
    client.post(f"/api/v1/imports/{batch_id}/commit")
    with db_session() as db:
        amounts = sorted(db.scalars(select(Expense.amount)))
    assert [str(a) for a in amounts] == ["10.00", "1234.56"]


def test_lote_confirmado_nao_pode_ser_revalidado(client):
    batch_id, validation, _ = full_import(client, SAMPLE / "despesas_demo.csv", "expenses")
    response = client.post(
        f"/api/v1/imports/{batch_id}/validate", json={"mapping": {"amount": "amount"}}
    )
    assert response.status_code == 409


def test_historico_de_lotes_e_dimensoes(client):
    full_import(client, SAMPLE / "despesas_demo.csv", "expenses")
    upload(client, "outro.csv", b"a,b\n1,2\n", "activities")
    page = client.get("/api/v1/imports", params={"page_size": 1}).json()
    assert page["total"] == 2
    assert page["items"][0]["filename"] == "outro.csv"
    committed = client.get("/api/v1/imports", params={"status": "committed"}).json()
    assert [b["filename"] for b in committed["items"]] == ["despesas_demo.csv"]
    assert client.get("/api/v1/imports/999").json()["error"]["code"] == "BATCH_NOT_FOUND"

    dims = client.get("/api/v1/dimensions").json()
    assert [u["code"] for u in dims["units"]] == ["CD-DEMO-01", "LOJA-DEMO-01", "LOJA-DEMO-02"]
    assert {d["code"]: d["unit_of_measure"] for d in dims["drivers"]}["trip"] == "trip"
