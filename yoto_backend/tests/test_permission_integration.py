"""
权限集成测试
测试权限工具在servers和channels模块中的集成效果
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.permission_utils import (
    create_crud_permissions,
    register_crud_permissions,
    require_crud_permission,
)


class TestPermissionIntegration:
    """测试权限集成功能"""

    def test_crud_permissions_creation(self):
        """测试CRUD权限创建"""
        # 测试服务器权限
        server_perms = create_crud_permissions("server", group="server")
        assert "server.create" in server_perms.values()
        assert "server.read" in server_perms.values()
        assert "server.update" in server_perms.values()
        assert "server.delete" in server_perms.values()

        # 测试频道权限
        channel_perms = create_crud_permissions("channel", group="channel")
        assert "channel.create" in channel_perms.values()
        assert "channel.read" in channel_perms.values()
        assert "channel.update" in channel_perms.values()
        assert "channel.delete" in channel_perms.values()

        # 测试消息权限
        message_perms = create_crud_permissions("message", group="message")
        assert "message.create" in message_perms.values()
        assert "message.read" in message_perms.values()
        assert "message.update" in message_perms.values()
        assert "message.delete" in message_perms.values()

    def test_permission_registration(self):
        """测试权限注册"""
        with patch("app.core.permission_utils.register_permission") as mock_register:
            mock_register.return_value = MagicMock()

            # 注册服务器权限
            server_perms = register_crud_permissions(
                "server", group="server", description="服务器管理权限"
            )

            # 验证注册调用
            assert mock_register.call_count == 4  # create, read, update, delete
            mock_register.assert_any_call(
                "server.create", group="server", description="服务器管理权限 - create"
            )
            mock_register.assert_any_call(
                "server.read", group="server", description="服务器管理权限 - read"
            )
            mock_register.assert_any_call(
                "server.update", group="server", description="服务器管理权限 - update"
            )
            mock_register.assert_any_call(
                "server.delete", group="server", description="服务器管理权限 - delete"
            )

    def test_require_crud_permission_decorator(self):
        """测试CRUD权限装饰器"""
        # 测试装饰器创建
        decorator = require_crud_permission(
            "delete", "server", scope="server", scope_id_arg="server_id"
        )
        assert callable(decorator)

        # 测试装饰器应用
        @decorator
        def test_function():
            return "success"

        assert callable(test_function)

    def test_permission_patterns_consistency(self):
        """测试权限模式一致性"""
        # 验证CRUD权限模式的一致性
        resources = ["server", "channel", "message", "role", "user"]

        for resource in resources:
            perms = create_crud_permissions(resource, group=resource)
            assert f"{resource}.create" in perms.values()
            assert f"{resource}.read" in perms.values()
            assert f"{resource}.update" in perms.values()
            assert f"{resource}.delete" in perms.values()

    def test_permission_scope_integration(self):
        """测试权限作用域集成"""
        # 测试不同作用域的权限装饰器
        scopes = ["server", "channel", "global"]

        for scope in scopes:
            decorator = require_crud_permission(
                "read", "resource", scope=scope, scope_id_arg=f"{scope}_id"
            )
            assert callable(decorator)

    def test_permission_group_organization(self):
        """测试权限组组织"""
        # 测试权限按组组织
        groups = ["server", "channel", "message", "role"]

        for group in groups:
            perms = create_crud_permissions(group, group=group)
            # 验证所有权限都属于指定组
            for perm in perms.values():
                assert perm.startswith(f"{group}.")

    def test_permission_validation_integration(self):
        """测试权限验证集成"""
        from app.core.permission_utils import validate_permission_structure

        # 测试有效的权限结构
        valid_permissions = [
            "server.create",
            "channel.read",
            "message.update",
            "role.delete",
            "user.manage",
        ]

        for perm in valid_permissions:
            assert validate_permission_structure(perm) == True

        # 测试无效的权限结构
        invalid_permissions = [
            "server",
            "create",
            "server.",
            ".create",
            "server..create",
        ]

        for perm in invalid_permissions:
            assert validate_permission_structure(perm) == False


class TestPermissionUtilsIntegration:
    """测试权限工具集成场景"""

    def test_complete_permission_workflow(self):
        """测试完整权限工作流程"""
        # 1. 创建权限
        server_perms = create_crud_permissions("server", group="server")

        # 2. 注册权限
        with patch("app.core.permission_utils.register_permission") as mock_register:
            mock_register.return_value = MagicMock()
            registered = register_crud_permissions(
                "server", group="server", description="服务器权限"
            )

            # 验证注册
            assert len(registered) == 4
            assert mock_register.call_count == 4

        # 3. 创建权限装饰器
        decorator = require_crud_permission(
            "delete", "server", scope="server", scope_id_arg="server_id"
        )

        # 4. 应用装饰器
        @decorator
        def test_api_function():
            return "success"

        # 验证装饰器应用
        assert callable(test_api_function)

    def test_permission_template_integration(self):
        """测试权限模板集成"""
        from app.core.permission_utils import PermissionTemplate, CRUD_TEMPLATE

        # 测试预定义模板
        assert CRUD_TEMPLATE.name == "crud"
        assert len(CRUD_TEMPLATE.permissions) == 4
        assert "create" in CRUD_TEMPLATE.permissions
        assert "read" in CRUD_TEMPLATE.permissions
        assert "update" in CRUD_TEMPLATE.permissions
        assert "delete" in CRUD_TEMPLATE.permissions

        # 测试自定义模板
        custom_template = PermissionTemplate(
            "custom", ["custom.action1", "custom.action2"], "自定义权限模板"
        )

        assert custom_template.name == "custom"
        assert len(custom_template.permissions) == 2
        assert "custom.action1" in custom_template.permissions
        assert "custom.action2" in custom_template.permissions

    def test_permission_chain_integration(self):
        """测试权限链集成"""
        from app.core.permission_utils import PermissionChain

        # 创建权限链
        chain = PermissionChain(["perm1", "perm2"], op="AND")

        assert chain.permissions == ["perm1", "perm2"]
        assert chain.op == "AND"

        # 测试装饰器应用
        @chain
        def test_function():
            return "success"

        assert callable(test_function)

    def test_permission_group_integration(self):
        """测试权限组集成"""
        from app.core.permission_utils import PermissionGroup

        # 创建权限组
        group = PermissionGroup("test_group", ["perm1", "perm2"])

        assert group.name == "test_group"
        assert len(group.permissions) == 2

        # 测试添加权限
        group.add_permission("perm3")
        assert len(group.permissions) == 3
        assert "perm3" in group.permissions

        # 测试移除权限
        group.remove_permission("perm1")
        assert len(group.permissions) == 2
        assert "perm1" not in group.permissions
        assert "perm2" in group.permissions
        assert "perm3" in group.permissions


class TestPermissionIntegrationEdgeCases:
    """测试权限集成边界情况"""

    def test_empty_permission_list(self):
        """测试空权限列表"""
        perms = create_crud_permissions("empty", group="empty")
        # 即使资源名为empty，也应该创建标准的CRUD权限
        assert len(perms) == 4
        assert "empty.create" in perms.values()

    def test_special_characters_in_resource_name(self):
        """测试资源名中的特殊字符"""
        # 权限验证应该处理特殊字符
        from app.core.permission_utils import validate_permission_structure

        # 包含特殊字符的权限名应该被拒绝
        invalid_perms = [
            "server.create!",
            "channel@read",
            "message#update",
            "role$delete",
        ]

        for perm in invalid_perms:
            assert validate_permission_structure(perm) == False

    def test_nested_permission_structure(self):
        """测试嵌套权限结构"""
        from app.core.permission_utils import (
            validate_permission_structure,
            get_permission_hierarchy,
        )

        # 测试多层嵌套权限
        nested_perm = "server.channel.message.create"
        assert validate_permission_structure(nested_perm) == True

        hierarchy = get_permission_hierarchy(nested_perm)
        assert hierarchy == [
            "server",
            "server.channel",
            "server.channel.message",
            "server.channel.message.create",
        ]

    def test_permission_cache_integration(self):
        """测试权限缓存集成"""
        from app.core.permission_utils import (
            create_permission_key,
            create_permission_hash,
        )

        # 测试权限键创建
        key = create_permission_key("server.create", scope="server", scope_id=1)
        assert key == "server.create:server:1"

        # 测试权限哈希创建
        perms = {"server.create", "server.read", "server.update"}
        hash_value = create_permission_hash(perms)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5哈希长度
