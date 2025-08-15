"""
SOTA权限体系基础测试
测试核心的数据模型和基本功能。
"""

import pytest
from datetime import datetime, timedelta
from app import create_app
from app.core.extensions import db
from app.blueprints.roles.models import (
    Role,
    UserRole,
    RolePermission,
    Permission,
    PermissionAuditLog,
)
from app.blueprints.auth.models import User
from app.core.permissions import (
    register_permission,
    list_registered_permissions,
    get_cache_stats,
)


class TestSOTABasicModels:
    """测试SOTA基础数据模型"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_role_model_creation(self):
        """测试Role模型创建"""
        role = Role(
            name="admin",
            server_id=1,
            role_type="system",
            priority=100,
            role_metadata={"description": "系统管理员"},
            is_active=True,
        )
        db.session.add(role)
        db.session.commit()

        assert role.id is not None
        assert role.name == "admin"
        assert role.role_type == "system"
        assert role.priority == 100
        assert role.role_metadata["description"] == "系统管理员"
        assert role.is_active is True
        assert role.created_at is not None

    def test_permission_model_creation(self):
        """测试Permission模型创建"""
        permission = Permission(
            name="manage_users",
            group="administration",
            category="user_management",
            permission_type="admin",
            level=5,
            dependencies=["read_users"],
            conflicts=["guest_access"],
            version="1.0",
            permission_metadata={"risk_level": "high"},
        )
        db.session.add(permission)
        db.session.commit()

        assert permission.id is not None
        assert permission.name == "manage_users"
        assert permission.group == "administration"
        assert permission.category == "user_management"
        assert permission.permission_type == "admin"
        assert permission.level == 5
        assert "read_users" in permission.dependencies
        assert "guest_access" in permission.conflicts
        assert permission.version == "1.0"
        assert permission.permission_metadata["risk_level"] == "high"

    def test_user_role_model_creation(self):
        """测试UserRole模型创建"""
        user = User(username="testuser", password_hash="dummy_hash")
        role = Role(name="member", server_id=1)
        db.session.add_all([user, role])
        db.session.commit()

        user_role = UserRole(
            user_id=user.id,
            role_id=role.id,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=30),
            conditions={"time_restriction": "business_hours"},
        )
        db.session.add(user_role)
        db.session.commit()

        assert user_role.id is not None
        assert user_role.user_id == user.id
        assert user_role.role_id == role.id
        assert user_role.valid_from is not None
        assert user_role.valid_until is not None
        assert user_role.conditions["time_restriction"] == "business_hours"

    def test_role_permission_model_creation(self):
        """测试RolePermission模型创建"""
        role = Role(name="moderator", server_id=1)
        permission = Permission(name="delete_message", group="moderation")
        db.session.add_all([role, permission])
        db.session.commit()

        role_perm = RolePermission(
            role_id=role.id,
            permission_id=permission.id,
            expression="user_id != message_author_id",
            conditions={"channel_type": "public"},
            scope_type="channel",
            scope_id=1,
        )
        db.session.add(role_perm)
        db.session.commit()

        assert role_perm.id is not None
        assert role_perm.role_id == role.id
        assert role_perm.permission_id == permission.id
        assert role_perm.expression == "user_id != message_author_id"
        assert role_perm.conditions["channel_type"] == "public"
        assert role_perm.scope_type == "channel"
        assert role_perm.scope_id == 1

    def test_permission_audit_log_creation(self):
        """测试PermissionAuditLog模型创建"""
        audit_log = PermissionAuditLog(
            operation="create",
            resource_type="role",
            resource_id=1,
            old_values={"name": "old_role"},
            new_values={"name": "new_role"},
            operator_id=1,
            operator_ip="127.0.0.1",
            user_agent="test-agent",
        )
        db.session.add(audit_log)
        db.session.commit()

        assert audit_log.id is not None
        assert audit_log.operation == "create"
        assert audit_log.resource_type == "role"
        assert audit_log.resource_id == 1
        assert audit_log.old_values["name"] == "old_role"
        assert audit_log.new_values["name"] == "new_role"
        assert audit_log.operator_id == 1
        assert audit_log.operator_ip == "127.0.0.1"
        assert audit_log.user_agent == "test-agent"
        assert audit_log.created_at is not None


class TestSOTAPermissionRegistration:
    """测试权限注册功能"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_register_permission(self):
        """测试权限注册"""
        # 注册权限
        register_permission("test.permission", group="test", description="测试权限")

        # 验证权限已注册到数据库
        permission = Permission.query.filter_by(name="test.permission").first()
        assert permission is not None
        assert permission.group == "test"
        assert permission.description == "测试权限"

    def test_list_registered_permissions(self):
        """测试列出已注册权限"""
        # 注册多个权限
        register_permission("permission1", group="group1", description="权限1")
        register_permission("permission2", group="group2", description="权限2")

        # 获取已注册权限列表
        permissions = list_registered_permissions()

        # 验证返回结果
        assert len(permissions) >= 2
        permission_names = [p["name"] for p in permissions]
        assert "permission1" in permission_names
        assert "permission2" in permission_names


class TestSOTACacheStats:
    """测试缓存统计功能"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get_cache_stats(self):
        """测试获取缓存统计"""
        stats = get_cache_stats()

        # 验证返回的统计信息
        assert "l1_cache_size" in stats
        assert "l1_cache_maxsize" in stats
        assert "l2_cache" in stats

        # 验证数据类型
        assert isinstance(stats["l1_cache_size"], int)
        assert isinstance(stats["l1_cache_maxsize"], int)
        assert isinstance(stats["l2_cache"], dict)


class TestSOTAModelRelationships:
    """测试模型关系"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_role_user_relationship(self):
        """测试角色用户关系"""
        user = User(username="testuser", password_hash="dummy_hash")
        role = Role(name="member", server_id=1)
        db.session.add_all([user, role])
        db.session.commit()

        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.session.add(user_role)
        db.session.commit()

        # 测试关系查询
        user_roles = UserRole.query.filter_by(user_id=user.id).all()
        assert len(user_roles) == 1
        assert user_roles[0].role_id == role.id

    def test_role_permission_relationship(self):
        """测试角色权限关系"""
        role = Role(name="moderator", server_id=1)
        permission = Permission(name="delete_message", group="moderation")
        db.session.add_all([role, permission])
        db.session.commit()

        role_perm = RolePermission(role_id=role.id, permission_id=permission.id)
        db.session.add(role_perm)
        db.session.commit()

        # 测试关系查询
        role_permissions = RolePermission.query.filter_by(role_id=role.id).all()
        assert len(role_permissions) == 1
        assert role_permissions[0].permission_id == permission.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
