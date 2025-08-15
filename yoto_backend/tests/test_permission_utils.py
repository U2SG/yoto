"""
权限工具模块测试 - 纯工具层
测试无状态、无外部依赖的权限工具函数
"""

import pytest
from app.core.permission_utils import (
    validate_permission_structure,
    create_permission_key,
    batch_validate_permissions,
    create_permission_hash,
    merge_permission_sets,
    filter_permissions_by_group,
    get_permission_hierarchy,
)


class TestValidatePermissionStructure:
    """测试权限结构验证函数"""

    def test_valid_permission_structure(self):
        """测试有效的权限结构"""
        assert validate_permission_structure("user.read") == True
        assert validate_permission_structure("server.manage.users") == True
        assert validate_permission_structure("channel.send") == True
        assert validate_permission_structure("role.assign") == True

    def test_invalid_permission_structure(self):
        """测试无效的权限结构"""
        assert validate_permission_structure("user") == False  # 缺少action
        assert validate_permission_structure("") == False  # 空字符串
        assert validate_permission_structure("user.") == False  # 空action
        assert validate_permission_structure(".read") == False  # 空resource

    def test_special_characters(self):
        """测试特殊字符"""
        assert validate_permission_structure("user-read") == False  # 包含连字符
        assert validate_permission_structure("user.read.write") == True  # 多层结构
        assert validate_permission_structure("user123.read") == True  # 包含数字


class TestCreatePermissionKey:
    """测试权限键生成函数"""

    def test_basic_permission_key(self):
        """测试基础权限键"""
        assert create_permission_key("user.read") == "user.read"
        assert create_permission_key("server.manage") == "server.manage"

    def test_permission_key_with_scope(self):
        """测试带作用域的权限键"""
        assert create_permission_key("user.read", "server") == "user.read:server"
        assert (
            create_permission_key("server.manage", "channel") == "server.manage:channel"
        )

    def test_permission_key_with_scope_id(self):
        """测试带作用域ID的权限键"""
        assert (
            create_permission_key("user.read", "server", 123) == "user.read:server:123"
        )
        assert (
            create_permission_key("server.manage", "channel", 456)
            == "server.manage:channel:456"
        )

    def test_permission_key_with_scope_and_id(self):
        """测试带作用域和ID的权限键"""
        result = create_permission_key("user.read", "server", 123)
        assert result == "user.read:server:123"

    def test_permission_key_without_scope(self):
        """测试不带作用域的权限键"""
        assert create_permission_key("user.read", scope_id=123) == "user.read:123"


class TestBatchValidatePermissions:
    """测试批量权限验证函数"""

    def test_batch_validate_valid_permissions(self):
        """测试批量验证有效权限"""
        permissions = ["user.read", "server.manage", "channel.send"]
        result = batch_validate_permissions(permissions)
        expected = {"user.read": True, "server.manage": True, "channel.send": True}
        assert result == expected

    def test_batch_validate_mixed_permissions(self):
        """测试批量验证混合权限"""
        permissions = ["user.read", "user", "server.manage", "channel"]
        result = batch_validate_permissions(permissions)
        expected = {
            "user.read": True,
            "user": False,
            "server.manage": True,
            "channel": False,
        }
        assert result == expected

    def test_batch_validate_empty_list(self):
        """测试批量验证空列表"""
        result = batch_validate_permissions([])
        assert result == {}

    def test_batch_validate_duplicate_permissions(self):
        """测试批量验证重复权限"""
        permissions = ["user.read", "user.read", "server.manage"]
        result = batch_validate_permissions(permissions)
        expected = {"user.read": True, "server.manage": True}
        assert result == expected


class TestCreatePermissionHash:
    """测试权限哈希生成函数"""

    def test_create_permission_hash(self):
        """测试权限哈希生成"""
        permissions = {"user.read", "user.write", "server.manage"}
        hash_result = create_permission_hash(permissions)

        # 验证哈希是字符串
        assert isinstance(hash_result, str)
        # 验证哈希长度（MD5是32位十六进制）
        assert len(hash_result) == 32
        # 验证哈希只包含十六进制字符
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_create_permission_hash_deterministic(self):
        """测试权限哈希的确定性"""
        permissions1 = {"user.read", "user.write"}
        permissions2 = {"user.write", "user.read"}  # 顺序不同

        hash1 = create_permission_hash(permissions1)
        hash2 = create_permission_hash(permissions2)

        # 相同权限集合应该产生相同的哈希
        assert hash1 == hash2

    def test_create_permission_hash_empty_set(self):
        """测试空权限集合的哈希"""
        hash_result = create_permission_hash(set())
        assert isinstance(hash_result, str)
        assert len(hash_result) == 32

    def test_create_permission_hash_single_permission(self):
        """测试单个权限的哈希"""
        permissions = {"user.read"}
        hash_result = create_permission_hash(permissions)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 32


