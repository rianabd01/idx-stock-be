"""Add raw staging table.

Revision ID: 20260817_0002
Revises: 20260817_0001
Create Date: 2026-08-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260817_0002"
down_revision: str | None = "20260817_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS raw (
            date date,
            share_code text,
            issuer_name text,
            investor_name text,
            investor_classification text,
            local_foreign text,
            nationality text,
            domicile text,
            holdings_scripless bigint,
            holdings_scrip bigint,
            total_holding_shares bigint,
            percentage numeric
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS raw")
