"""question rubric_json

Revision ID: 6f032688d4ee
Revises: 3e151d2e3b02
Create Date: 2026-06-01 14:08:22.905658
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6f032688d4ee'
down_revision: Union[str, None] = '3e151d2e3b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rubric_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_column('rubric_json')
