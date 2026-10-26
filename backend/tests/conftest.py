import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app

# Testes de integração usam um banco descartável: as tabelas são limpas a cada teste.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

TABLES = (
    "audit_logs, calculation_issues, allocation_results, cost_results, calculation_runs, "
    "allocation_rules, import_row_errors, import_staging_rows, expenses, activities, budgets, "
    "import_batches, "
    "processes, drivers, cost_centers, accounts, units"
)

DIMENSIONS_SQL = """
INSERT INTO units (code, name, unit_type) VALUES
  ('CD-DEMO-01', 'Centro de Distribuição Demo', 'distribution_center'),
  ('LOJA-DEMO-01', 'Loja Demo Norte', 'store'),
  ('LOJA-DEMO-02', 'Loja Demo Sul', 'store');
INSERT INTO drivers (code, name, unit_of_measure) VALUES
  ('pallet_received', 'Palete recebido', 'pallet'),
  ('position_day', 'Posição-dia', 'position_day'),
  ('order_picked', 'Pedido separado', 'order'),
  ('pallet_shipped', 'Palete expedido', 'pallet'),
  ('trip', 'Viagem', 'trip');
INSERT INTO processes (code, name, default_driver_id)
SELECT p.code, p.name, d.id FROM (VALUES
  ('REC', 'Recebimento', 'pallet_received'), ('ARM', 'Armazenagem', 'position_day'),
  ('PICK', 'Separação / picking', 'order_picked'), ('EXP', 'Expedição', 'pallet_shipped'),
  ('TRANS', 'Transporte', 'trip')
) AS p(code, name, driver) JOIN drivers d ON d.code = p.driver;
INSERT INTO accounts (code, name) VALUES
  ('6101', 'Mão de obra'), ('6102', 'Armazenagem'), ('6103', 'Separação'),
  ('6104', 'Expedição'), ('6105', 'Fretes'), ('6199', 'Compartilhados');
"""


@pytest.fixture(scope="session")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("defina TEST_DATABASE_URL para rodar os testes de integração")
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "alembic")
    )
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    from app.core.config import get_settings

    get_settings.cache_clear()
    command.upgrade(config, "head")
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Iterator[sessionmaker[Session]]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.execute(text(DIMENSIONS_SQL))
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(db_session) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
