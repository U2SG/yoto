"""
权限工厂模块测试 - 工厂函数层
测试权限相关的工厂函数，验证创建和注册逻辑
"""

import pytest
from unittest.mock import Mock
from app.core.permission_factories import (
    create_crud_permissions,
    register_crud_permissions,
    create_permission_pattern,
    register_permission_pattern,
    create_permission_chain,
    create_permission_group,
    create_permission_decorator,
    require_crud_permission,
)


class TestCreateCrudPermissions:
    """测试CRUD权限创建函数"""

    def test_create_crud_permissions_basic(self):
        """测试基础CRUD权限创建"""
        result = create_crud_permissions("user")
        expected = {
            "create": "user.create",
            "read": "user.read",
            "update": "user.update",
            "delete": "user.delete",
        }
        assert result == expected

    def test_create_crud_permissions_with_group(self):
        """测试带组的CRUD权限创建"""
        result = create_crud_permissions("server", "admin")
        expected = {
            "create": "server.create",
            "read": "server.read",
            "update": "server.update",
            "delete": "server.delete",
        }
        assert result == expected

    def test_create_crud_permissions_different_resource(self):
        """测试不同资源的CRUD权限创建"""
        result = create_crud_permissions("channel")
        expected = {
            "create": "channel.create",
            "read": "channel.read",
            "update": "channel.update",
            "delete": "channel.delete",
        }
        assert result == expected


class TestRegisterCrudPermissions:
    """测试CRUD权限注册函数"""

    def test_register_crud_permissions_without_register(self):
        """测试无注册函数的CRUD权限注册"""
        result = register_crud_permissions("user")
        expected = {
            "create": "user.create",
            "read": "user.read",
            "update": "user.update",
            "delete": "user.delete",
        }
        assert result == expected

    def test_register_crud_permissions_with_register(self):
        """测试有注册函数的CRUD权限注册"""
        mock_register = Mock()
        result = register_crud_permissions("user", mock_register, "admin", "用户管理")

        expected = {
            "create": "user.create",
            "read": "user.read",
            "update": "user.update",
            "delete": "user.delete",
        }
        assert result == expected

        # 验证注册函数被调用了4次（create, read, update, delete）
        assert mock_register.call_count == 4
        mock_register.assert_any_call(
            "user.create", group="admin", description="用户管理 - create"
        )
        mock_register.assert_any_call(
            "user.read", group="admin", description="用户管理 - read"
        )
        mock_register.assert_any_call(
            "user.update", group="admin", description="用户管理 - update"
        )
        mock_register.assert_any_call(
            "user.delete", group="admin", description="用户管理 - delete"
        )

    def test_register_crud_permissions_with_description(self):
        """测试带描述的CRUD权限注册"""
        mock_register = Mock()
        register_crud_permissions("server", mock_register, description="服务器管理")

        # 验证描述被正确传递
        mock_register.assert_any_call(
            "server.create", group=None, description="服务器管理 - create"
        )


class TestCreatePermissionPattern:
    """测试权限模式创建函数"""

    def test_create_permission_pattern_basic(self):
        """测试基础权限模式创建"""
        template = create_permission_pattern("admin", ["user.manage", "server.manage"])
        assert template.name == "admin"
        assert template.permissions == ["user.manage", "server.manage"]
        assert template.description == ""

    def test_create_permission_pattern_with_description(self):
        """测试带描述的权限模式创建"""
        template = create_permission_pattern(
            "admin", ["user.manage"], "admin", "管理员权限"
        )
        assert template.name == "admin"
        assert template.permissions == ["user.manage"]
        assert template.description == "管理员权限"

    def test_create_permission_pattern_empty_permissions(self):
        """测试空权限列表的模式创建"""
        template = create_permission_pattern("empty", [])
        assert template.name == "empty"
        assert template.permissions == []


