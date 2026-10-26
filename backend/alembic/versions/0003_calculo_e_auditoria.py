"""calculo e auditoria

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26 17:15:13.280169

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_table(
        "calculation_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "allocation_rules",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("driver_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "scope", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column(
            "rounding", sa.String(length=40), server_default="largest_remainder", nullable=False
        ),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cost_results",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("calculation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("unit_id", sa.BigInteger(), nullable=False),
        sa.Column("process_id", sa.BigInteger(), nullable=True),
        sa.Column("direct_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("allocated_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("driver_id", sa.BigInteger(), nullable=True),
        sa.Column("driver_quantity", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=40), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("budget_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("variance_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("variance_percent", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column(
            "alerts", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["calculation_run_id"], ["calculation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cost_results_run_period",
        "cost_results",
        ["calculation_run_id", "period_start"],
        unique=False,
    )
    op.create_table(
        "allocation_results",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("calculation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("expense_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("target_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("target_process_id", sa.BigInteger(), nullable=False),
        sa.Column("driver_quantity", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["calculation_run_id"], ["calculation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["allocation_rules.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_process_id"],
            ["processes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_unit_id"],
            ["units.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_allocation_results_calculation_run_id"),
        "allocation_results",
        ["calculation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_allocation_results_expense_id"), "allocation_results", ["expense_id"], unique=False
    )
    op.create_table(
        "calculation_issues",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("calculation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("expense_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["calculation_run_id"], ["calculation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calculation_issues_calculation_run_id"),
        "calculation_issues",
        ["calculation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_calculation_issues_calculation_run_id"), table_name="calculation_issues")
    op.drop_table("calculation_issues")
    op.drop_index(op.f("ix_allocation_results_expense_id"), table_name="allocation_results")
    op.drop_index(op.f("ix_allocation_results_calculation_run_id"), table_name="allocation_results")
    op.drop_table("allocation_results")
    op.drop_index("ix_cost_results_run_period", table_name="cost_results")
    op.drop_table("cost_results")
    op.drop_table("allocation_rules")
    op.drop_table("calculation_runs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
