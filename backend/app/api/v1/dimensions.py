from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.dimensions import list_dimensions

router = APIRouter(tags=["dimensions"])


@router.get("/dimensions")
def dimensions(db: Annotated[Session, Depends(get_db)]) -> dict[str, list]:
    """Unidades, processos, contas, centros de custo e direcionadores ativos."""
    return list_dimensions(db)
