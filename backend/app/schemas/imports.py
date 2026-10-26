from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.imports.fields import FileType
from app.services.imports.normalize import DateFormat, DecimalSeparator


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: FileType
    uploaded_by: str | None
    status: str
    rows_total: int
    rows_valid: int
    rows_rejected: int
    rows_ignored: int
    rows_committed: int
    file_sha256: str | None
    created_at: datetime
    committed_at: datetime | None


class FieldOut(BaseModel):
    name: str
    kind: str
    required: bool


class PreviewOut(BaseModel):
    batch: BatchOut
    columns: list[str]
    sheets: list[str] = Field(description="Abas do XLSX (vazio para CSV).")
    sheet: str | None = Field(description="Aba lida.")
    rows: list[dict[str, str]]
    fields: list[FieldOut]
    suggested_mapping: dict[str, str]
    warnings: list[str]


class ValidateIn(BaseModel):
    mapping: dict[str, str] = Field(
        description="Campo padronizado -> nome da coluna no arquivo.",
        examples=[{"competence_date": "Data", "amount": "Valor"}],
    )
    defaults: dict[str, str] = Field(
        default_factory=dict,
        description="Valor fixo para campos que não existem como coluna (ex.: unit_code).",
    )
    date_format: DateFormat = DateFormat.ISO
    decimal_separator: DecimalSeparator = DecimalSeparator.DOT


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row: int
    column: str | None
    code: str
    severity: str
    message: str


class ValidationOut(BaseModel):
    batch: BatchOut
    rows_warning: int
    issues_total: int
    issues: list[IssueOut]


class BatchPage(BaseModel):
    items: list[BatchOut]
    page: int
    page_size: int
    total: int


class IssuePage(BaseModel):
    items: list[IssueOut]
    page: int
    page_size: int
    total: int
