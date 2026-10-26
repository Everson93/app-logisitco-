"""Orquestração da importação: preview -> validate -> commit (RF-001 a RF-006, RF-012)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Activity, Budget, Expense, ImportBatch, ImportRowError, ImportStagingRow
from app.repositories.dimensions import load_dimensions
from app.services.imports.fields import FIELDS, FileType, suggest_mapping
from app.services.imports.normalize import DateFormat, DecimalSeparator
from app.services.imports.parsing import FileRejected, ParsedRow, parse_csv
from app.services.imports.validation import (
    Issue,
    RowResult,
    RowValidator,
    ValidationOptions,
    budget_key,
    mark_duplicates,
)

PREVIEW_ROWS = 20
ISSUES_IN_RESPONSE = 100
EDITABLE_STATUSES = ("uploaded", "ready", "failed")

FACT_MODELS = {FileType.EXPENSES: Expense, FileType.ACTIVITIES: Activity, FileType.BUDGETS: Budget}


@dataclass
class PreviewResult:
    batch: ImportBatch
    rows: list[dict[str, str]]
    suggested_mapping: dict[str, str]
    same_file_batch_id: int | None


@dataclass
class ValidationSummary:
    batch: ImportBatch
    issues: list[Issue]
    issues_total: int
    rows_warning: int


def _get_batch(db: Session, batch_id: int, *, lock: bool = False) -> ImportBatch:
    stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
    if lock:
        stmt = stmt.with_for_update()
    batch = db.scalar(stmt)
    if batch is None:
        raise AppError(404, "BATCH_NOT_FOUND", "Lote de importação não encontrado.")
    return batch


def preview(
    db: Session, *, filename: str, content: bytes, file_type: FileType, uploaded_by: str | None
) -> PreviewResult:
    try:
        parsed = parse_csv(filename, content)
    except FileRejected as exc:
        raise AppError(422, exc.code, exc.message) from None

    same_file = db.scalar(
        select(ImportBatch.id)
        .where(ImportBatch.file_sha256 == parsed.sha256, ImportBatch.status == "committed")
        .order_by(ImportBatch.id.desc())
        .limit(1)
    )
    batch = ImportBatch(
        filename=filename[:255],
        file_type=file_type.value,
        uploaded_by=uploaded_by,
        status="uploaded",
        rows_total=len(parsed.rows),
        file_sha256=parsed.sha256,
        columns=parsed.columns,
    )
    db.add(batch)
    db.flush()
    db.add_all(
        ImportStagingRow(batch_id=batch.id, row_number=row.row_number, raw=row.values)
        for row in parsed.rows
    )
    db.commit()
    return PreviewResult(
        batch=batch,
        rows=[row.values for row in parsed.rows[:PREVIEW_ROWS]],
        suggested_mapping=suggest_mapping(file_type, parsed.columns),
        same_file_batch_id=same_file,
    )


def _check_mapping(
    file_type: FileType, columns: list[str], mapping: dict[str, str], defaults: dict[str, str]
) -> None:
    known = {spec.name for spec in FIELDS[file_type]}
    details: list[dict[str, Any]] = []
    for name, column in mapping.items():
        if name not in known:
            details.append({"field": name, "code": "UNKNOWN_FIELD"})
        elif column not in columns:
            details.append({"field": name, "column": column, "code": "UNKNOWN_COLUMN"})
    for name in defaults:
        if name not in known:
            details.append({"field": name, "code": "UNKNOWN_FIELD"})
    for spec in FIELDS[file_type]:
        if (
            spec.required
            and spec.name not in mapping
            and not (defaults.get(spec.name) or "").strip()
        ):
            details.append({"field": spec.name, "code": "REQUIRED_FIELD_NOT_MAPPED"})
    if details:
        raise AppError(
            422,
            "MAPPING_INCOMPLETE",
            "O mapeamento de colunas está incompleto ou inválido.",
            details,
        )


def _existing_keys(db: Session, file_type: FileType, results: Iterable[RowResult]) -> set:
    candidates = [r for r in results if r.is_valid]
    if not candidates:
        return set()
    if file_type is FileType.BUDGETS:
        keys = {budget_key(r.values) for r in candidates}
        stmt = select(
            Budget.period_start, Budget.unit_id, Budget.process_id, Budget.account_id
        ).where(
            tuple_(Budget.period_start, Budget.unit_id, Budget.process_id).in_(
                {k[:3] for k in keys}
            )
        )
        return {tuple(row) for row in db.execute(stmt)} & keys
    model = FACT_MODELS[file_type]
    source_keys = list({r.values["source_key"] for r in candidates})
    found: set = set()
    for start in range(0, len(source_keys), 1000):
        chunk = source_keys[start : start + 1000]
        found.update(db.scalars(select(model.source_key).where(model.source_key.in_(chunk))))
    return found


def _options_from_json(data: dict[str, Any]) -> ValidationOptions:
    return ValidationOptions(
        date_format=DateFormat(data.get("date_format", DateFormat.ISO)),
        decimal_separator=DecimalSeparator(data.get("decimal_separator", DecimalSeparator.DOT)),
    )


def _run_validation(db: Session, batch: ImportBatch) -> list[RowResult]:
    file_type = FileType(batch.file_type)
    validator = RowValidator(
        file_type,
        batch.column_mapping or {},
        batch.defaults or {},
        _options_from_json(batch.options or {}),
        load_dimensions(db),
    )
    staged = db.scalars(
        select(ImportStagingRow)
        .where(ImportStagingRow.batch_id == batch.id)
        .order_by(ImportStagingRow.row_number)
    )
    results = [validator.validate(ParsedRow(s.row_number, s.raw)) for s in staged]
    mark_duplicates(file_type, results, _existing_keys(db, file_type, results))
    return results


def validate(
    db: Session,
    batch_id: int,
    *,
    mapping: dict[str, str],
    defaults: dict[str, str],
    options: ValidationOptions,
) -> ValidationSummary:
    batch = _get_batch(db, batch_id, lock=True)
    if batch.status not in EDITABLE_STATUSES:
        raise AppError(
            409, "BATCH_NOT_EDITABLE", f"Lote com status '{batch.status}' não pode ser validado."
        )
    file_type = FileType(batch.file_type)
    _check_mapping(file_type, batch.columns or [], mapping, defaults)

    batch.column_mapping = mapping
    batch.defaults = defaults
    batch.options = {
        "date_format": options.date_format.value,
        "decimal_separator": options.decimal_separator.value,
    }
    results = _run_validation(db, batch)

    db.execute(delete(ImportRowError).where(ImportRowError.batch_id == batch.id))
    issues = [issue for r in results for issue in r.issues]
    db.add_all(
        ImportRowError(
            batch_id=batch.id,
            row_number=i.row_number,
            column_name=i.column,
            error_code=i.code.value,
            severity=i.severity.value,
            message=i.message,
        )
        for i in issues
    )
    batch.rows_valid = sum(r.is_valid for r in results)
    batch.rows_rejected = len(results) - batch.rows_valid
    batch.rows_ignored = sum(r.is_valid and r.already_imported for r in results)
    batch.status = "ready" if batch.rows_valid > batch.rows_ignored else "failed"
    db.commit()

    return ValidationSummary(
        batch=batch,
        issues=issues[:ISSUES_IN_RESPONSE],
        issues_total=len(issues),
        rows_warning=sum(r.is_valid and bool(r.issues) for r in results),
    )


def _fact_row(file_type: FileType, batch_id: int, values: dict[str, Any]) -> dict[str, Any]:
    row = {"source_batch_id": batch_id, **values}
    columns = FACT_MODELS[file_type].__table__.columns.keys()
    return {k: v for k, v in row.items() if k in columns}


def commit(db: Session, batch_id: int) -> ImportBatch:
    """Grava as linhas válidas em uma única transação; nada fica gravado pela metade."""
    batch = _get_batch(db, batch_id, lock=True)
    if batch.status != "ready":
        raise AppError(
            409,
            "BATCH_NOT_READY",
            f"Lote com status '{batch.status}' não pode ser confirmado. Valide-o antes.",
        )
    file_type = FileType(batch.file_type)
    model = FACT_MODELS[file_type]
    try:
        # Revalida com os cadastros atuais: algo pode ter mudado desde a validação.
        results = _run_validation(db, batch)
        to_insert = [
            _fact_row(file_type, batch.id, r.values)
            for r in results
            if r.is_valid and not r.already_imported
        ]
        inserted = 0
        for start in range(0, len(to_insert), 1000):
            chunk = to_insert[start : start + 1000]
            stmt = insert(model).values(chunk)
            if file_type is not FileType.BUDGETS:
                stmt = stmt.on_conflict_do_nothing(index_elements=["source_key"])
            inserted += len(db.scalars(stmt.returning(model.id)).all())

        batch.rows_valid = sum(r.is_valid for r in results)
        batch.rows_rejected = len(results) - batch.rows_valid
        batch.rows_committed = inserted
        batch.rows_ignored = batch.rows_valid - inserted
        batch.status = "committed"
        batch.committed_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return batch


def list_batches(
    db: Session, *, page: int, page_size: int, status: str | None, file_type: FileType | None
) -> tuple[list[ImportBatch], int]:
    stmt = select(ImportBatch)
    if status:
        stmt = stmt.where(ImportBatch.status == status)
    if file_type:
        stmt = stmt.where(ImportBatch.file_type == file_type.value)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(ImportBatch.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(items), total


def get_batch(db: Session, batch_id: int) -> ImportBatch:
    return _get_batch(db, batch_id)


def list_errors(
    db: Session, batch_id: int, *, page: int, page_size: int, severity: str | None
) -> tuple[list[ImportRowError], int]:
    _get_batch(db, batch_id)
    stmt = select(ImportRowError).where(ImportRowError.batch_id == batch_id)
    if severity:
        stmt = stmt.where(ImportRowError.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(ImportRowError.row_number, ImportRowError.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total
