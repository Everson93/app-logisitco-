from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Status possíveis de um lote: uploaded, validating, ready, committed, failed, cancelled.


class ImportBatch(Base):
    """Lote de importação; todo fato aponta para o lote que o originou."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(40))
    uploaded_by: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), server_default="uploaded")
    rows_total: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_valid: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_rejected: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_ignored: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_committed: Mapped[int] = mapped_column(Integer, server_default="0")
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    columns: Mapped[list[str] | None] = mapped_column(JSONB)
    column_mapping: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    defaults: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportStagingRow(Base):
    """Linha bruta do arquivo, guardada sem alteração até (e depois de) a confirmação."""

    __tablename__ = "import_staging_rows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict[str, str]] = mapped_column(JSONB)


class ImportRowError(Base):
    __tablename__ = "import_row_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(120))
    error_code: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10), server_default="error")
    message: Mapped[str] = mapped_column(Text)
