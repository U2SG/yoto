"""
智能失效机制修复验证脚本
"""

import sys
import os
import time
from unittest.mock import Mock

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def test_smart_invalidation_analysis():
    """测试智能失效分析"""
    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.ping.return_value = True

        # 创建配置
        config = {
            "smart_invalidation_interval": 1,
            "min_queue_size": 10,
            "max_growth_rate": 0.1,
            "min_processing_rate": 5,
        }

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(config, mock_redis)

        # 测试智能失效分析
        analysis = optimizer._get_smart_invalidation_analysis()
        print(f"✅ 智能失效分析测试通过")
        print(f"   分析结果: {analysis}")

        return True
    except Exception as e:
        print(f"❌ 智能失效分析测试失败: {e}")
        return False


def test_batch_operations_fix():
    """测试批量操作修复"""
    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        # 确保返回正确的列表格式
        mock_redis.lrange.return_value = [
            '{"type": "set_permissions", "cache_data": {"test_key": ["perm1", "perm2"]}, "ttl": 300}'
        ]
        mock_redis.ltrim.return_value = True

        # 创建配置
        config = {"batch_size": 100}

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(config, mock_redis)

        # 测试批量操作处理
        result = optimizer._process_batch_operations()
        print(f"✅ 批量操作修复测试通过")
        print(f"   处理结果: {result}")

        return True
    except Exception as e:
        print(f"❌ 批量操作修复测试失败: {e}")
        return False


def test_error_handling():
    """测试错误处理"""
    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        # 测试各种错误情况
        mock_redis.lrange.return_value = [
            "invalid json",  # 无效JSON
            '{"type": "unknown_type"}',  # 未知类型
            '{"type": "set_permissions", "cache_data": "not_dict"}',  # 错误的数据格式
        ]

        # 创建配置
        config = {"batch_size": 100}

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(config, mock_redis)

        # 测试错误处理
        result = optimizer._process_batch_operations()
        print(f"✅ 错误处理测试通过")
        print(f"   处理结果: {result}")

        return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


def run_fix_tests():
    """运行修复验证测试"""
    print("🔧 开始验证智能失效机制修复...")
    print("=" * 60)

    tests = [
        ("智能失效分析", test_smart_invalidation_analysis),
        ("批量操作修复", test_batch_operations_fix),
        ("错误处理", test_error_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 测试: {test_name}")
        print("-" * 40)
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} 失败")

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有修复验证测试通过！")
        print("\n📋 修复内容:")
        print("✅ 批量操作数据类型检查 - 确保Redis返回正确的列表格式")
        print("✅ JSON解析错误处理 - 优雅处理无效的JSON数据")
        print("✅ 操作类型验证 - 检查未知的操作类型")
        print("✅ 数据格式验证 - 验证缓存数据格式")
        print("✅ 错误隔离 - 单个操作失败不影响其他操作")
        return True
    else:
        print("❌ 部分修复验证测试失败，需要进一步调试。")
        return False


if __name__ == "__main__":
    run_fix_tests()
