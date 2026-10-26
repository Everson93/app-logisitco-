"""Manutenção dos cadastros (seção 11.4).

Cadastros não são apagados: um registro sai de uso ao ser desativado. Desativado, o código deixa
de ser aceito na importação e some dos filtros, mas o histórico importado e calculado continua
válido. Um direcionador não pode ser desativado enquanto for o padrão de um processo ativo ou
estiver numa regra de rateio ativa, porque o cálculo dependeria dele.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Account, AllocationRule, CostCenter, Driver, Process, Unit
from app.services import audit


@dataclass(frozen=True)
class Kind:
    model: type
    entity: str
    fields: tuple[str, ...]
    # campo da API -> (coluna, cadastro referenciado)
    refs: dict[str, tuple[str, type]] = field(default_factory=dict)


KINDS: dict[str, Kind] = {
    "units": Kind(Unit, "unit", ("unit_type",)),
    "drivers": Kind(Driver, "driver", ("unit_of_measure",)),
    "processes": Kind(
        Process, "process", (), {"default_driver_code": ("default_driver_id", Driver)}
    ),
    "accounts": Kind(Account, "account", ("cost_nature",)),
    "cost-centers": Kind(CostCenter, "cost_center", (), {"unit_code": ("unit_id", Unit)}),
}

REF_ERRORS = {Driver: "DRIVER", Unit: "UNIT"}


def _kind(kind: str) -> Kind:
    return KINDS[kind]


def _codes(db: Session, model: type, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(db.execute(select(model.id, model.code).where(model.id.in_(ids))).all())


def serialize(db: Session, kind: str, rows: list[Any]) -> list[dict[str, Any]]:
    spec = _kind(kind)
    ref_codes = {
        name: _codes(db, ref, {getattr(r, column) for r in rows} - {None})
        for name, (column, ref) in spec.refs.items()
    }
    out = []
    for r in rows:
        item = {"id": r.id, "code": r.code, "name": r.name, "active": r.active}
        item.update({f: getattr(r, f) for f in spec.fields})
        for name, (column, _) in spec.refs.items():
            ref_id = getattr(r, column)
            item[column] = ref_id
            item[name] = ref_codes[name].get(ref_id)
        out.append(item)
    return out


def list_items(db: Session, kind: str) -> list[Any]:
    model = _kind(kind).model
    return list(db.scalars(select(model).order_by(model.code)))


def get_item(db: Session, kind: str, item_id: int) -> Any:
    item = db.get(_kind(kind).model, item_id)
    if item is None:
        raise AppError(404, "DIMENSION_NOT_FOUND", "Cadastro não encontrado.")
    return item


def _resolve_refs(db: Session, spec: Kind, data: dict[str, Any]) -> dict[str, Any]:
    """Troca os códigos de referência pelos ids; só aceita cadastros ativos."""
    values: dict[str, Any] = {}
    details = []
    for name, (column, ref) in spec.refs.items():
        if name not in data:
            continue
        code = data.pop(name)
        if code is None:
            values[column] = None
            continue
        row = db.execute(select(ref.id, ref.active).where(ref.code == code)).first()
        if row is None:
            details.append({"field": name, "value": code, "code": f"UNKNOWN_{REF_ERRORS[ref]}"})
        elif not row.active:
            details.append({"field": name, "value": code, "code": f"INACTIVE_{REF_ERRORS[ref]}"})
        else:
            values[column] = row.id
    if details:
        raise AppError(422, "INVALID_DIMENSION", "O cadastro tem campos inválidos.", details)
    return values


def _check_driver_in_use(db: Session, driver: Driver) -> None:
    processes = db.scalars(
        select(Process.code).where(Process.default_driver_id == driver.id, Process.active.is_(True))
    ).all()
    rules = db.scalars(
        select(AllocationRule.id).where(
            AllocationRule.driver_id == driver.id, AllocationRule.active.is_(True)
        )
    ).all()
    if processes or rules:
        details = [{"field": "process", "value": c, "code": "DEFAULT_DRIVER"} for c in processes]
        details += [{"field": "allocation_rule", "value": r, "code": "RULE_DRIVER"} for r in rules]
        raise AppError(
            409,
            "DIMENSION_IN_USE",
            "O direcionador está em uso por processos ou regras de rateio ativos.",
            details,
        )


def create_item(db: Session, kind: str, data: dict[str, Any], actor: str | None) -> Any:
    spec = _kind(kind)
    model = spec.model
    if db.scalar(select(model.id).where(model.code == data["code"])) is not None:
        raise AppError(
            409,
            "DUPLICATE_CODE",
            "Já existe um cadastro com esse código.",
            [{"field": "code", "value": data["code"], "code": "DUPLICATE_CODE"}],
        )
    data = dict(data)
    values = _resolve_refs(db, spec, data)
    item = model(**data, **values)
    db.add(item)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="dimension.create",
        entity_type=spec.entity,
        entity_id=item.id,
        details={"code": item.code},
    )
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, kind: str, item_id: int, data: dict[str, Any], actor: str | None):
    spec = _kind(kind)
    item = get_item(db, kind, item_id)
    data = dict(data)
    if data.get("active") is False and item.active and spec.model is Driver:
        _check_driver_in_use(db, item)
    resolved = _resolve_refs(db, spec, data)  # tira os códigos de referência de `data`
    values = {**data, **resolved}
    changes = {
        key: [getattr(item, key), value]
        for key, value in values.items()
        if getattr(item, key) != value
    }
    for key, value in values.items():
        setattr(item, key, value)
    if changes:
        audit.record(
            db,
            actor=actor,
            action="dimension.update",
            entity_type=spec.entity,
            entity_id=item.id,
            details={"code": item.code, "changes": changes},
        )
    db.commit()
    db.refresh(item)
    return item
