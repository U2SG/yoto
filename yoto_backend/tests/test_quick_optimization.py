"""
快速优化测试
避免长时间运行的测试，专注于基础功能验证
"""

import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 检查模块是否可用
try:
    from app.core.advanced_optimization import (
        ADVANCED_OPTIMIZATION_CONFIG,
        OptimizedDistributedLock,
        _advanced_optimizer,
    )

    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"模块导入失败: {e}")
    MODULES_AVAILABLE = False


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
class TestQuickOptimization:
    """快速优化测试"""

    def test_config_loading(self):
        """测试配置加载"""
        assert ADVANCED_OPTIMIZATION_CONFIG is not None
        assert "connection_pool_size" in ADVANCED_OPTIMIZATION_CONFIG
        assert "lock_timeout" in ADVANCED_OPTIMIZATION_CONFIG

        print(f"✓ 配置加载成功")
        print(f"  连接池大小: {ADVANCED_OPTIMIZATION_CONFIG['connection_pool_size']}")
        print(f"  锁超时时间: {ADVANCED_OPTIMIZATION_CONFIG['lock_timeout']}秒")

    def test_optimizer_initialization(self):
        """测试优化器初始化"""
        assert _advanced_optimizer is not None
        assert hasattr(_advanced_optimizer, "preload_cache")
        assert hasattr(_advanced_optimizer, "_stats")

        print(f"✓ 优化器初始化成功")
        print(f"  预加载缓存: {len(_advanced_optimizer.preload_cache)} 项")

    def test_lock_creation(self):
        """测试锁创建（不实际获取锁）"""
        lock = OptimizedDistributedLock("test_lock", timeout=1.0)
        assert lock is not None
        assert lock.key == "adv_lock:test_lock"
        assert lock.timeout == 1.0

        print(f"✓ 锁创建成功")
        print(f"  锁键: {lock.key}")
        print(f"  超时时间: {lock.timeout}秒")

    def test_config_values(self):
        """测试配置值"""
        config = ADVANCED_OPTIMIZATION_CONFIG

        # 验证关键配置
        assert config["connection_pool_size"] >= 100
        assert config["lock_timeout"] <= 2.0
        assert config["batch_size"] >= 200

        print(f"✓ 配置值验证成功")
        print(f"  连接池大小: {config['connection_pool_size']} (>= 100)")
        print(f"  锁超时时间: {config['lock_timeout']}秒 (<= 2.0)")
        print(f"  批量大小: {config['batch_size']} (>= 200)")


if __name__ == "__main__":
    print("开始快速优化测试...")

    if MODULES_AVAILABLE:
        print("✓ 模块导入成功")

        # 运行快速测试
        test = TestQuickOptimization()
        test.test_config_loading()
        test.test_optimizer_initialization()
        test.test_lock_creation()
        test.test_config_values()

        print("✓ 所有快速测试通过")
    else:
        print("✗ 模块导入失败")
        print("请检查模块依赖和导入路径")