class TestMergePermissionSets:
    """测试权限集合合并函数"""

    def test_merge_permission_sets(self):
        """测试权限集合合并"""
        set1 = {"user.read", "user.write"}
        set2 = {"server.manage", "channel.send"}
        set3 = {"user.read", "role.assign"}  # 包含重复权限

        result = merge_permission_sets(set1, set2, set3)
        expected = {
            "user.read",
            "user.write",
            "server.manage",
            "channel.send",
            "role.assign",
        }
        assert result == expected

    def test_merge_permission_sets_empty(self):
        """测试合并空集合"""
        result = merge_permission_sets(set(), set(), set())
        assert result == set()

    def test_merge_permission_sets_single(self):
        """测试合并单个集合"""
        permissions = {"user.read", "user.write"}
        result = merge_permission_sets(permissions)
        assert result == permissions

    def test_merge_permission_sets_no_duplicates(self):
        """测试合并无重复权限"""
        set1 = {"user.read"}
        set2 = {"user.write"}
        set3 = {"server.manage"}

        result = merge_permission_sets(set1, set2, set3)
        expected = {"user.read", "user.write", "server.manage"}
        assert result == expected


class TestFilterPermissionsByGroup:
    """测试权限按组过滤函数"""

    def test_filter_permissions_by_group(self):
        """测试按组过滤权限"""
        permissions = {
            "user.read",
            "user.write",
            "server.manage",
            "server.invite",
            "channel.send",
        }
        result = filter_permissions_by_group(permissions, "user")
        expected = {"user.read", "user.write"}
        assert result == expected

    def test_filter_permissions_by_group_server(self):
        """测试按server组过滤权限"""
        permissions = {"user.read", "server.manage", "server.invite", "channel.send"}
        result = filter_permissions_by_group(permissions, "server")
        expected = {"server.manage", "server.invite"}
        assert result == expected

    def test_filter_permissions_by_group_no_match(self):
        """测试按组过滤无匹配权限"""
        permissions = {"user.read", "user.write"}
        result = filter_permissions_by_group(permissions, "server")
        assert result == set()

    def test_filter_permissions_by_group_empty_set(self):
        """测试过滤空权限集合"""
        result = filter_permissions_by_group(set(), "user")
        assert result == set()

    def test_filter_permissions_by_group_partial_match(self):
        """测试部分匹配的权限过滤"""
        permissions = {"user.read", "user.read.write", "userwrite"}  # 最后一个不匹配
        result = filter_permissions_by_group(permissions, "user")
        expected = {"user.read", "user.read.write"}
        assert result == expected


class TestGetPermissionHierarchy:
    """测试权限层次结构函数"""

    def test_get_permission_hierarchy_simple(self):
        """测试简单权限层次"""
        result = get_permission_hierarchy("user.read")
        expected = ["user", "user.read"]
        assert result == expected

    def test_get_permission_hierarchy_complex(self):
        """测试复杂权限层次"""
        result = get_permission_hierarchy("server.manage.users")
        expected = ["server", "server.manage", "server.manage.users"]
        assert result == expected

    def test_get_permission_hierarchy_three_levels(self):
        """测试三级权限层次"""
        result = get_permission_hierarchy("channel.send.message")
        expected = ["channel", "channel.send", "channel.send.message"]
        assert result == expected

    def test_get_permission_hierarchy_single_level(self):
        """测试单级权限层次"""
        result = get_permission_hierarchy("user")
        expected = ["user"]
        assert result == expected

    def test_get_permission_hierarchy_with_numbers(self):
        """测试包含数字的权限层次"""
        result = get_permission_hierarchy("user123.read456")
        expected = ["user123", "user123.read456"]
        assert result == expected


class TestIntegration:
    """集成测试"""

    def test_workflow_with_multiple_functions(self):
        """测试多个函数的协作工作流"""
        # 1. 验证权限结构
        permissions = ["user.read", "user.write", "server.manage", "invalid"]
        valid_permissions = [p for p in permissions if validate_permission_structure(p)]
        assert valid_permissions == ["user.read", "user.write", "server.manage"]

        # 2. 创建权限集合
        permission_set = set(valid_permissions)

        # 3. 按组过滤
        user_permissions = filter_permissions_by_group(permission_set, "user")
        server_permissions = filter_permissions_by_group(permission_set, "server")

        assert user_permissions == {"user.read", "user.write"}
        assert server_permissions == {"server.manage"}

        # 4. 合并权限
        all_permissions = merge_permission_sets(user_permissions, server_permissions)
        assert all_permissions == {"user.read", "user.write", "server.manage"}

        # 5. 创建哈希
        hash_result = create_permission_hash(all_permissions)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 32

        # 6. 获取层次结构
        for permission in all_permissions:
            hierarchy = get_permission_hierarchy(permission)
            assert len(hierarchy) >= 1
            assert hierarchy[-1] == permission

    def test_permission_key_workflow(self):
        """测试权限键生成工作流"""
        # 1. 验证权限结构
        permission = "user.read"
        assert validate_permission_structure(permission) == True

        # 2. 创建不同作用域的权限键
        basic_key = create_permission_key(permission)
        scoped_key = create_permission_key(permission, "server", 123)

        assert basic_key == "user.read"
        assert scoped_key == "user.read:server:123"

        # 3. 验证键的唯一性
        assert basic_key != scoped_key


if __name__ == "__main__":
    pytest.main([__file__])