class TestRegisterPermissionPattern:
    """测试权限模式注册函数"""

    def test_register_permission_pattern_without_register(self):
        """测试无注册函数的权限模式注册"""
        template = create_permission_pattern("admin", ["user.manage", "server.manage"])
        result = register_permission_pattern(template)
        assert result == ["user.manage", "server.manage"]

    def test_register_permission_pattern_with_register(self):
        """测试有注册函数的权限模式注册"""
        template = create_permission_pattern("admin", ["user.manage", "server.manage"])
        mock_register = Mock()

        result = register_permission_pattern(template, mock_register, "admin")

        assert result == ["user.manage", "server.manage"]
        assert mock_register.call_count == 2
        mock_register.assert_any_call(
            "user.manage", group="admin", description=" - user.manage"
        )
        mock_register.assert_any_call(
            "server.manage", group="admin", description=" - server.manage"
        )


class TestCreatePermissionChain:
    """测试权限链创建函数"""

    def test_create_permission_chain_basic(self):
        """测试基础权限链创建"""
        chain = create_permission_chain(["user.read", "user.write"])
        assert chain.permissions == ["user.read", "user.write"]
        assert chain.op == "AND"
        assert chain.permission_checker is None

    def test_create_permission_chain_with_checker(self):
        """测试带检查器的权限链创建"""
        mock_checker = Mock()
        chain = create_permission_chain(["user.read"], "OR", mock_checker)
        assert chain.permissions == ["user.read"]
        assert chain.op == "OR"
        assert chain.permission_checker == mock_checker

    def test_create_permission_chain_different_op(self):
        """测试不同操作符的权限链创建"""
        chain = create_permission_chain(["user.read", "user.write"], "OR")
        assert chain.op == "OR"


class TestCreatePermissionGroup:
    """测试权限组创建函数"""

    def test_create_permission_group_basic(self):
        """测试基础权限组创建"""
        group = create_permission_group("admin", ["user.manage", "server.manage"])
        assert group.name == "admin"
        assert group.permissions == ["user.manage", "server.manage"]

    def test_create_permission_group_empty(self):
        """测试空权限组创建"""
        group = create_permission_group("empty")
        assert group.name == "empty"
        assert group.permissions == []


class TestCreatePermissionDecorator:
    """测试权限装饰器创建函数"""

    def test_create_permission_decorator_basic(self):
        """测试基础权限装饰器创建"""
        decorator = create_permission_decorator("user.read")
        assert callable(decorator)

    def test_create_permission_decorator_with_scope(self):
        """测试带作用域的权限装饰器创建"""
        decorator = create_permission_decorator("user.read", "server", "server_id")
        assert callable(decorator)

    def test_create_permission_decorator_with_resource_check(self):
        """测试带资源检查的权限装饰器创建"""
        mock_resource_check = Mock()
        decorator = create_permission_decorator(
            "user.read", resource_check=mock_resource_check
        )
        assert callable(decorator)

    def test_create_permission_decorator_usage(self):
        """测试权限装饰器的使用"""
        decorator = create_permission_decorator("user.read")

        @decorator
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"


class TestRequireCrudPermission:
    """测试CRUD权限装饰器创建函数"""

    def test_require_crud_permission_basic(self):
        """测试基础CRUD权限装饰器创建"""
        decorator = require_crud_permission("read", "user")
        assert callable(decorator)

    def test_require_crud_permission_with_scope(self):
        """测试带作用域的CRUD权限装饰器创建"""
        decorator = require_crud_permission("read", "user", "server", "server_id")
        assert callable(decorator)

    def test_require_crud_permission_with_resource_check(self):
        """测试带资源检查的CRUD权限装饰器创建"""
        mock_resource_check = Mock()
        decorator = require_crud_permission(
            "read", "user", resource_check=mock_resource_check
        )
        assert callable(decorator)

    def test_require_crud_permission_all_actions(self):
        """测试所有CRUD操作的权限装饰器创建"""
        actions = ["create", "read", "update", "delete"]
        for action in actions:
            decorator = require_crud_permission(action, "user")
            assert callable(decorator)

    def test_require_crud_permission_usage(self):
        """测试CRUD权限装饰器的使用"""
        decorator = require_crud_permission("read", "user")

        @decorator
        def get_user():
            return "user_data"

        result = get_user()
        assert result == "user_data"


