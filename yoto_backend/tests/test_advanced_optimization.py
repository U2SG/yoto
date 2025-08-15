"""
高级优化模块测试
验证修复后的代码是否正常工作
"""

import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 检查高级优化模块是否存在
try:
    from app.core.advanced_optimization import (
        ADVANCED_OPTIMIZATION_CONFIG,
        OptimizedDistributedLock,
        advanced_get_permissions_from_cache,
        advanced_set_permissions_to_cache,
        advanced_batch_get_permissions,
        advanced_batch_set_permissions,
        advanced_invalidate_user_permissions,
        get_advanced_performance_stats,
        _advanced_optimizer,
    )

    ADVANCED_OPTIMIZATION_AVAILABLE = True
except ImportError as e:
    print(f"高级优化模块导入失败: {e}")
    ADVANCED_OPTIMIZATION_AVAILABLE = False


@pytest.mark.skipif(not ADVANCED_OPTIMIZATION_AVAILABLE, reason="高级优化模块不可用")
class TestAdvancedOptimization:
    """高级优化模块测试"""

    def test_config_loading(self):
        """测试配置加载"""
        assert ADVANCED_OPTIMIZATION_CONFIG is not None
        assert "connection_pool_size" in ADVANCED_OPTIMIZATION_CONFIG
        assert "lock_timeout" in ADVANCED_OPTIMIZATION_CONFIG
        assert "batch_size" in ADVANCED_OPTIMIZATION_CONFIG

        print(f"配置加载成功:")
        print(f"  连接池大小: {ADVANCED_OPTIMIZATION_CONFIG['connection_pool_size']}")
        print(f"  锁超时时间: {ADVANCED_OPTIMIZATION_CONFIG['lock_timeout']}秒")
        print(f"  批量大小: {ADVANCED_OPTIMIZATION_CONFIG['batch_size']}")

    def test_optimized_distributed_lock_creation(self):
        """测试优化的分布式锁创建"""
        # 创建应用上下文
        from app import create_app

        app = create_app("testing")

        with app.app_context():
            lock = OptimizedDistributedLock("test_lock", timeout=0.5)  # 减少超时时间
            assert lock is not None
            assert lock.key == "adv_lock:test_lock"
            assert lock.timeout == 0.5

            print(f"优化的分布式锁创建成功:")
            print(f"  锁键: {lock.key}")
            print(f"  超时时间: {lock.timeout}秒")

    def test_advanced_optimizer_initialization(self):
        """测试高级优化器初始化"""
        assert _advanced_optimizer is not None
        assert hasattr(_advanced_optimizer, "preload_cache")
        assert hasattr(_advanced_optimizer, "_stats")

        print(f"高级优化器初始化成功:")
        print(f"  预加载缓存: {len(_advanced_optimizer.preload_cache)} 项")
        print(f"  统计信息: {len(_advanced_optimizer._stats)} 项")

    def test_advanced_performance_stats(self):
        """测试高级性能统计"""
        # 创建应用上下文
        from app import create_app

        app = create_app("testing")

        with app.app_context():
            stats = get_advanced_performance_stats()
            assert stats is not None
            assert "optimization_config" in stats
            assert "advanced_stats" in stats

            print(f"高级性能统计获取成功:")
            print(f"  配置项数: {len(stats['optimization_config'])}")
            print(f"  统计项数: {len(stats['advanced_stats'])}")

    def test_basic_function_imports(self):
        """测试基础函数导入"""
        # 测试函数是否存在
        assert callable(advanced_get_permissions_from_cache)
        assert callable(advanced_set_permissions_to_cache)
        assert callable(advanced_batch_get_permissions)
        assert callable(advanced_batch_set_permissions)
        assert callable(advanced_invalidate_user_permissions)

        print(f"所有高级优化函数导入成功")

    def test_config_optimization_values(self):
        """测试配置优化值"""
        config = ADVANCED_OPTIMIZATION_CONFIG

        # 验证连接优化
        assert config["connection_pool_size"] >= 100
        assert config["socket_timeout"] <= 0.5
        assert config["health_check_interval"] <= 15

        # 验证锁优化
        assert config["lock_timeout"] <= 2.0
        assert config["lock_retry_interval"] <= 0.02
        assert config["lock_retry_count"] <= 2

        # 验证批量操作优化
        assert config["batch_size"] >= 200
        assert config["max_concurrent_batches"] >= 10

        print(f"配置优化值验证成功:")
        print(f"  连接池大小: {config['connection_pool_size']} (>= 100)")
        print(f"  锁超时时间: {config['lock_timeout']}秒 (<= 2.0)")
        print(f"  批量大小: {config['batch_size']} (>= 200)")


if __name__ == "__main__":
    # 运行基本测试
    print("开始高级优化模块测试...")

    if ADVANCED_OPTIMIZATION_AVAILABLE:
        print("✓ 高级优化模块导入成功")

        # 测试配置
        test = TestAdvancedOptimization()
        test.test_config_loading()
        test.test_optimized_distributed_lock_creation()
        test.test_advanced_optimizer_initialization()
        test.test_advanced_performance_stats()
        test.test_basic_function_imports()
        test.test_config_optimization_values()

        print("✓ 所有测试通过")
    else:
        print("✗ 高级优化模块导入失败")
        print("请检查模块依赖和导入路径")
