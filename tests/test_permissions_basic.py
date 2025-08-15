import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token

# 更新导入语句，使用重构后的权限系统
from app.core.permissions_refactored import (
    register_permission,
    list_registered_permissions,
)


class TestPermissionsBasic:
    @pytest.fixture
    def app(self):
        app = create_app("testing")
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_permission_creation(self, app):
        """测试权限创建"""
        with app.app_context():
            # 创建权限
            permission = Permission(
                name="test.permission", group="test", description="Test permission"
            )
            db.session.add(permission)
            db.session.commit()

            assert permission.id is not None
            assert permission.name == "test.permission"
            assert permission.group == "test"
            assert permission.description == "Test permission"
            assert permission.is_deprecated is False

    def test_role_creation(self, app):
        """测试角色创建"""
        with app.app_context():
            # 创建角色
            role = Role(name="Test Role", role_type="custom", priority=50)
            db.session.add(role)
            db.session.commit()

            assert role.id is not None
            assert role.name == "Test Role"
            assert role.role_type == "custom"
            assert role.priority == 50
            assert role.is_active is True

    def test_user_role_assignment(self, app):
        """测试用户角色分配"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("password"),
            )
            db.session.add(user)
            db.session.commit()

            # 创建角色
            role = Role(name="Test Role", role_type="custom", priority=50)
            db.session.add(role)
            db.session.commit()

            # 分配角色给用户
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.session.add(user_role)
            db.session.commit()

            assert user_role.id is not None
            assert user_role.user_id == user.id
            assert user_role.role_id == role.id

    def test_permission_registration(self, app):
        """测试权限注册功能"""
        with app.app_context():
            # 注册权限
            register_permission(
                "test.permission", group="test", description="Test permission"
            )

            # 检查权限是否注册成功
            permissions = list_registered_permissions()
            permission_names = [p["name"] for p in permissions]

            assert "test.permission" in permission_names

    def test_message_permissions_registration(self, app):
        """测试消息权限注册"""
        with app.app_context():
            # 注册消息相关权限
            message_permissions = [
                "message.send",
                "message.edit",
                "message.delete",
                "message.pin",
                "message.unpin",
                "message.forward",
                "message.react",
                "message.search",
                "message.view_history",
                "message.manage_history",
            ]

            for perm in message_permissions:
                register_permission(
                    perm, group="message", description=f"{perm} permission"
                )

            # 检查权限是否注册成功
            permissions = list_registered_permissions()
            permission_names = [p["name"] for p in permissions]

            for perm in message_permissions:
                assert perm in permission_names
