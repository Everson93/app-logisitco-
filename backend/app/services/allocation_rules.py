"""Cadastro de regras de rateio (seção 11.4) com validação de cadastros e conflitos."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Account, AllocationRule, Driver, Process, Unit
from app.services import audit

SCOPE_KEYS = {
    "source_unit_codes": Unit,
    "source_account_codes": Account,
    "target_unit_codes": Unit,
    "target_process_codes": Process,
    "source_process_codes": Process,
}
EDITABLE_FIELDS = ("name", "valid_from", "valid_to", "scope", "priority", "active")


def _check(db: Session, *, driver_code: str | None, data: dict[str, Any]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    driver_id = None
    if driver_code is not None:
        driver_id = db.scalar(select(Driver.id).where(Driver.code == driver_code))
        if driver_id is None:
            details.append({"field": "driver_code", "code": "UNKNOWN_DRIVER"})

    scope = data.get("scope") or {}
    for key, codes in scope.items():
        model = SCOPE_KEYS.get(key)
        if model is None:
            details.append({"field": f"scope.{key}", "code": "UNKNOWN_FIELD"})
            continue
        known = set(db.scalars(select(model.code).where(model.code.in_(codes))))
        for code in codes:
            if code not in known:
                details.append({"field": f"scope.{key}", "value": code, "code": "UNKNOWN_CODE"})

    sources = set(scope.get("source_process_codes") or [])
    if sources and scope.get("source_account_codes"):
        details.append({"field": "scope.source_account_codes", "code": "NOT_ALLOWED_IN_CASCADE"})
    for code in sorted(sources & set(scope.get("target_process_codes") or [])):
        details.append(
            {"field": "scope.target_process_codes", "value": code, "code": "SOURCE_IS_TARGET"}
        )

    valid_from: date | None = data.get("valid_from")
    valid_to: date | None = data.get("valid_to")
    if valid_from and valid_to and valid_to < valid_from:
        details.append({"field": "valid_to", "code": "BEFORE_VALID_FROM"})

    if details:
        raise AppError(422, "INVALID_RULE", "A regra de rateio tem campos inválidos.", details)
    return {"driver_id": driver_id} if driver_id is not None else {}


def _overlaps(a: AllocationRule, b: AllocationRule) -> bool:
    a_end = a.valid_to or date.max
    b_end = b.valid_to or date.max
    if a.valid_from > b_end or b.valid_from > a_end:
        return False
    # Rateio de despesas e cascata nunca disputam o mesmo custo.
    a_sources = set((a.scope or {}).get("source_process_codes") or [])
    b_sources = set((b.scope or {}).get("source_process_codes") or [])
    if bool(a_sources) != bool(b_sources):
        return False
    if a_sources and not a_sources & b_sources:
        return False
    for key in ("source_unit_codes", "source_account_codes"):
        sa = set((a.scope or {}).get(key) or [])
        sb = set((b.scope or {}).get(key) or [])
        if sa and sb and not sa & sb:
            return False
    return True


def conflicts(db: Session, rule: AllocationRule) -> list[int]:
    """Regras ativas com a mesma prioridade que podem cobrir as mesmas despesas."""
    if not rule.active:
        return []
    others = db.scalars(
        select(AllocationRule).where(
            AllocationRule.active.is_(True),
            AllocationRule.priority == rule.priority,
            AllocationRule.id != rule.id,
        )
    )
    return [other.id for other in others if _overlaps(rule, other)]


def create_rule(db: Session, *, driver_code: str, data: dict[str, Any], actor: str | None):
    resolved = _check(db, driver_code=driver_code, data=data)
    rule = AllocationRule(**{k: v for k, v in data.items() if k in EDITABLE_FIELDS}, **resolved)
    rule.scope = data.get("scope") or {}
    db.add(rule)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="allocation_rule.create",
        entity_type="allocation_rule",
        entity_id=rule.id,
        details={"driver_code": driver_code, "priority": rule.priority},
    )
    db.commit()
    return rule


def update_rule(
    db: Session,
    rule_id: int,
    *,
    driver_code: str | None,
    data: dict[str, Any],
    actor: str | None,
):
    rule = get_rule(db, rule_id)
    merged = {
        "valid_from": data.get("valid_from", rule.valid_from),
        "valid_to": data.get("valid_to", rule.valid_to),
        "scope": data.get("scope", rule.scope),
    }
    resolved = _check(db, driver_code=driver_code, data=merged)
    changed = sorted(k for k in data if k in EDITABLE_FIELDS) + sorted(resolved)
    for key in EDITABLE_FIELDS:
        if key in data:
            setattr(rule, key, data[key] if key != "scope" else (data[key] or {}))
    for key, value in resolved.items():
        setattr(rule, key, value)
    audit.record(
        db,
        actor=actor,
        action="allocation_rule.update",
        entity_type="allocation_rule",
        entity_id=rule.id,
        details={"changed": changed},
    )
    db.commit()
    return rule


def get_rule(db: Session, rule_id: int) -> AllocationRule:
    rule = db.get(AllocationRule, rule_id)
    if rule is None:
        raise AppError(404, "RULE_NOT_FOUND", "Regra de rateio não encontrada.")
    return rule


def list_rules(db: Session, *, active: bool | None) -> list[AllocationRule]:
    stmt = select(AllocationRule).order_by(AllocationRule.priority, AllocationRule.id)
    if active is not None:
        stmt = stmt.where(AllocationRule.active.is_(active))
    return list(db.scalars(stmt))


def driver_codes(db: Session) -> dict[int, str]:
    return {id_: code for id_, code in db.execute(select(Driver.id, Driver.code))}
