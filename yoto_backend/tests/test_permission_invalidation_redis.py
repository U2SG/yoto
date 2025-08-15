"""
权限失效模块Redis测试

测试Redis存储的延迟失效队列功能
"""

import pytest
import time
import json
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.permission_invalidation import (
    add_delayed_invalidation,
    get_delayed_invalidation_stats,
    get_invalidation_statistics,
    get_smart_batch_invalidation_analysis,
    process_delayed_invalidations,
    cleanup_expired_invalidations,
    get_cache_auto_tune_suggestions,
    get_cache_invalidation_strategy_analysis,
    get_distributed_cache_stats,
    distributed_cache_get,
    distributed_cache_set,
    distributed_cache_delete,
)


class TestPermissionInvalidationRedis:
    """权限失效模块Redis测试类"""

    def setup_method(self):
        """测试前准备"""
        self.mock_redis = MagicMock()
        self.mock_redis.lpush.return_value = 1
        self.mock_redis.llen.return_value = 5
        self.mock_redis.rpop.return_value = json.dumps(
            {
                "cache_key": "test:key:1",
                "cache_level": "l1",
                "reason": "test_reason",
                "timestamp": time.time(),
                "processed": False,
            }
        )
        self.mock_redis.lrange.return_value = [
            json.dumps(
                {
                    "cache_key": "test:key:1",
                    "cache_level": "l1",
                    "reason": "test_reason",
                    "timestamp": time.time(),
                    "processed": False,
                }
            ),
            json.dumps(
                {
                    "cache_key": "test:key:2",
                    "cache_level": "l2",
                    "reason": "test_reason2",
                    "timestamp": time.time(),
                    "processed": False,
                }
            ),
        ]
        self.mock_redis.hincrby.return_value = 1
        self.mock_redis.hgetall.return_value = {
            b"total_invalidations": b"10",
            b"delayed_invalidations": b"5",
            b"immediate_invalidations": b"3",
            b"batch_invalidations": b"2",
        }
        self.mock_redis.dbsize.return_value = 100
        self.mock_redis.get.return_value = b"test_value"
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = 1
        self.mock_redis.eval.return_value = 2
        self.mock_redis.lindex.return_value = json.dumps(
            {
                "cache_key": "test:key:1",
                "cache_level": "l1",
                "reason": "test_reason",
                "timestamp": time.time(),
                "processed": False,
            }
        )

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_add_delayed_invalidation_success(self, mock_get_redis):
        """测试成功添加延迟失效"""
        mock_get_redis.return_value = self.mock_redis

        result = add_delayed_invalidation("test:key:1", "l1", "test_reason")

        assert result is True
        self.mock_redis.lpush.assert_called_once()
        self.mock_redis.hincrby.assert_called_once()

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_add_delayed_invalidation_no_redis(self, mock_get_redis):
        """测试Redis不可用时添加延迟失效"""
        mock_get_redis.return_value = None

        result = add_delayed_invalidation("test:key:1", "l1", "test_reason")

        assert result is False

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_delayed_invalidation_stats(self, mock_get_redis):
        """测试获取延迟失效统计"""
        mock_get_redis.return_value = self.mock_redis

        stats = get_delayed_invalidation_stats()

        assert "pending_count" in stats
        assert "processed_count" in stats
        assert "total_count" in stats
        assert "stats" in stats
        assert stats["pending_count"] == 5

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_invalidation_statistics(self, mock_get_redis):
        """测试获取失效统计"""
        mock_get_redis.return_value = self.mock_redis

        stats = get_invalidation_statistics()

        assert "total_invalidations" in stats
        assert "delayed_invalidations" in stats
        assert "immediate_invalidations" in stats
        assert "batch_invalidations" in stats
        assert "delayed_stats" in stats

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_smart_batch_invalidation_analysis(self, mock_get_redis):
        """测试获取智能批量失效分析"""
        mock_get_redis.return_value = self.mock_redis

        analysis = get_smart_batch_invalidation_analysis()

        assert "pending_count" in analysis
        assert "key_patterns" in analysis
        assert "reasons" in analysis
        assert "recommendations" in analysis

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_process_delayed_invalidations(self, mock_get_redis):
        """测试处理延迟失效"""
        mock_get_redis.return_value = self.mock_redis

        results = process_delayed_invalidations(batch_size=10)

        assert "processed_count" in results
        assert "remaining_count" in results
        assert "execution_time" in results

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_cleanup_expired_invalidations(self, mock_get_redis):
        """测试清理过期失效记录"""
        mock_get_redis.return_value = self.mock_redis

        cleanup_expired_invalidations(max_age=3600)

        self.mock_redis.eval.assert_called_once()

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_cache_auto_tune_suggestions(self, mock_get_redis):
        """测试获取缓存自动调优建议"""
        mock_get_redis.return_value = self.mock_redis

        suggestions = get_cache_auto_tune_suggestions()

        assert "suggestions" in suggestions
        assert "recent_invalidations" in suggestions
        assert "patterns" in suggestions

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_cache_invalidation_strategy_analysis(self, mock_get_redis):
        """测试获取缓存失效策略分析"""
        mock_get_redis.return_value = self.mock_redis

        analysis = get_cache_invalidation_strategy_analysis()

        assert "reasons_distribution" in analysis
        assert "levels_distribution" in analysis
        assert "avg_delay" in analysis
        assert "total_pending" in analysis
        assert "total_processed" in analysis

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_get_distributed_cache_stats(self, mock_get_redis):
        """测试获取分布式缓存统计"""
        mock_get_redis.return_value = self.mock_redis

        stats = get_distributed_cache_stats()

        assert "connected" in stats
        assert "keys" in stats
        assert stats["connected"] is True
        assert stats["keys"] == 100

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_distributed_cache_get(self, mock_get_redis):
        """测试分布式缓存获取"""
        mock_get_redis.return_value = self.mock_redis

        result = distributed_cache_get("test_key")

        assert result == b"test_value"
        self.mock_redis.get.assert_called_once_with("test_key")

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_distributed_cache_set(self, mock_get_redis):
        """测试分布式缓存设置"""
        mock_get_redis.return_value = self.mock_redis

        result = distributed_cache_set("test_key", b"test_value", 300)

        assert result is True
        self.mock_redis.setex.assert_called_once_with("test_key", 300, b"test_value")

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_distributed_cache_delete(self, mock_get_redis):
        """测试分布式缓存删除"""
        mock_get_redis.return_value = self.mock_redis

        result = distributed_cache_delete("test_key")

        assert result is True
        self.mock_redis.delete.assert_called_once_with("test_key")

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_redis_connection_error_handling(self, mock_get_redis):
        """测试Redis连接错误处理"""
        self.mock_redis.lpush.side_effect = Exception("Connection error")
        mock_get_redis.return_value = self.mock_redis

        result = add_delayed_invalidation("test:key:1", "l1", "test_reason")

        assert result is False

    @patch("app.core.permission_invalidation._get_redis_client")
    def test_json_decode_error_handling(self, mock_get_redis):
        """测试JSON解析错误处理"""
        self.mock_redis.rpop.return_value = "invalid_json"
        mock_get_redis.return_value = self.mock_redis

        results = process_delayed_invalidations(batch_size=1)

        assert results["processed_count"] == 0

    def test_redis_key_constants(self):
        """测试Redis键常量"""
        from app.core.permission_invalidation import (
            DELAYED_INVALIDATION_QUEUE,
            INVALIDATION_STATS_KEY,
            INVALIDATION_STATS_LOCK,
        )

        assert DELAYED_INVALIDATION_QUEUE == "delayed_invalidation_queue"
        assert INVALIDATION_STATS_KEY == "invalidation_stats"
        assert INVALIDATION_STATS_LOCK == "invalidation_stats_lock"


if __name__ == "__main__":
    pytest.main([__file__])
