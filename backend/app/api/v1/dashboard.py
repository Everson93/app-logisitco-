from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import audit
from app.services import dashboard as service
from app.services import transport as transport_service

router = APIRouter(tags=["dashboard"])

Db = Annotated[Session, Depends(get_db)]

DEMO_USER = "demo"


def filters(
    date_from: Annotated[date, Query(alias="from", examples=["2026-07-01"])],
    date_to: Annotated[date, Query(alias="to", examples=["2026-09-30"])],
    unit_id: int | None = None,
    process_id: int | None = None,
) -> service.Filters:
    return service.Filters(date_from, date_to, unit_id, process_id)


Filters = Annotated[service.Filters, Depends(filters)]


@router.get("/dashboard/summary")
def summary(db: Db, f: Filters) -> dict:
    """Cartões do dashboard: realizado, orçamento, desvios, custo unitário e alertas."""
    return service.summary(db, f)


@router.get("/dashboard/trend")
def trend(db: Db, f: Filters) -> list[dict]:
    """Série mensal de custo e orçamento."""
    return service.trend(db, f)


@router.get("/dashboard/by-process")
def by_process(db: Db, f: Filters) -> list[dict]:
    """Custo, orçamento, desvio e custo unitário por processo."""
    return service.by_process(db, f)


@router.get("/dashboard/variance")
def variance(
    db: Db,
    f: Filters,
    base_from: Annotated[date, Query(examples=["2026-07-01"])],
    base_to: Annotated[date, Query(examples=["2026-07-31"])],
) -> dict:
    """Variação contra um período base, separada em efeito volume e efeito eficiência."""
    base = service.Filters(base_from, base_to, f.unit_id, f.process_id)
    return service.variance(db, base, f)


@router.get("/dashboard/transport")
def transport(db: Db, f: Filters) -> dict:
    """Indicadores de transporte: custo por viagem, km e palete, ocupação e frota própria x
    terceira (seção 5.7). O filtro de processo não se aplica."""
    return transport_service.transport(db, f)


@router.get("/reports/costs.csv", response_class=Response)
def costs_csv(db: Db, f: Filters, format: str = Query("br", pattern="^(br|intl)$")) -> Response:
    content = service.report_csv(db, f, brazilian=format == "br")
    audit.record(
        db,
        actor=DEMO_USER,
        action="report.export",
        entity_type="report",
        entity_id=None,
        details={
            "from": f.date_from.isoformat(),
            "to": f.date_to.isoformat(),
            "unit_id": f.unit_id,
            "process_id": f.process_id,
        },
    )
    db.commit()
    filename = f"custos_{f.date_from:%Y%m}_{f.date_to:%Y%m}.csv"
    return Response(
        # BOM para o Excel reconhecer UTF-8 (acentos em nomes de unidade e processo).
        content="﻿" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
