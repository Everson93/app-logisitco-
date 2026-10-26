from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.dimensions import list_dimensions
from app.schemas import dimensions as schemas
from app.services import dimensions as service

router = APIRouter(tags=["dimensions"])

Db = Annotated[Session, Depends(get_db)]

# Usuário fixo até a autenticação real (seção 3).
DEMO_USER = "demo"

# Campos que aceitam null para limpar o valor; nos demais, null significa "não alterar".
CLEARABLE = {"default_driver_code", "cost_nature", "unit_code"}


@router.get("/dimensions")
def dimensions(db: Db) -> dict[str, list]:
    """Unidades, processos, contas, centros de custo e direcionadores ativos."""
    return list_dimensions(db)


def _register(kind: str, create_schema: type[BaseModel], update_schema: type[BaseModel]) -> None:
    path = f"/dimensions/{kind}"

    def list_items(db: Db) -> list[dict[str, Any]]:
        return service.serialize(db, kind, service.list_items(db, kind))

    def create_item(db: Db, body: create_schema) -> dict[str, Any]:  # type: ignore[valid-type]
        item = service.create_item(db, kind, body.model_dump(), DEMO_USER)
        return service.serialize(db, kind, [item])[0]

    def update_item(db: Db, item_id: int, body: update_schema) -> dict[str, Any]:  # type: ignore[valid-type]
        data = {
            k: v
            for k, v in body.model_dump(exclude_unset=True).items()
            if v is not None or k in CLEARABLE
        }
        item = service.update_item(db, kind, item_id, data, DEMO_USER)
        return service.serialize(db, kind, [item])[0]

    router.add_api_route(
        path, list_items, methods=["GET"], summary=f"Lista {kind}, inclusive inativos"
    )
    router.add_api_route(
        path, create_item, methods=["POST"], status_code=201, summary=f"Cria em {kind}"
    )
    router.add_api_route(
        f"{path}/{{item_id}}", update_item, methods=["PATCH"], summary=f"Altera em {kind}"
    )


_register("units", schemas.UnitIn, schemas.UnitUpdate)
_register("processes", schemas.ProcessIn, schemas.ProcessUpdate)
_register("drivers", schemas.DriverIn, schemas.DriverUpdate)
_register("accounts", schemas.AccountIn, schemas.AccountUpdate)
_register("cost-centers", schemas.CostCenterIn, schemas.CostCenterUpdate)
