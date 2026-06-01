"""exam_matrix lifecycle fields

Revision ID: d18552a4ed68
Revises: c58ded1000f2
Create Date: 2026-06-01 08:59:03.051783
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd18552a4ed68'
down_revision: Union[str, None] = 'c58ded1000f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cột mới có server_default để tương thích hàng dữ liệu sẵn có; FK đặt tên rõ
    # (tránh lỗi "Constraint must have a name" khi batch ALTER trên SQLite).
    with op.batch_alter_table('exam_matrices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('total_points', sa.Float(), nullable=False, server_default='10'))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('approved_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key('fk_exam_matrices_created_by', 'users', ['created_by'], ['id'])
        batch_op.create_foreign_key('fk_exam_matrices_approved_by', 'users', ['approved_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('exam_matrices', schema=None) as batch_op:
        batch_op.drop_constraint('fk_exam_matrices_approved_by', type_='foreignkey')
        batch_op.drop_constraint('fk_exam_matrices_created_by', type_='foreignkey')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('approved_by')
        batch_op.drop_column('created_by')
        batch_op.drop_column('total_points')
        batch_op.drop_column('status')
