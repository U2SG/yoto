"""
调试批量注册角色问题
"""

import pytest
from app import create_app
from app.core.permission_registry import batch_register_roles
from app.blueprints.roles.models import Role
from app.core.extensions import db
from config import TestingConfig


class TestDebugRoles:
    """调试角色注册问题"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app(TestingConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()

    def test_debug_batch_register_roles(self, app):
        """调试批量注册角色"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Role).filter(
                Role.name.in_(["test_role_1", "test_role_2", "admin_role", "user_role"])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试数据
            roles_data = [
                {"name": "test_role_1", "server_id": 1, "is_active": True},
                {"name": "test_role_2", "server_id": 1, "is_active": True},
                {
                    "name": "admin_role",
                    "server_id": 1,
                    "is_active": True,
                },  # 使用有效的server_id
                {
                    "name": "user_role",
                    "server_id": 1,
                    "is_active": True,
                },  # 使用有效的server_id
            ]

            print(f"输入数据: {roles_data}")

            # 检查数据库中是否已有角色
            existing_before = (
                db.session.query(Role)
                .filter(
                    Role.name.in_(
                        ["test_role_1", "test_role_2", "admin_role", "user_role"]
                    )
                )
                .all()
            )
            print(
                f"注册前数据库中已有角色: {[(r.name, r.server_id) for r in existing_before]}"
            )

            # 执行批量注册
            results = batch_register_roles(roles_data)
            print(f"批量注册结果: {results}")

            # 检查数据库中的角色
            existing_after = (
                db.session.query(Role)
                .filter(
                    Role.name.in_(
                        ["test_role_1", "test_role_2", "admin_role", "user_role"]
                    )
                )
                .all()
            )
            print(
                f"注册后数据库中的角色: {[(r.name, r.server_id) for r in existing_after]}"
            )

            # 验证结果
            assert len(results) == len(roles_data)
            assert all(result["status"] in ["created", "updated"] for result in results)

            # 验证数据库中的角色数量
            assert len(existing_after) == len(roles_data)
