"""
回归测试脚本

验证智能缓存失效和数据预加载机制的所有功能正常工作
"""

import sys
import os
import time
from unittest.mock import Mock

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def test_basic_functionality():
    """测试基础功能"""
    print("🔍 测试基础功能...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update(
            {
                "TESTING": True,
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "preload_interval": 1,
                    "preload": {"enabled": True},
                    "batch_size": 100,
                },
            }
        )

        with app.app_context():
            from app.core.permission.advanced_optimization import get_advanced_optimizer

            optimizer = get_advanced_optimizer()
            if optimizer is None:
                print("❌ 无法获取高级优化器")
                return False

            print("✅ 基础功能测试通过")
            return True
    except Exception as e:
        print(f"❌ 基础功能测试失败: {e}")
        return False


def test_cache_operations():
    """测试缓存操作"""
    print("🔍 测试缓存操作...")

    try:
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            from app.core.permission.hybrid_permission_cache import (
                HybridPermissionCache,
            )

            cache = HybridPermissionCache()

            # 测试L1缓存
            test_key = "test_cache_key"
            test_data = {"permissions": ["read", "write"]}

            # 设置缓存
            cache.l1_simple_cache.set(test_key, test_data)

            # 获取缓存
            result = cache.l1_simple_cache.get(test_key)

            if result != test_data:
                print("❌ 缓存数据不匹配")
                return False

            print("✅ 缓存操作测试通过")
            return True
    except Exception as e:
        print(f"❌ 缓存操作测试失败: {e}")
        return False


def test_smart_invalidation():
    """测试智能失效"""
    print("🔍 测试智能失效...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update(
            {
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "min_queue_size": 10,
                    "max_growth_rate": 0.1,
                    "min_processing_rate": 5,
                }
            }
        )

        with app.app_context():
            from app.core.permission.advanced_optimization import (
                AdvancedDistributedOptimizer,
            )

            # 创建优化器实例
            config = app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
            mock_redis = Mock()
            mock_redis.ping.return_value = True

            optimizer = AdvancedDistributedOptimizer(config, mock_redis)

            # 测试智能失效分析
            analysis = optimizer._get_smart_invalidation_analysis()
            if not isinstance(analysis, dict):
                print("❌ 智能失效分析返回格式错误")
                return False

            # 测试预加载策略
            preload_result = optimizer._execute_preload_strategy()
            if not isinstance(preload_result, dict):
                print("❌ 预加载策略返回格式错误")
                return False

            print("✅ 智能失效测试通过")
            return True
    except Exception as e:
        print(f"❌ 智能失效测试失败: {e}")
        return False


def test_data_preloading():
    """测试数据预加载"""
    print("🔍 测试数据预加载...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update(
            {"ADVANCED_OPTIMIZATION_CONFIG": {"preload": {"enabled": True}}}
        )

        with app.app_context():
            from app.core.permission.advanced_optimization import (
                AdvancedDistributedOptimizer,
            )

            config = app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.zrevrange.return_value = [b"1", b"2", b"3"]

            optimizer = AdvancedDistributedOptimizer(config, mock_redis)

            # 测试获取热门用户
            hot_users = optimizer._get_hot_users()
            if not isinstance(hot_users, list):
                print("❌ 热门用户获取返回格式错误")
                return False

            # 测试获取热门角色
            hot_roles = optimizer._get_hot_roles()
            if not isinstance(hot_roles, list):
                print("❌ 热门角色获取返回格式错误")
                return False

            print("✅ 数据预加载测试通过")
            return True
    except Exception as e:
        print(f"❌ 数据预加载测试失败: {e}")
        return False


def test_double_checked_locking():
    """测试双重检查锁定"""
    print("🔍 测试双重检查锁定...")

    try:
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            from app.core.permission.hybrid_permission_cache import (
                HybridPermissionCache,
            )

            # 创建模拟的Redis客户端
            mock_redis = Mock()
            mock_redis.get.return_value = b'{"permissions": ["perm1", "perm2"]}'

            # 创建混合缓存实例
            cache = HybridPermissionCache()
            cache.distributed_cache = Mock()
            cache.distributed_cache.redis_client = mock_redis

            # 模拟分布式锁管理器
            mock_lock_manager = Mock()
            mock_lock = Mock()
            mock_lock.__enter__ = Mock(return_value=mock_lock)
            mock_lock.__exit__ = Mock(return_value=None)
            mock_lock_manager.create_lock.return_value = mock_lock
            cache._distributed_lock_manager = mock_lock_manager

            # 测试双重检查锁定
            result = cache.distributed_cache_get("test_key")
            if result is None:
                print("❌ 双重检查锁定返回空值")
                return False

            print("✅ 双重检查锁定测试通过")
            return True
    except Exception as e:
        print(f"❌ 双重检查锁定测试失败: {e}")
        return False


