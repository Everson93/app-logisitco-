from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, CostCenter, Driver, Process, Unit
from app.services.imports.validation import Dimensions


def _codes(db: Session, model) -> dict[str, int]:
    rows = db.execute(select(model.code, model.id).where(model.active.is_(True)))
    return {code: id_ for code, id_ in rows}


def load_dimensions(db: Session) -> Dimensions:
    drivers = db.execute(
        select(Driver.code, Driver.id, Driver.unit_of_measure).where(Driver.active.is_(True))
    )
    return Dimensions(
        units=_codes(db, Unit),
        processes=_codes(db, Process),
        accounts=_codes(db, Account),
        cost_centers=_codes(db, CostCenter),
        drivers={code: (id_, uom) for code, id_, uom in drivers},
    )


def list_dimensions(db: Session) -> dict[str, list]:
    def rows(model):
        return db.execute(
            select(model).where(model.active.is_(True)).order_by(model.code)
        ).scalars()

    return {
        "units": [
            {"id": u.id, "code": u.code, "name": u.name, "unit_type": u.unit_type}
            for u in rows(Unit)
        ],
        "processes": [
            {"id": p.id, "code": p.code, "name": p.name, "default_driver_id": p.default_driver_id}
            for p in rows(Process)
        ],
        "accounts": [
            {"id": a.id, "code": a.code, "name": a.name, "cost_nature": a.cost_nature}
            for a in rows(Account)
        ],
        "cost_centers": [
            {"id": c.id, "code": c.code, "name": c.name, "unit_id": c.unit_id}
            for c in rows(CostCenter)
        ],
        "drivers": [
            {"id": d.id, "code": d.code, "name": d.name, "unit_of_measure": d.unit_of_measure}
            for d in rows(Driver)
        ],
    }
