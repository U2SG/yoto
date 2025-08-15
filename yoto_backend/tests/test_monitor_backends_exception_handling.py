"""
测试监控后端异常处理修复

验证RedisBackend的异常处理是否更加健壮和精确
"""

import pytest
import redis
import time
from unittest.mock import Mock, patch, MagicMock
from yoto_backend.app.core.permission.monitor_backends import (
    RedisBackend,
    MonitorBackendFactory,
    BackendType,
)


class TestRedisBackendExceptionHandling:
    """测试Redis后端异常处理"""

    def setup_method(self):
        """设置测试环境"""
        self.redis_backend = RedisBackend(
            redis_url="redis://localhost:6379", key_prefix="test:", max_history_size=100
        )

    def test_connection_health_check_success(self):
        """测试连接健康检查成功"""
        # 模拟Redis连接正常
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        self.redis_backend._redis = mock_redis

        result = self.redis_backend._check_connection_health()

        assert result is True
        assert self.redis_backend._connection_healthy is True
        mock_redis.ping.assert_called_once()

    def test_connection_health_check_connection_error(self):
        """测试连接健康检查 - 连接错误"""
        # 模拟Redis连接错误
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
        self.redis_backend._redis = mock_redis

        result = self.redis_backend._check_connection_health()

        assert result is False
        assert self.redis_backend._connection_healthy is False

    def test_connection_health_check_timeout_error(self):
        """测试连接健康检查 - 超时错误"""
        # 模拟Redis超时错误
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.TimeoutError("Timeout")
        self.redis_backend._redis = mock_redis

        result = self.redis_backend._check_connection_health()

        assert result is False
        assert self.redis_backend._connection_healthy is False

    def test_connection_health_check_auth_error(self):
        """测试连接健康检查 - 认证错误"""
        # 模拟Redis认证错误
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.AuthenticationError("Auth failed")
        self.redis_backend._redis = mock_redis

        result = self.redis_backend._check_connection_health()

        assert result is False
        assert self.redis_backend._connection_healthy is False

    def test_connection_health_check_no_redis(self):
        """测试连接健康检查 - 无Redis连接"""
        self.redis_backend._redis = None

        result = self.redis_backend._check_connection_health()

        assert result is False

    def test_record_metric_connection_error(self):
        """测试记录指标 - 连接错误"""
        # 模拟连接健康检查失败
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.record_metric("test_metric", 100.0)

            assert result is False

    def test_record_metric_redis_connection_error(self):
        """测试记录指标 - Redis连接错误"""
        # 模拟连接健康检查成功，但Redis操作失败
        mock_redis = Mock()
        mock_redis.lpush.side_effect = redis.ConnectionError("Connection failed")
        self.redis_backend._redis = mock_redis

        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=True
        ):
            result = self.redis_backend.record_metric("test_metric", 100.0)

            assert result is False
            assert self.redis_backend._connection_healthy is False

    def test_record_metric_redis_timeout_error(self):
        """测试记录指标 - Redis超时错误"""
        # 模拟Redis超时错误
        mock_redis = Mock()
        mock_redis.lpush.side_effect = redis.TimeoutError("Timeout")
        self.redis_backend._redis = mock_redis

        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=True
        ):
            result = self.redis_backend.record_metric("test_metric", 100.0)

            assert result is False
            assert self.redis_backend._connection_healthy is False

    def test_record_metric_redis_auth_error(self):
        """测试记录指标 - Redis认证错误"""
        # 模拟Redis认证错误
        mock_redis = Mock()
        mock_redis.lpush.side_effect = redis.AuthenticationError("Auth failed")
        self.redis_backend._redis = mock_redis

        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=True
        ):
            result = self.redis_backend.record_metric("test_metric", 100.0)

            assert result is False
            # 认证错误不应该影响连接健康状态
            assert self.redis_backend._connection_healthy is True

    def test_record_metric_redis_operation_error(self):
        """测试记录指标 - Redis操作错误"""
        # 模拟Redis操作错误
        mock_redis = Mock()
        mock_redis.lpush.side_effect = redis.RedisError("Operation failed")
        self.redis_backend._redis = mock_redis

        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=True
        ):
            result = self.redis_backend.record_metric("test_metric", 100.0)

            assert result is False

    def test_get_metrics_connection_unavailable(self):
        """测试获取指标 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.get_metrics("test_metric")

            assert result == []

    def test_get_events_connection_unavailable(self):
        """测试获取事件 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.get_events("test_event")

            assert result == []

    def test_get_stats_connection_unavailable(self):
        """测试获取统计 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.get_stats("test_stat")

            assert result == {
                "count": 0,
                "sum": 0,
                "min": float("inf"),
                "max": float("-inf"),
            }

    def test_create_alert_connection_unavailable(self):
        """测试创建告警 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            mock_alert = Mock()
            mock_alert.id = "test_alert"
            mock_alert.level.value = "warning"
            mock_alert.message = "Test alert"
            mock_alert.metric_type.value = "error_rate"
            mock_alert.current_value = 0.8
            mock_alert.threshold = 0.5
            mock_alert.timestamp = time.time()
            mock_alert.resolved = False

            result = self.redis_backend.create_alert(mock_alert)

            assert result is False

    def test_get_active_alerts_connection_unavailable(self):
        """测试获取活跃告警 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.get_active_alerts()

            assert result == []

    def test_resolve_alert_connection_unavailable(self):
        """测试解决告警 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.resolve_alert("test_alert_id")

            assert result is False

    def test_get_alert_counters_connection_unavailable(self):
        """测试获取告警计数器 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            result = self.redis_backend.get_alert_counters()

            assert result == {}

    def test_update_stats_connection_unavailable(self):
        """测试更新统计 - 连接不可用"""
        # 模拟连接不可用
        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=False
        ):
            # 这个方法不返回任何值，我们主要测试它不会抛出异常
            self.redis_backend._update_stats("test_stat", 100.0)
            # 如果没有抛出异常，说明测试通过

    def test_successful_metric_recording(self):
        """测试成功的指标记录"""
        # 模拟成功的Redis操作
        mock_redis = Mock()
        mock_redis.lpush.return_value = 1
        mock_redis.ltrim.return_value = True
        mock_redis.set.return_value = True
        self.redis_backend._redis = mock_redis

        with patch.object(
            self.redis_backend, "_check_connection_health", return_value=True
        ):
            with patch.object(self.redis_backend, "_update_stats"):
                result = self.redis_backend.record_metric("test_metric", 100.0)

                assert result is True
                mock_redis.lpush.assert_called_once()
                mock_redis.ltrim.assert_called_once()
                mock_redis.set.assert_called_once()


class TestMonitorBackendFactory:
    """测试监控后端工厂"""

    def test_create_redis_backend(self):
        """测试创建Redis后端"""
        backend = MonitorBackendFactory.create_backend(
            BackendType.REDIS, redis_url="redis://localhost:6379", key_prefix="test:"
        )

        assert isinstance(backend, RedisBackend)
        assert backend.redis_url == "redis://localhost:6379"
        assert backend.key_prefix == "test:"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
