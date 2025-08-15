"""修复password_hash字段长度

Revision ID: fix_password_hash_length
Revises: 005_add_permission_groups
Create Date: 2025-08-03 13:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'fix_password_hash_length'
down_revision = '005_add_permission_groups'
branch_labels = None
depends_on = None


def upgrade():
    """升级：增加password_hash字段长度"""
    # 修改password_hash字段长度从128增加到180
    op.alter_column('users', 'password_hash',
                    existing_type=mysql.VARCHAR(length=128),
                    type_=mysql.VARCHAR(length=180),
                    existing_nullable=False)


def downgrade():
    """降级：恢复password_hash字段长度"""
    # 恢复password_hash字段长度从180减少到128
    op.alter_column('users', 'password_hash',
                    existing_type=mysql.VARCHAR(length=180),
                    type_=mysql.VARCHAR(length=128),
                    existing_nullable=False) 