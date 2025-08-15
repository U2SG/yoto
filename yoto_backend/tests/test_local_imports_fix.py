"""
测试局部导入问题修复
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_local_imports_fix():
    """测试局部导入问题是否已经解决"""
    try:
        # 测试主模块导入 - 应该没有局部导入
        from app.core.permissions_refactored import (
            PermissionSystem,
            get_permission_system,
            register_permission_convenience,
            register_role_convenience,
            assign_permissions_to_role,
            assign_roles_to_user,
        )

        print("✅ 主模块导入成功，无局部导入")

        # 测试子模块导入
        from app.core.permission_registry import register_permission, register_role

        print("✅ 权限注册模块导入成功")

        from app.core.permission_decorators import require_permission

        print("✅ 权限装饰器模块导入成功")

        from app.core.hybrid_permission_cache import get_hybrid_cache

        print("✅ 混合缓存模块导入成功")

        from app.core.permission_monitor import get_permission_monitor

        print("✅ 权限监控模块导入成功")

        # 测试实例化
        ps = PermissionSystem()
        print("✅ 权限系统实例化成功")

        # 测试便捷函数调用
        result = register_permission_convenience(
            "test_permission", "test_group", "测试权限"
        )
        print("✅ 便捷函数调用成功")

        # 测试所有导入都在模块顶部
        import inspect

        source = inspect.getsource(sys.modules["app.core.permissions_refactored"])

        # 检查是否有局部导入
        lines = source.split("\n")
        local_imports = []
        for i, line in enumerate(lines):
            if "from ." in line and "import" in line and "as" in line:
                local_imports.append(f"Line {i+1}: {line.strip()}")

        if local_imports:
            print(f"⚠️  发现局部导入:")
            for imp in local_imports:
                print(f"   {imp}")
        else:
            print("✅ 没有发现局部导入")

        print("\n🎉 局部导入问题已解决！")
        return True

    except Exception as e:
        print(f"❌ 局部导入问题仍然存在: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_local_imports_fix()
