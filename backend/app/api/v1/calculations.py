from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.calculations import (
    AllocationOut,
    CalculationIssueOut,
    CostResultOut,
    RunIn,
    RunOut,
    RunPage,
)
from app.services import calculation_service as service

router = APIRouter(prefix="/calculations", tags=["calculations"])

Db = Annotated[Session, Depends(get_db)]

# Usuário fixo até a autenticação real (seção 3).
DEMO_USER = "demo"


@router.post("/run", response_model=RunOut, status_code=201)
def run(db: Db, body: RunIn) -> RunOut:
    """Calcula todos os meses do período. Filtros por unidade/processo ficam nas consultas,
    porque o rateio depende do volume de todas as unidades elegíveis."""
    return RunOut.model_validate(
        service.run_calculation(
            db, period_start=body.period_start, period_end=body.period_end, actor=DEMO_USER
        )
    )


@router.get("", response_model=RunPage)
def list_runs(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RunPage:
    items, total = service.list_runs(db, page=page, page_size=page_size)
    return RunPage(
        items=[RunOut.model_validate(r) for r in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(db: Db, run_id: int) -> RunOut:
    return RunOut.model_validate(service.get_run(db, run_id))


@router.get("/{run_id}/results", response_model=list[CostResultOut])
def results(db: Db, run_id: int) -> list[CostResultOut]:
    return [CostResultOut.model_validate(r) for r in service.run_results(db, run_id)]


@router.get("/{run_id}/allocations", response_model=list[AllocationOut])
def allocations(db: Db, run_id: int) -> list[AllocationOut]:
    return [AllocationOut.model_validate(a) for a in service.run_allocations(db, run_id)]


@router.get("/{run_id}/issues", response_model=list[CalculationIssueOut])
def issues(db: Db, run_id: int) -> list[CalculationIssueOut]:
    return [CalculationIssueOut.model_validate(i) for i in service.run_issues(db, run_id)]
