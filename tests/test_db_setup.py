"""
数据库设置测试
验证所有表是否正确创建
"""

import pytest
from app import create_app
from app.core.extensions import db


def test_database_tables():
    """测试数据库表创建"""
    app = create_app("testing")
    with app.app_context():
        # 创建所有表
        db.create_all()

        # 检查所有表是否存在
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"创建的数据库表: {tables}")

        # 检查关键表是否存在
        expected_tables = [
            "users",
            "servers",
            "server_members",
            "channels",
            "categories",
            "channel_members",
            "messages",
            "roles",
            "user_roles",
            "role_permissions",
            "permissions",
            "permission_audit_logs",
            "friendships",
        ]

        for table in expected_tables:
            assert table in tables, f"表 {table} 不存在"

        # 清理
        db.drop_all()


def test_model_imports():
    """测试模型导入"""
    app = create_app("testing")
    with app.app_context():
        # 测试导入所有模型
        from app.blueprints.auth.models import User
        from app.blueprints.servers.models import Server, ServerMember
        from app.blueprints.channels.models import (
            Channel,
            Message,
            Category,
            ChannelMember,
        )
        from app.blueprints.roles.models import (
            Role,
            UserRole,
            RolePermission,
            Permission,
            PermissionAuditLog,
        )
        from app.blueprints.users.models import Friendship

        print("所有模型导入成功")

        # 创建表
        db.create_all()

        # 验证表存在
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"实际创建的表: {tables}")

        db.drop_all()