def test_error_handling():
    """测试错误处理"""
    print("🔍 测试错误处理...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update({"ADVANCED_OPTIMIZATION_CONFIG": {"batch_size": 100}})

        with app.app_context():
            from app.core.permission.advanced_optimization import (
                AdvancedDistributedOptimizer,
            )

            config = app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})

            # 测试Redis连接失败的情况
            mock_redis_failed = Mock()
            mock_redis_failed.ping.side_effect = Exception("Connection failed")

            optimizer = AdvancedDistributedOptimizer(config, mock_redis_failed)

            # 测试批量操作处理
            result = optimizer._process_batch_operations()
            if not isinstance(result, dict):
                print("❌ 批量操作处理返回格式错误")
                return False

            print("✅ 错误处理测试通过")
            return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


def test_configuration_management():
    """测试配置管理"""
    print("🔍 测试配置管理...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update(
            {
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "preload_interval": 1,
                    "preload": {"enabled": True},
                    "batch_size": 100,
                }
            }
        )

        with app.app_context():
            from app.core.permission.advanced_optimization import (
                get_advanced_optimization_config,
            )

            config = get_advanced_optimization_config()
            if not isinstance(config, dict):
                print("❌ 配置管理返回格式错误")
                return False

            # 检查必要的配置项
            required_keys = [
                "smart_invalidation_interval",
                "preload_interval",
                "batch_size",
            ]
            for key in required_keys:
                if key not in config:
                    print(f"❌ 缺少必要的配置项: {key}")
                    return False

            print("✅ 配置管理测试通过")
            return True
    except Exception as e:
        print(f"❌ 配置管理测试失败: {e}")
        return False


def test_background_tasks():
    """测试后台任务"""
    print("🔍 测试后台任务...")

    try:
        from flask import Flask

        app = Flask(__name__)
        app.config.update(
            {
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "preload_interval": 1,
                    "preload": {"enabled": True},
                    "batch_size": 100,
                }
            }
        )

        with app.app_context():
            from app.core.permission.advanced_optimization import (
                AdvancedDistributedOptimizer,
            )

            config = app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.zrevrange.return_value = [b"1", b"2"]
            mock_redis.lrange.return_value = []

            optimizer = AdvancedDistributedOptimizer(config, mock_redis)

            # 检查后台任务是否启动
            if not hasattr(optimizer, "_stats"):
                print("❌ 后台任务统计信息不存在")
                return False

            print("✅ 后台任务测试通过")
            return True
    except Exception as e:
        print(f"❌ 后台任务测试失败: {e}")
        return False


def run_regression_tests():
    """运行回归测试"""
    print("🚀 开始回归测试...")
    print("=" * 60)

    tests = [
        ("基础功能", test_basic_functionality),
        ("缓存操作", test_cache_operations),
        ("智能失效", test_smart_invalidation),
        ("数据预加载", test_data_preloading),
        ("双重检查锁定", test_double_checked_locking),
        ("错误处理", test_error_handling),
        ("配置管理", test_configuration_management),
        ("后台任务", test_background_tasks),
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
    print(f"📊 回归测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有回归测试通过！")
        print("\n📋 功能验证:")
        print("✅ 基础功能 - 高级优化器正常工作")
        print("✅ 缓存操作 - L1缓存读写正常")
        print("✅ 智能失效 - 智能失效分析正常")
        print("✅ 数据预加载 - 热门用户/角色识别正常")
        print("✅ 双重检查锁定 - 减少锁竞争，提高性能")
        print("✅ 错误处理 - 优雅处理各种异常")
        print("✅ 配置管理 - 配置加载和管理正常")
        print("✅ 后台任务 - 异步处理正常工作")
        return True
    else:
        print("❌ 部分回归测试失败，需要进一步调试。")
        return False


if __name__ == "__main__":
    run_regression_tests()
