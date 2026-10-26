from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.imports import (
    BatchOut,
    BatchPage,
    FieldOut,
    IssueOut,
    IssuePage,
    PreviewOut,
    ValidateIn,
    ValidationOut,
)
from app.services.imports import service
from app.services.imports.fields import FIELDS, FileType
from app.services.imports.parsing import MAX_FILE_BYTES
from app.services.imports.validation import ValidationOptions

router = APIRouter(prefix="/imports", tags=["imports"])

Db = Annotated[Session, Depends(get_db)]

# Usuário fixo até a autenticação real (seção 3: MVP com um usuário local de demonstração).
DEMO_USER = "demo"


@router.post("/preview", response_model=PreviewOut, status_code=201)
async def preview(
    db: Db,
    file: Annotated[UploadFile, File(description="Arquivo CSV")],
    file_type: Annotated[FileType, Form()],
) -> PreviewOut:
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise AppError(422, "FILE_TOO_LARGE", "O arquivo excede o limite de 5 MB.")
    result = service.preview(
        db,
        filename=file.filename or "arquivo.csv",
        content=content,
        file_type=file_type,
        uploaded_by=DEMO_USER,
    )
    warnings = []
    if result.same_file_batch_id is not None:
        warnings.append(
            f"Este arquivo já foi importado no lote {result.same_file_batch_id}; "
            "registros repetidos serão ignorados."
        )
    return PreviewOut(
        batch=BatchOut.model_validate(result.batch),
        columns=result.batch.columns or [],
        rows=result.rows,
        fields=[
            FieldOut(name=f.name, kind=f.kind.value, required=f.required) for f in FIELDS[file_type]
        ],
        suggested_mapping=result.suggested_mapping,
        warnings=warnings,
    )


@router.post("/{batch_id}/validate", response_model=ValidationOut)
def validate(db: Db, batch_id: int, body: ValidateIn) -> ValidationOut:
    summary = service.validate(
        db,
        batch_id,
        mapping=body.mapping,
        defaults=body.defaults,
        options=ValidationOptions(body.date_format, body.decimal_separator),
    )
    return ValidationOut(
        batch=BatchOut.model_validate(summary.batch),
        rows_warning=summary.rows_warning,
        issues_total=summary.issues_total,
        issues=[
            IssueOut(
                row=i.row_number,
                column=i.column,
                code=i.code.value,
                severity=i.severity.value,
                message=i.message,
            )
            for i in summary.issues
        ],
    )


@router.post("/{batch_id}/commit", response_model=BatchOut)
def commit(db: Db, batch_id: int) -> BatchOut:
    return BatchOut.model_validate(service.commit(db, batch_id))


@router.get("", response_model=BatchPage)
def list_batches(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    file_type: FileType | None = None,
) -> BatchPage:
    items, total = service.list_batches(
        db, page=page, page_size=page_size, status=status, file_type=file_type
    )
    return BatchPage(
        items=[BatchOut.model_validate(b) for b in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(db: Db, batch_id: int) -> BatchOut:
    return BatchOut.model_validate(service.get_batch(db, batch_id))


@router.get("/{batch_id}/errors", response_model=IssuePage)
def list_errors(
    db: Db,
    batch_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 100,
    severity: str | None = None,
) -> IssuePage:
    items, total = service.list_errors(
        db, batch_id, page=page, page_size=page_size, severity=severity
    )
    return IssuePage(
        items=[
            IssueOut(
                row=e.row_number,
                column=e.column_name,
                code=e.error_code,
                severity=e.severity,
                message=e.message,
            )
            for e in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )
