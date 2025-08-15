"""
权限抽象模块测试 - 高级抽象层
测试权限模板、权限链、权限组等高级抽象概念
"""

import pytest
from unittest.mock import Mock, patch
from app.core.permission_abstractions import (
    PermissionTemplate,
    PermissionChain,
    PermissionGroup,
    PERMISSION_PATTERNS,
    CRUD_TEMPLATE,
    MESSAGE_TEMPLATE,
    SERVER_TEMPLATE,
    CHANNEL_TEMPLATE,
    ROLE_TEMPLATE,
    create_permission_template,
    create_permission_chain,
    create_permission_group,
)


class TestPermissionTemplate:
    """测试权限模板类"""

    def test_permission_template_creation(self):
        """测试权限模板创建"""
        template = PermissionTemplate("test", ["user.read", "user.write"], "测试模板")
        assert template.name == "test"
        assert template.permissions == ["user.read", "user.write"]
        assert template.description == "测试模板"

    def test_register_all_without_checker(self):
        """测试无权限检查器的注册"""
        template = PermissionTemplate("test", ["user.read", "user.write"])
        result = template.register_all()
        assert result == ["user.read", "user.write"]

    def test_register_all_with_checker(self):
        """测试有权限检查器的注册"""
        mock_checker = Mock()
        template = PermissionTemplate("test", ["user.read", "user.write"])

        result = template.register_all(mock_checker, "test_group")

        assert result == ["user.read", "user.write"]
        assert mock_checker.call_count == 2
        mock_checker.assert_any_call(
            "user.read", group="test_group", description=" - user.read"
        )
        mock_checker.assert_any_call(
            "user.write", group="test_group", description=" - user.write"
        )

    def test_validate_permissions(self):
        """测试权限验证"""
        template = PermissionTemplate("test", ["user.read", "invalid", "server.manage"])
        result = template.validate_permissions()
        expected = {"user.read": True, "invalid": False, "server.manage": True}
        assert result == expected


class TestPermissionChain:
    """测试权限链类"""

    def test_permission_chain_creation(self):
        """测试权限链创建"""
        chain = PermissionChain(["user.read", "user.write"], "AND")
        assert chain.permissions == ["user.read", "user.write"]
        assert chain.op == "AND"
        assert chain.permission_checker is None

    def test_permission_chain_with_checker(self):
        """测试带权限检查器的权限链"""
        mock_checker = Mock()
        chain = PermissionChain(["user.read"], "AND", mock_checker)
        assert chain.permission_checker == mock_checker

    def test_add_permission(self):
        """测试添加权限"""
        chain = PermissionChain(["user.read"])
        chain.add_permission("user.write")
        assert "user.write" in chain.permissions
        assert len(chain.permissions) == 2

    def test_remove_permission(self):
        """测试移除权限"""
        chain = PermissionChain(["user.read", "user.write"])
        chain.remove_permission("user.read")
        assert "user.read" not in chain.permissions
        assert "user.write" in chain.permissions

    def test_set_permission_checker(self):
        """测试设置权限检查器"""
        chain = PermissionChain(["user.read"])
        mock_checker = Mock()
        chain.set_permission_checker(mock_checker)
        assert chain.permission_checker == mock_checker

    def test_check_permissions_and_all_true(self):
        """测试AND操作，所有权限都通过"""
        mock_checker = Mock(side_effect=[True, True])
        chain = PermissionChain(["user.read", "user.write"], "AND", mock_checker)

        result = chain._check_permissions()
        assert result == True
        assert mock_checker.call_count == 2

    def test_check_permissions_and_one_false(self):
        """测试AND操作，一个权限失败"""
        mock_checker = Mock(side_effect=[True, False])
        chain = PermissionChain(["user.read", "user.write"], "AND", mock_checker)

        result = chain._check_permissions()
        assert result == False
        assert mock_checker.call_count == 2  # 短路求值，第二个调用后停止

    def test_check_permissions_or_one_true(self):
        """测试OR操作，一个权限通过"""
        mock_checker = Mock(side_effect=[False, True])
        chain = PermissionChain(["user.read", "user.write"], "OR", mock_checker)

        result = chain._check_permissions()
        assert result == True
        assert mock_checker.call_count == 2  # 短路求值，第二个调用后停止

    def test_check_permissions_or_all_false(self):
        """测试OR操作，所有权限都失败"""
        mock_checker = Mock(side_effect=[False, False])
        chain = PermissionChain(["user.read", "user.write"], "OR", mock_checker)

        result = chain._check_permissions()
        assert result == False
        assert mock_checker.call_count == 2

    def test_check_permissions_empty_list(self):
        """测试空权限列表"""
        chain = PermissionChain([], "AND")
        result = chain._check_permissions()
        assert result == True

    def test_check_permissions_exception_handling(self):
        """测试权限检查异常处理"""
        mock_checker = Mock(side_effect=Exception("权限检查出错"))
        chain = PermissionChain(["user.read"], "AND", mock_checker)

        result = chain._check_permissions()
        assert result == False

    def test_decorator_without_checker(self):
        """测试无权限检查器的装饰器"""
        chain = PermissionChain(["user.read"])

        @chain
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"

    def test_decorator_with_checker_success(self):
        """测试有权限检查器的装饰器 - 成功"""
        mock_checker = Mock(return_value=True)
        chain = PermissionChain(["user.read"], "AND", mock_checker)

        @chain
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"

    def test_decorator_with_checker_failure(self):
        """测试有权限检查器的装饰器 - 失败"""
        mock_checker = Mock(return_value=False)
        chain = PermissionChain(["user.read"], "AND", mock_checker)

        @chain
        def test_function():
            return "success"

        with patch("flask.jsonify") as mock_jsonify:
            # 模拟jsonify返回一个响应对象
            mock_response = Mock()
            mock_response.return_value = {"error": "权限不足"}
            mock_jsonify.return_value = mock_response

            result = test_function()
            # 检查是否调用了jsonify
            mock_jsonify.assert_called_once_with({"error": "权限不足"})


class TestPermissionGroup:
    """测试权限组类"""

    def test_permission_group_creation(self):
        """测试权限组创建"""
        group = PermissionGroup("test_group", ["user.read", "user.write"])
        assert group.name == "test_group"
        assert group.permissions == ["user.read", "user.write"]

    def test_permission_group_empty(self):
        """测试空权限组创建"""
        group = PermissionGroup("test_group")
        assert group.name == "test_group"
        assert group.permissions == []

    def test_add_permission(self):
        """测试添加权限"""
        group = PermissionGroup("test_group")
        group.add_permission("user.read")
        assert "user.read" in group.permissions

    def test_add_permission_duplicate(self):
        """测试添加重复权限"""
        group = PermissionGroup("test_group", ["user.read"])
        group.add_permission("user.read")  # 重复添加
        assert group.permissions.count("user.read") == 1  # 不重复

    def test_remove_permission(self):
        """测试移除权限"""
        group = PermissionGroup("test_group", ["user.read", "user.write"])
        group.remove_permission("user.read")
        assert "user.read" not in group.permissions
        assert "user.write" in group.permissions

    def test_remove_permission_not_exists(self):
        """测试移除不存在的权限"""
        group = PermissionGroup("test_group", ["user.read"])
        group.remove_permission("user.write")  # 不存在的权限
        assert group.permissions == ["user.read"]  # 无变化

    def test_register_all_without_checker(self):
        """测试无权限检查器的注册"""
        group = PermissionGroup("test_group", ["user.read", "user.write"])
        group.register_all()  # 不抛出异常

    def test_register_all_with_checker(self):
        """测试有权限检查器的注册"""
        mock_checker = Mock()
        group = PermissionGroup("test_group", ["user.read", "user.write"])

        group.register_all(mock_checker, "测试前缀")

        assert mock_checker.call_count == 2
        mock_checker.assert_any_call(
            "user.read", group="test_group", description="测试前缀 - user.read"
        )
        mock_checker.assert_any_call(
            "user.write", group="test_group", description="测试前缀 - user.write"
        )

    def test_get_permissions(self):
        """测试获取权限列表"""
        permissions = ["user.read", "user.write"]
        group = PermissionGroup("test_group", permissions)
        result = group.get_permissions()
        assert result == permissions
        assert result is not permissions  # 返回副本

    def test_validate_permissions(self):
        """测试权限验证"""
        group = PermissionGroup("test_group", ["user.read", "invalid", "server.manage"])
        result = group.validate_permissions()
        expected = {"user.read": True, "invalid": False, "server.manage": True}
        assert result == expected


class TestPermissionPatterns:
    """测试权限模式定义"""

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


class TestFactoryFunctions:
    """测试工厂函数"""

    def test_create_permission_template(self):
        """测试创建权限模板"""
        template = create_permission_template("test", ["user.read"], "测试")
        assert isinstance(template, PermissionTemplate)
        assert template.name == "test"
        assert template.permissions == ["user.read"]
        assert template.description == "测试"

    def test_create_permission_chain(self):
        """测试创建权限链"""
        chain = create_permission_chain(["user.read"], "AND")
        assert isinstance(chain, PermissionChain)
        assert chain.permissions == ["user.read"]
        assert chain.op == "AND"

    def test_create_permission_chain_with_checker(self):
        """测试创建带检查器的权限链"""
        mock_checker = Mock()
        chain = create_permission_chain(["user.read"], "OR", mock_checker)
        assert isinstance(chain, PermissionChain)
        assert chain.permission_checker == mock_checker
        assert chain.op == "OR"

    def test_create_permission_group(self):
        """测试创建权限组"""
        group = create_permission_group("test_group", ["user.read"])
        assert isinstance(group, PermissionGroup)
        assert group.name == "test_group"
        assert group.permissions == ["user.read"]

    def test_create_permission_group_empty(self):
        """测试创建空权限组"""
        group = create_permission_group("test_group")
        assert isinstance(group, PermissionGroup)
        assert group.name == "test_group"
        assert group.permissions == []


class TestIntegration:
    """集成测试"""

    def test_template_to_chain_workflow(self):
        """测试模板到权限链的工作流"""
        # 1. 创建模板
        template = create_permission_template("test", ["user.read", "user.write"])

        # 2. 验证模板权限
        validation = template.validate_permissions()
        assert validation["user.read"] == True
        assert validation["user.write"] == True

        # 3. 创建权限链
        mock_checker = Mock(side_effect=[True, True])
        chain = create_permission_chain(template.permissions, "AND", mock_checker)

        # 4. 测试权限链
        result = chain._check_permissions()
        assert result == True
        assert mock_checker.call_count == 2

    def test_group_to_template_workflow(self):
        """测试权限组到模板的工作流"""
        # 1. 创建权限组
        group = create_permission_group("test_group", ["user.read", "user.write"])

        # 2. 添加权限到组
        group.add_permission("server.manage")

        # 3. 从组创建模板
        template = create_permission_template("from_group", group.get_permissions())

        # 4. 验证模板
        validation = template.validate_permissions()
        assert validation["user.read"] == True
        assert validation["user.write"] == True
        assert validation["server.manage"] == True

    def test_dependency_injection_workflow(self):
        """测试依赖注入工作流"""
        # 1. 创建权限检查器
        mock_checker = Mock(return_value=True)

        # 2. 创建权限链并注入检查器
        chain = create_permission_chain(["user.read"], "AND")
        chain.set_permission_checker(mock_checker)

        # 3. 测试装饰器
        @chain
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"
        assert mock_checker.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__])
