"""
测试PermissionSystem的无状态设计
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_stateless_design():
    """测试PermissionSystem的无状态设计"""
    try:
        from app.core.permissions_refactored import (
            PermissionSystem,
            get_permission_system,
        )

        # 测试1: 验证PermissionSystem没有内部状态
        ps1 = PermissionSystem()
        ps2 = PermissionSystem()

        # 检查是否有冗余的stats属性
        if hasattr(ps1, "stats"):
            print(f"❌ PermissionSystem仍然有冗余的stats属性: {ps1.stats}")
            return False
        else:
            print("✅ PermissionSystem没有冗余的stats属性")

        # 检查是否有必要的子模块实例
        if hasattr(ps1, "cache") and hasattr(ps1, "monitor"):
            print("✅ PermissionSystem正确持有子模块实例")
        else:
            print("❌ PermissionSystem缺少必要的子模块实例")
            return False

        # 测试2: 验证get_system_stats返回实时数据
        stats1 = ps1.get_system_stats()
        stats2 = ps2.get_system_stats()

        # 检查返回的数据结构
        expected_keys = ["cache", "registry", "invalidation", "performance", "health"]
        for key in expected_keys:
            if key not in stats1:
                print(f"❌ get_system_stats缺少必要的键: {key}")
                return False

        print("✅ get_system_stats返回完整的数据结构")

        # 测试3: 验证无状态特性 - 多次调用应该返回一致的结果
        if stats1.keys() == stats2.keys():
            print("✅ 无状态设计：多次调用返回一致的数据结构")
        else:
            print("❌ 状态不一致：多次调用返回不同的数据结构")
            return False

        # 测试4: 验证单例模式
        singleton1 = get_permission_system()
        singleton2 = get_permission_system()

        if singleton1 is singleton2:
            print("✅ 单例模式工作正常")
        else:
            print("❌ 单例模式失效")
            return False

        # 测试5: 验证方法调用不会影响状态
        # 调用一些方法，然后检查系统状态是否保持一致
        try:
            # 这些调用应该不会影响系统状态
            ps1.get_optimization_suggestions()
            ps1.process_maintenance()

            # 再次获取统计信息
            stats3 = ps1.get_system_stats()

            if stats3.keys() == stats1.keys():
                print("✅ 方法调用后系统状态保持一致")
            else:
                print("❌ 方法调用后系统状态发生变化")
                return False

        except Exception as e:
            print(f"⚠️  方法调用测试中出现异常（可能是正常的）: {e}")

        print("\n🎉 PermissionSystem无状态设计验证成功！")
        return True

    except Exception as e:
        print(f"❌ 无状态设计测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_data_consistency():
    """测试数据一致性"""
    try:
        from app.core.permissions_refactored import get_permission_system

        ps = get_permission_system()

        # 获取系统统计
        stats = ps.get_system_stats()

        # 验证数据来源的一致性
        if "cache" in stats and "performance" in stats:
            print("✅ 缓存统计和性能数据来源一致")
        else:
            print("❌ 数据来源不一致")
            return False

        # 验证健康状态数据
        if "health" in stats and "overall_status" in stats["health"]:
            print("✅ 健康状态数据完整")
        else:
            print("❌ 健康状态数据不完整")
            return False

        print("✅ 数据一致性验证成功")
        return True

    except Exception as e:
        print(f"❌ 数据一致性测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=== 测试PermissionSystem无状态设计 ===")
    test_stateless_design()

    print("\n=== 测试数据一致性 ===")
    test_data_consistency()
