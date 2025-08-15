"""
测试循环依赖修复
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_circular_dependency_fix():
    """测试循环依赖是否已经解决"""
    try:
        # 测试主模块导入
        from app.core.permissions_refactored import (
            PermissionSystem,
            get_permission_system,
        )

        print("✅ 主模块导入成功")

        # 测试子模块导入
        from app.core.permission_registry import register_permission, register_role

        print("✅ 权限注册模块导入成功")

        from app.core.permission_decorators import (
            require_permission,
            require_permission_v2,
        )

        print("✅ 权限装饰器模块导入成功")

        from app.core.hybrid_permission_cache import get_hybrid_cache

        print("✅ 混合缓存模块导入成功")

        from app.core.permission_monitor import get_permission_monitor

        print("✅ 权限监控模块导入成功")

        # 测试实例化
        ps = PermissionSystem()
        print("✅ 权限系统实例化成功")

        # 测试便捷函数
        from app.core.permissions_refactored import register_permission_convenience

        result = register_permission_convenience(
            "test_permission", "test_group", "测试权限"
        )
        print("✅ 便捷函数调用成功")

        print("\n🎉 循环依赖问题已解决！")
        return True

    except Exception as e:
        print(f"❌ 循环依赖问题仍然存在: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_circular_dependency_fix()
