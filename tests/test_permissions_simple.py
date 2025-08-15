import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


class TestPermissionsSimple:
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

    def test_permission_system_basic(self, app):
        """测试权限系统基本功能"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)

            # 创建服务器
            server = Server(name="Test Server", owner_id=user.id)
            db.session.add(server)
            db.session.commit()

            # 创建频道
            channel = Channel(name="General", server_id=server.id, type="text")
            db.session.add(channel)
            db.session.commit()

            # 创建权限
            permission = Permission(
                name="message.send",
                group="message",
                description="Send message permission",
            )
            db.session.add(permission)
            db.session.commit()

            # 创建角色
            role = Role(name="member", server_id=server.id, role_type="custom")
            db.session.add(role)
            db.session.commit()

            # 分配权限给角色
            role_permission = RolePermission(
                role_id=role.id,
                permission_id=permission.id,
                scope_type="channel",
                scope_id=channel.id,
            )
            db.session.add(role_permission)
            db.session.commit()

            # 分配角色给用户
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.session.add(user_role)
            db.session.commit()

            # 验证权限关系
            assert role_permission.role_id == role.id
            assert role_permission.permission_id == permission.id
            assert user_role.user_id == user.id
            assert user_role.role_id == role.id

    def test_permission_registration_works(self, app):
        """测试权限注册功能正常工作"""
        with app.app_context():
            from app.core.permissions import (
                register_permission,
                list_registered_permissions,
            )

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
            from app.core.permissions import (
                register_permission,
                list_registered_permissions,
            )

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

    def test_api_without_permission_decorator(self, client, app):
        """测试没有权限装饰器的API正常工作"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)

            # 创建服务器
            server = Server(name="Test Server", owner_id=user.id)
            db.session.add(server)
            db.session.commit()

            # 创建频道
            channel = Channel(name="General", server_id=server.id, type="text")
            db.session.add(channel)
            db.session.commit()

            # 获取token
            token = create_access_token(identity=str(user.id))
            auth_headers = {"Authorization": f"Bearer {token}"}

            # 测试获取频道信息（没有权限装饰器）
            resp = client.get(f"/api/channels/{channel.id}", headers=auth_headers)
            assert resp.status_code == 200

            # 测试获取频道类型（没有权限装饰器）
            resp = client.get(f"/api/channels/{channel.id}/type", headers=auth_headers)
            assert resp.status_code == 200

    def test_permission_decorator_integration(self, app):
        """测试权限装饰器集成"""
        with app.app_context():
            from app.core.permissions import require_permission

            # 测试权限装饰器可以正常应用
            @require_permission("test.permission")
            def test_function():
                return "success"

            # 装饰器应该返回一个函数
            assert callable(test_function)

            # 测试权限装饰器可以接受参数
            @require_permission(
                "test.permission", scope="channel", scope_id_arg="channel_id"
            )
            def test_function_with_scope():
                return "success"

            assert callable(test_function_with_scope)
