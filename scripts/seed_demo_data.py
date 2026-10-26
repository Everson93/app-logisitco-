"""Carrega cadastros e dados fictícios de sample-data/ no banco.

Idempotente: pode rodar várias vezes sem duplicar registros (cadastros por
`code`, fatos por `source_key`, orçamento pela sua dimensão).
Não substitui a importação da Fase 1; serve só para ter dados de demonstração.

Uso (a partir de backend/, com o banco migrado):
    python ../scripts/seed_demo_data.py
"""

import csv
import hashlib
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Account,
    Activity,
    Budget,
    Driver,
    Expense,
    ImportBatch,
    Process,
    Unit,
)

SAMPLE = ROOT / "sample-data"

UNITS = [
    ("CD-DEMO-01", "Centro de Distribuição Demo", "distribution_center"),
    ("LOJA-DEMO-01", "Loja Demo Norte", "store"),
    ("LOJA-DEMO-02", "Loja Demo Sul", "store"),
]
DRIVERS = [
    ("pallet_received", "Palete recebido", "pallet"),
    ("position_day", "Posição-dia", "position_day"),
    ("order_picked", "Pedido separado", "order"),
    ("pallet_shipped", "Palete expedido", "pallet"),
    ("trip", "Viagem", "trip"),
]
PROCESSES = [
    ("REC", "Recebimento", "pallet_received"),
    ("ARM", "Armazenagem", "position_day"),
    ("PICK", "Separação / picking", "order_picked"),
    ("EXP", "Expedição", "pallet_shipped"),
    ("TRANS", "Transporte", "trip"),
]
ACCOUNTS = [
    ("6101", "Mão de obra operacional", "personnel"),
    ("6102", "Armazenagem", "facility"),
    ("6103", "Separação", "personnel"),
    ("6104", "Expedição", "personnel"),
    ("6105", "Fretes", "transport"),
    ("6199", "Custos compartilhados", "shared"),
]


def upsert_by_code(db: Session, model, rows: list[dict]) -> dict[str, int]:
    for row in rows:
        stmt = insert(model).values(**row).on_conflict_do_nothing(index_elements=["code"])
        db.execute(stmt)
    return {code: id_ for code, id_ in db.execute(select(model.code, model.id))}


def read_csv(name: str) -> tuple[list[dict], str]:
    path = SAMPLE / name
    content = path.read_bytes()
    rows = list(csv.DictReader(content.decode("utf-8").splitlines()))
    return rows, hashlib.sha256(content).hexdigest()


def new_batch(db: Session, filename: str, file_type: str, sha: str, total: int) -> int | None:
    """Registra o lote; retorna None se o mesmo arquivo já foi carregado."""
    already_loaded = select(ImportBatch.id).filter_by(file_sha256=sha, status="committed")
    if db.scalar(already_loaded) is not None:
        return None
    batch = ImportBatch(
        filename=filename,
        file_type=file_type,
        uploaded_by="seed",
        status="committed",
        rows_total=total,
        rows_valid=total,
        rows_rejected=0,
        file_sha256=sha,
    )
    db.add(batch)
    db.flush()
    return batch.id


def rows_to_load(rows: list[dict], batch_id: int | None) -> list[dict]:
    return rows if batch_id is not None else []


def main() -> None:
    with SessionLocal.begin() as db:
        units = upsert_by_code(
            db, Unit, [{"code": c, "name": n, "unit_type": t} for c, n, t in UNITS]
        )
        drivers = upsert_by_code(
            db, Driver, [{"code": c, "name": n, "unit_of_measure": u} for c, n, u in DRIVERS]
        )
        processes = upsert_by_code(
            db,
            Process,
            [{"code": c, "name": n, "default_driver_id": drivers[d]} for c, n, d in PROCESSES],
        )
        accounts = upsert_by_code(
            db, Account, [{"code": c, "name": n, "cost_nature": k} for c, n, k in ACCOUNTS]
        )

        rows, sha = read_csv("despesas_demo.csv")
        batch_id = new_batch(db, "despesas_demo.csv", "expenses", sha, len(rows))
        inserted_expenses = 0
        for r in rows_to_load(rows, batch_id):
            stmt = (
                insert(Expense)
                .values(
                    source_batch_id=batch_id,
                    competence_date=date.fromisoformat(r["competence_date"]),
                    unit_id=units.get(r["unit_code"]),
                    process_id=processes.get(r["process_code"]) if r["process_code"] else None,
                    account_id=accounts.get(r["account_code"]),
                    description=r["description"],
                    amount=Decimal(r["amount"]),
                    nature=r["nature"],
                    source_key=r["source_key"],
                )
                .on_conflict_do_nothing(index_elements=["source_key"])
                .returning(Expense.id)
            )
            inserted_expenses += db.execute(stmt).scalar() is not None

        rows, sha = read_csv("atividades_demo.csv")
        batch_id = new_batch(db, "atividades_demo.csv", "activities", sha, len(rows))
        inserted_activities = 0
        for r in rows_to_load(rows, batch_id):
            stmt = (
                insert(Activity)
                .values(
                    source_batch_id=batch_id,
                    activity_date=date.fromisoformat(r["activity_date"]),
                    unit_id=units[r["unit_code"]],
                    process_id=processes[r["process_code"]],
                    driver_id=drivers[r["driver_code"]],
                    quantity=Decimal(r["quantity"]),
                    unit_of_measure=r["unit_of_measure"],
                    source_key=r["source_key"],
                )
                .on_conflict_do_nothing(index_elements=["source_key"])
                .returning(Activity.id)
            )
            inserted_activities += db.execute(stmt).scalar() is not None

        rows, sha = read_csv("orcamento_demo.csv")
        batch_id = new_batch(db, "orcamento_demo.csv", "budgets", sha, len(rows))
        inserted_budgets = 0
        for r in rows_to_load(rows, batch_id):
            key = {
                "period_start": date.fromisoformat(r["period_start"]),
                "unit_id": units[r["unit_code"]],
                "process_id": processes[r["process_code"]],
                "account_id": accounts.get(r["account_code"]),
            }
            if db.scalar(select(Budget.id).filter_by(**key)) is not None:
                continue
            db.add(
                Budget(
                    **key,
                    source_batch_id=batch_id,
                    period_end=date.fromisoformat(r["period_end"]),
                    amount=Decimal(r["amount"]),
                )
            )
            inserted_budgets += 1

    print(
        f"Seed concluído: {inserted_expenses} despesas, {inserted_activities} atividades, "
        f"{inserted_budgets} linhas de orçamento inseridas."
    )


if __name__ == "__main__":
    main()
