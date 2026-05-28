# ruff: noqa: I001
"""knowledge builder enhancements

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:02.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.add_column(sa.Column("raw_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("extra_meta", sa.Text(), nullable=True))
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.add_column(sa.Column("extra_meta", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.drop_column("extra_meta")
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.drop_column("extra_meta")
        batch_op.drop_column("raw_text")
