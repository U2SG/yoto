"""
测试哈希标签的实现

验证所有Redis键名都已正确使用哈希标签，
确保在Redis集群环境中能正确执行多键操作。
"""

import unittest
from unittest.mock import patch, MagicMock
import redis
import pytest
from app.core.permission.permission_resilience import (
    ResilienceController,
    CircuitBreaker,
    RateLimiter,
    Bulkhead,
)
from app.core.permission.hybrid_permission_cache import (
    HybridPermissionCache,
    _make_perm_cache_key,
)


class TestHashTags(unittest.TestCase):
    """测试哈希标签的实现"""

    def test_resilience_controller_keys(self):
        """测试韧性控制器的键名是否使用哈希标签"""
        self.assertEqual(
            ResilienceController.CIRCUIT_BREAKER_KEY, "resilience:{circuit_breaker}"
        )
        self.assertEqual(ResilienceController.RATE_LIMIT_KEY, "resilience:{rate_limit}")
        self.assertEqual(
            ResilienceController.DEGRADATION_KEY, "resilience:{degradation}"
        )
        self.assertEqual(ResilienceController.BULKHEAD_KEY, "resilience:{bulkhead}")
        self.assertEqual(
            ResilienceController.GLOBAL_SWITCH_KEY, "resilience:{global_switch}"
        )
        self.assertEqual(
            ResilienceController.CONFIG_OVERRIDES_KEY, "resilience:{config_overrides}"
        )

    @patch("redis.Redis")
    def test_circuit_breaker_lua_script(self, mock_redis):
        """测试熔断器的Lua脚本是否使用哈希标签"""
        # 创建模拟对象
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.register_script.return_value = MagicMock()

        # 创建控制器
        controller = ResilienceController(mock_redis_instance)

        # 创建熔断器
        breaker = CircuitBreaker("test_breaker", controller)

        # 断言脚本中使用了哈希标签
        lua_script = CircuitBreaker.EXECUTE_OR_RECORD_FAILURE_SCRIPT
        self.assertIn("circuit_breaker:{", lua_script)
        self.assertNotIn(
            "circuit_breaker:", lua_script.replace("circuit_breaker:{", "")
        )

    @patch("redis.Redis")
    def test_rate_limiter_lua_scripts(self, mock_redis):
        """测试限流器的Lua脚本是否使用哈希标签"""
        # 创建模拟对象
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.register_script.return_value = MagicMock()

        # 创建控制器
        controller = ResilienceController(mock_redis_instance)

        # 创建限流器
        limiter = RateLimiter("test_limiter", controller)

        # 断言脚本中使用了哈希标签
        self.assertIn("rate_limiter:{", limiter.TOKEN_BUCKET_ATOMIC_SCRIPT)
        self.assertIn("rate_limiter:{", limiter.SLIDING_WINDOW_ATOMIC_SCRIPT)
        self.assertIn("rate_limiter:{", limiter.FIXED_WINDOW_ATOMIC_SCRIPT)

    @patch("redis.Redis")
    def test_bulkhead_lua_script(self, mock_redis):
        """测试舱壁隔离的Lua脚本是否使用哈希标签"""
        # 创建模拟对象
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.register_script.return_value = MagicMock()

        # 创建控制器
        controller = ResilienceController(mock_redis_instance)

        # 创建舱壁隔离器
        bulkhead = Bulkhead("test_bulkhead", controller)

        # 断言脚本中使用了哈希标签
        lua_script = Bulkhead.BULKHEAD_ATOMIC_SCRIPT
        self.assertIn("bulkhead:{", lua_script)
        self.assertNotIn("bulkhead:", lua_script.replace("bulkhead:{", ""))

    def test_perm_cache_key(self):
        """测试权限缓存键是否使用哈希标签"""
        key = _make_perm_cache_key(123, "server", 456)
        self.assertTrue(key.startswith("perm:{"))
        self.assertTrue(key.endswith("}"))

    @patch("app.core.permission.hybrid_permission_cache.DistributedCacheManager")
    def test_user_index_keys(self, mock_distributed_cache):
        """测试用户索引键是否使用哈希标签"""
        # 创建模拟对象
        mock_redis_client = MagicMock()
        mock_distributed_cache.return_value = MagicMock()
        mock_distributed_cache.return_value.redis_client = mock_redis_client

        # 创建缓存实例
        cache = HybridPermissionCache()
        cache.distributed_cache = mock_distributed_cache.return_value

        # 调用方法
        cache._add_to_user_index(123, "test_key")

        # 断言使用了正确的键格式
        mock_redis_client.sadd.assert_called_once()
        args, _ = mock_redis_client.sadd.call_args
        self.assertEqual(args[0], "user_index:{123}")


if __name__ == "__main__":
    pytest.main(["-xvs", "test_hash_tags.py"])
