"""exam_matrix assessment link

Revision ID: 3e151d2e3b02
Revises: df061cc372a5
Create Date: 2026-06-01 13:52:55.657853
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3e151d2e3b02'
down_revision: Union[str, None] = 'df061cc372a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exam_matrices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assessment_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_exam_matrices_assessment', 'assessments', ['assessment_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('exam_matrices', schema=None) as batch_op:
        batch_op.drop_constraint('fk_exam_matrices_assessment', type_='foreignkey')
        batch_op.drop_column('assessment_id')
