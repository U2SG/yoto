"""
权限工具模块测试
测试权限模板、权限链、权限组等高级功能
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.permission_utils import (
    PermissionTemplate,
    PermissionChain,
    PermissionGroup,
    create_crud_permissions,
    register_crud_permissions,
    require_crud_permission,
    validate_permission_structure,
    create_permission_key,
    get_permission_metadata,
    batch_validate_permissions,
    create_permission_hash,
    merge_permission_sets,
    filter_permissions_by_group,
    get_permission_hierarchy,
    CRUD_TEMPLATE,
    MESSAGE_TEMPLATE,
    SERVER_TEMPLATE,
    CHANNEL_TEMPLATE,
    ROLE_TEMPLATE,
    PERMISSION_PATTERNS,
)


class TestPermissionTemplate:
    """测试权限模板功能"""

    def test_permission_template_creation(self):
        """测试权限模板创建"""
        template = PermissionTemplate(
            "test_template", ["perm1", "perm2", "perm3"], "测试模板"
        )

        assert template.name == "test_template"
        assert template.permissions == ["perm1", "perm2", "perm3"]
        assert template.description == "测试模板"

    def test_permission_template_register_all(self):
        """测试权限模板注册所有权限"""
        with patch("app.core.permission_utils.register_permission") as mock_register:
            mock_register.return_value = MagicMock()

            template = PermissionTemplate(
                "test_template", ["perm1", "perm2"], "测试模板"
            )

            result = template.register_all(group="test_group")

            assert len(result) == 2
            assert mock_register.call_count == 2
            mock_register.assert_any_call(
                "perm1", group="test_group", description="测试模板 - perm1"
            )
            mock_register.assert_any_call(
                "perm2", group="test_group", description="测试模板 - perm2"
            )


class TestPermissionChain:
    """测试权限链功能"""

    def test_permission_chain_creation(self):
        """测试权限链创建"""
        chain = PermissionChain(["perm1", "perm2"], op="AND")

        assert chain.permissions == ["perm1", "perm2"]
        assert chain.op == "AND"

    def test_permission_chain_decorator(self):
        """测试权限链装饰器"""
        chain = PermissionChain(["perm1", "perm2"], op="AND")

        @chain
        def test_function():
            return "success"

        # 这里只是测试装饰器语法，实际权限检查需要更复杂的实现
        assert callable(test_function)


class TestPermissionGroup:
    """测试权限组功能"""

    def test_permission_group_creation(self):
        """测试权限组创建"""
        group = PermissionGroup("test_group", ["perm1", "perm2"])

        assert group.name == "test_group"
        assert group.permissions == ["perm1", "perm2"]

    def test_add_permission(self):
        """测试添加权限"""
        group = PermissionGroup("test_group")
        group.add_permission("perm1")

        assert "perm1" in group.permissions

    def test_remove_permission(self):
        """测试移除权限"""
        group = PermissionGroup("test_group", ["perm1", "perm2"])
        group.remove_permission("perm1")

        assert "perm1" not in group.permissions
        assert "perm2" in group.permissions


class TestPermissionUtils:
    """测试权限工具函数"""

    def test_create_crud_permissions(self):
        """测试创建CRUD权限"""
        perms = create_crud_permissions("user")

        assert perms["create"] == "user.create"
        assert perms["read"] == "user.read"
        assert perms["update"] == "user.update"
        assert perms["delete"] == "user.delete"

    def test_validate_permission_structure(self):
        """测试权限结构验证"""
        # 有效权限
        assert validate_permission_structure("user.create") == True
        assert validate_permission_structure("server.manage.users") == True

        # 无效权限
        assert validate_permission_structure("user") == False
        assert validate_permission_structure("user.") == False
        assert validate_permission_structure(".create") == False

    def test_create_permission_key(self):
        """测试创建权限键"""
        # 基本权限键
        key = create_permission_key("user.create")
        assert key == "user.create"

        # 带作用域的权限键
        key = create_permission_key("user.create", scope="server", scope_id=1)
        assert key == "user.create:server:1"

    def test_batch_validate_permissions(self):
        """测试批量权限验证"""
        permissions = ["user.create", "user.read", "invalid", "server.manage"]
        results = batch_validate_permissions(permissions)

        assert results["user.create"] == True
        assert results["user.read"] == True
        assert results["invalid"] == False
        assert results["server.manage"] == True

    def test_create_permission_hash(self):
        """测试创建权限哈希"""
        perms1 = {"user.create", "user.read"}
        perms2 = {"user.read", "user.create"}  # 相同权限，不同顺序

        hash1 = create_permission_hash(perms1)
        hash2 = create_permission_hash(perms2)

        assert hash1 == hash2  # 应该相同，因为排序后相同

    def test_merge_permission_sets(self):
        """测试合并权限集合"""
        set1 = {"perm1", "perm2"}
        set2 = {"perm2", "perm3"}
        set3 = {"perm4"}

        merged = merge_permission_sets(set1, set2, set3)

        assert merged == {"perm1", "perm2", "perm3", "perm4"}

    def test_filter_permissions_by_group(self):
        """测试按组过滤权限"""
        permissions = {"user.create", "user.read", "server.manage", "server.view"}

        user_perms = filter_permissions_by_group(permissions, "user")
        server_perms = filter_permissions_by_group(permissions, "server")

        assert user_perms == {"user.create", "user.read"}
        assert server_perms == {"server.manage", "server.view"}

    def test_get_permission_hierarchy(self):
        """测试获取权限层次结构"""
        hierarchy = get_permission_hierarchy("server.manage.users")

        assert hierarchy == ["server", "server.manage", "server.manage.users"]


class TestPredefinedTemplates:
    """测试预定义模板"""

    def test_crud_template(self):
        """测试CRUD模板"""
        assert CRUD_TEMPLATE.name == "crud"
        assert "create" in CRUD_TEMPLATE.permissions
        assert "read" in CRUD_TEMPLATE.permissions
        assert "update" in CRUD_TEMPLATE.permissions
        assert "delete" in CRUD_TEMPLATE.permissions

    def test_message_template(self):
        """测试消息模板"""
        assert MESSAGE_TEMPLATE.name == "message"
        assert "message.send" in MESSAGE_TEMPLATE.permissions
        assert "message.edit" in MESSAGE_TEMPLATE.permissions
        assert "message.delete" in MESSAGE_TEMPLATE.permissions

    def test_server_template(self):
        """测试服务器模板"""
        assert SERVER_TEMPLATE.name == "server"
        assert "server.view" in SERVER_TEMPLATE.permissions
        assert "server.manage" in SERVER_TEMPLATE.permissions

    def test_channel_template(self):
        """测试频道模板"""
        assert CHANNEL_TEMPLATE.name == "channel"
        assert "channel.view" in CHANNEL_TEMPLATE.permissions
        assert "channel.send" in CHANNEL_TEMPLATE.permissions

    def test_role_template(self):
        """测试角色模板"""
        assert ROLE_TEMPLATE.name == "role"
        assert "role.view" in ROLE_TEMPLATE.permissions
        assert "role.assign" in ROLE_TEMPLATE.permissions


class TestPermissionPatterns:
    """测试权限模式"""

    def test_permission_patterns_structure(self):
        """测试权限模式结构"""
        assert "crud" in PERMISSION_PATTERNS
        assert "message" in PERMISSION_PATTERNS
        assert "server" in PERMISSION_PATTERNS
        assert "channel" in PERMISSION_PATTERNS
        assert "role" in PERMISSION_PATTERNS

    def test_crud_pattern(self):
        """测试CRUD模式"""
        crud_pattern = PERMISSION_PATTERNS["crud"]
        assert "create" in crud_pattern
        assert "read" in crud_pattern
        assert "update" in crud_pattern
        assert "delete" in crud_pattern

    def test_message_pattern(self):
        """测试消息模式"""
        message_pattern = PERMISSION_PATTERNS["message"]
        assert "send" in message_pattern
        assert "edit" in message_pattern
        assert "delete" in message_pattern
        assert "pin" in message_pattern
        assert "react" in message_pattern
        assert "search" in message_pattern


class TestPermissionUtilsIntegration:
    """测试权限工具集成场景"""

    def test_complete_workflow(self):
        """测试完整工作流程"""
        # 1. 创建权限模板
        template = PermissionTemplate(
            "custom_template",
            ["custom.create", "custom.read", "custom.update"],
            "自定义模板",
        )

        # 2. 创建权限组
        group = PermissionGroup("custom_group", ["custom.create"])
        group.add_permission("custom.read")

        # 3. 验证权限结构
        permissions = ["custom.create", "custom.read", "custom.update"]
        validation_results = batch_validate_permissions(permissions)

        # 4. 创建权限键
        key = create_permission_key("custom.create", scope="server", scope_id=1)

        # 5. 合并权限集合
        set1 = {"custom.create", "custom.read"}
        set2 = {"custom.update", "custom.delete"}
        merged = merge_permission_sets(set1, set2)

        # 验证结果
        assert template.name == "custom_template"
        assert len(template.permissions) == 3
        assert "custom.read" in group.permissions
        assert all(validation_results.values())
        assert key == "custom.create:server:1"
        assert merged == {
            "custom.create",
            "custom.read",
            "custom.update",
            "custom.delete",
        }
