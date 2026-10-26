from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AllocationRule
from app.schemas.calculations import RuleIn, RuleOut, RuleUpdate
from app.services import allocation_rules as service

router = APIRouter(prefix="/allocation-rules", tags=["allocation-rules"])

Db = Annotated[Session, Depends(get_db)]

# Usuário fixo até a autenticação real (seção 3).
DEMO_USER = "demo"


def _out(db: Session, rule: AllocationRule, drivers: dict[int, str] | None = None) -> RuleOut:
    drivers = drivers or service.driver_codes(db)
    return RuleOut(
        id=rule.id,
        name=rule.name,
        driver_code=drivers[rule.driver_id],
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        scope=rule.scope or {},
        priority=rule.priority,
        rounding=rule.rounding,
        active=rule.active,
        conflicts_with=service.conflicts(db, rule),
    )


@router.get("", response_model=list[RuleOut])
def list_rules(db: Db, active: bool | None = None) -> list[RuleOut]:
    drivers = service.driver_codes(db)
    return [_out(db, rule, drivers) for rule in service.list_rules(db, active=active)]


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(db: Db, body: RuleIn) -> RuleOut:
    data = body.model_dump(exclude={"driver_code", "scope"})
    data["scope"] = body.scope.compact()
    rule = service.create_rule(db, driver_code=body.driver_code, data=data, actor=DEMO_USER)
    return _out(db, rule)


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(db: Db, rule_id: int) -> RuleOut:
    return _out(db, service.get_rule(db, rule_id))


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(db: Db, rule_id: int, body: RuleUpdate) -> RuleOut:
    data = body.model_dump(exclude_unset=True, exclude={"driver_code", "scope"})
    # Só valid_to pode ser limpo com null; nos demais campos, null significa "não alterar".
    data = {k: v for k, v in data.items() if v is not None or k == "valid_to"}
    if body.scope is not None:
        data["scope"] = body.scope.compact()
    rule = service.update_rule(
        db, rule_id, driver_code=body.driver_code, data=data, actor=DEMO_USER
    )
    return _out(db, rule)
