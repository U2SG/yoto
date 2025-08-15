#!/usr/bin/env python3
"""
重构后权限系统验证测试
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_permission_system_imports():
    """测试重构后权限系统的导入"""
    try:
        # 测试主模块导入
        from app.core.permissions_refactored import (
            PermissionSystem,
            get_permission_system,
            check_permission,
            register_permission,
            require_permission_v2,
        )

        print("✓ 主模块导入成功")

        # 测试装饰器模块导入
        from app.core.permission_decorators import (
            require_permission,
            require_permission_v2,
            require_permissions_v2,
        )

        print("✓ 装饰器模块导入成功")

        # 测试缓存模块导入
        from app.core.permission_cache import (
            get_permissions_from_cache,
            set_permissions_to_cache,
        )

        print("✓ 缓存模块导入成功")

        # 测试查询模块导入
        from app.core.permission_queries import optimized_single_user_query_v3

        print("✓ 查询模块导入成功")

        # 测试注册模块导入
        from app.core.permission_registry import (
            register_permission_v2,
            register_role_v2,
        )

        print("✓ 注册模块导入成功")

        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_permission_system_functionality():
    """测试权限系统基本功能"""
    try:
        # 获取权限系统实例
        from app.core.permissions_refactored import get_permission_system

        permission_system = get_permission_system()

        # 测试权限注册
        permission_system.register_permission(
            name="test.permission", group="test", description="测试权限"
        )
        print("✓ 权限注册功能正常")

        # 测试获取系统统计
        stats = permission_system.get_system_stats()
        print("✓ 系统统计功能正常")

        return True
    except Exception as e:
        print(f"✗ 功能测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=== 重构后权限系统验证测试 ===")

    # 测试导入
    if not test_permission_system_imports():
        return False

    # 测试功能
    if not test_permission_system_functionality():
        return False

    print("\n✅ 所有测试通过，重构后的权限系统工作正常！")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
