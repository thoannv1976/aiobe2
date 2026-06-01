"""question review fields

Revision ID: df061cc372a5
Revises: d18552a4ed68
Create Date: 2026-06-01 09:19:09.586073
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'df061cc372a5'
down_revision: Union[str, None] = 'd18552a4ed68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chapter', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('learning_resource', sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column('review_status', sa.String(length=50), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('reviewed_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('review_note', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_questions_reviewed_by', 'users', ['reviewed_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_questions_reviewed_by', type_='foreignkey')
        batch_op.drop_column('review_note')
        batch_op.drop_column('reviewed_by')
        batch_op.drop_column('review_status')
        batch_op.drop_column('learning_resource')
        batch_op.drop_column('chapter')

    # ### end Alembic commands ###
