"""staging de importacao

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 17:02:53.194493

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_staging_rows",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_staging_rows_batch_id"), "import_staging_rows", ["batch_id"], unique=False
    )
    op.add_column(
        "import_batches",
        sa.Column("rows_ignored", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_batches",
        sa.Column("rows_committed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_batches",
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "import_batches", sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "import_row_errors",
        sa.Column("severity", sa.String(length=10), server_default="error", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("import_row_errors", "severity")
    op.drop_column("import_batches", "committed_at")
    op.drop_column("import_batches", "options")
    op.drop_column("import_batches", "defaults")
    op.drop_column("import_batches", "column_mapping")
    op.drop_column("import_batches", "columns")
    op.drop_column("import_batches", "rows_committed")
    op.drop_column("import_batches", "rows_ignored")
    op.drop_index(op.f("ix_import_staging_rows_batch_id"), table_name="import_staging_rows")
    op.drop_table("import_staging_rows")
