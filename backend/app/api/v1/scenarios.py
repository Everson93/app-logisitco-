from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.calculations import ScenarioIn
from app.services import scenarios as service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

Db = Annotated[Session, Depends(get_db)]


@router.post("/simulate")
def simulate(db: Db, body: ScenarioIn) -> dict:
    """Recalcula o período com volume, custo variável e direcionador alterados, sem gravar."""
    scenario = service.resolve(
        db,
        {c.process_code: c.percent for c in body.volume_changes},
        body.variable_cost_share,
        body.allocation_driver_code,
    )
    return service.simulate(db, body.period_start, body.period_end, scenario)