class TestIntegration:
    """集成测试"""

    def test_crud_workflow(self):
        """测试CRUD工作流"""
        # 1. 创建CRUD权限
        crud_perms = create_crud_permissions("user")
        assert "create" in crud_perms
        assert "read" in crud_perms

        # 2. 注册CRUD权限
        mock_register = Mock()
        registered_perms = register_crud_permissions("user", mock_register)
        assert registered_perms == crud_perms
        assert mock_register.call_count == 4

    def test_pattern_workflow(self):
        """测试权限模式工作流"""
        # 1. 创建权限模式
        template = create_permission_pattern("admin", ["user.manage", "server.manage"])

        # 2. 注册权限模式
        mock_register = Mock()
        registered_perms = register_permission_pattern(template, mock_register)
        assert registered_perms == ["user.manage", "server.manage"]
        assert mock_register.call_count == 2

    def test_chain_workflow(self):
        """测试权限链工作流"""
        # 1. 创建权限链
        chain = create_permission_chain(["user.read", "user.write"], "AND")

        # 2. 设置权限检查器
        mock_checker = Mock(return_value=True)
        chain.set_permission_checker(mock_checker)

        # 3. 测试权限检查
        result = chain._check_permissions()
        assert result == True
        assert mock_checker.call_count == 2

    def test_group_workflow(self):
        """测试权限组工作流"""
        # 1. 创建权限组
        group = create_permission_group("admin", ["user.manage", "server.manage"])

        # 2. 添加权限到组
        group.add_permission("channel.manage")
        assert len(group.permissions) == 3

        # 3. 注册组权限
        mock_register = Mock()
        group.register_all(mock_register)
        assert mock_register.call_count == 3

    def test_decorator_workflow(self):
        """测试装饰器工作流"""
        # 1. 创建CRUD权限装饰器
        decorator = require_crud_permission("read", "user")

        # 2. 使用装饰器
        @decorator
        def get_user():
            return "user_data"

        # 3. 测试装饰器功能
        result = get_user()
        assert result == "user_data"


class TestFactoryFunctions:
    """测试工厂函数特性"""

    def test_factory_functions_are_pure(self):
        """测试工厂函数是纯函数"""
        # 相同的输入应该产生相同的输出
        result1 = create_crud_permissions("user")
        result2 = create_crud_permissions("user")
        assert result1 == result2

        template1 = create_permission_pattern("admin", ["user.manage"])
        template2 = create_permission_pattern("admin", ["user.manage"])
        assert template1.name == template2.name
        assert template1.permissions == template2.permissions

    def test_factory_functions_no_side_effects(self):
        """测试工厂函数无副作用"""
        # 创建权限组不应该影响其他操作
        group1 = create_permission_group("group1", ["perm1"])
        group2 = create_permission_group("group2", ["perm2"])

        assert group1.name == "group1"
        assert group2.name == "group2"
        assert group1.permissions == ["perm1"]
        assert group2.permissions == ["perm2"]

    def test_factory_functions_dependency_injection(self):
        """测试工厂函数的依赖注入"""
        # 测试依赖注入的正确性
        mock_register = Mock()
        mock_checker = Mock()

        # 创建带依赖注入的实例
        template = create_permission_pattern("test", ["perm1"])
        chain = create_permission_chain(["perm1"], "AND", mock_checker)

        # 验证依赖注入
        assert chain.permission_checker == mock_checker


if __name__ == "__main__":
    pytest.main([__file__])
