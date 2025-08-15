"""添加权限组支持

Revision ID: 005
Revises: 004
Create Date: 2024-12-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """升级：添加权限组相关表"""
    
    # 创建权限组表
    op.create_table('permission_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # 创建权限组到权限的映射表
    op.create_table('group_to_permission_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['group_id'], ['permission_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('group_id', 'permission_id', name='uq_group_permission')
    )
    
    # 创建角色到权限组的映射表
    op.create_table('role_to_group_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('scope_type', sa.String(length=50), nullable=True),
        sa.Column('scope_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['permission_groups.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('role_id', 'group_id', 'scope_type', 'scope_id', name='uq_role_group_scope')
    )
    
    # 创建索引以提高查询性能
    op.create_index('idx_permission_groups_name', 'permission_groups', ['name'])
    op.create_index('idx_permission_groups_active', 'permission_groups', ['is_active'])
    op.create_index('idx_group_permission_mappings_group', 'group_to_permission_mappings', ['group_id'])
    op.create_index('idx_group_permission_mappings_permission', 'group_to_permission_mappings', ['permission_id'])
    op.create_index('idx_role_group_mappings_role', 'role_to_group_mappings', ['role_id'])
    op.create_index('idx_role_group_mappings_group', 'role_to_group_mappings', ['group_id'])
    op.create_index('idx_role_group_mappings_scope', 'role_to_group_mappings', ['scope_type', 'scope_id'])


def downgrade():
    """降级：删除权限组相关表"""
    
    # 删除索引
    op.drop_index('idx_role_group_mappings_scope', 'role_to_group_mappings')
    op.drop_index('idx_role_group_mappings_group', 'role_to_group_mappings')
    op.drop_index('idx_role_group_mappings_role', 'role_to_group_mappings')
    op.drop_index('idx_group_permission_mappings_permission', 'group_to_permission_mappings')
    op.drop_index('idx_group_permission_mappings_group', 'group_to_permission_mappings')
    op.drop_index('idx_permission_groups_active', 'permission_groups')
    op.drop_index('idx_permission_groups_name', 'permission_groups')
    
    # 删除表
    op.drop_table('role_to_group_mappings')
    op.drop_table('group_to_permission_mappings')
    op.drop_table('permission_groups') 