"""
智能预取模块测试

测试行为分析、预测算法、预取策略等功能
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.core.smart_prefetch import (
    UserBehavior,
    BehaviorAnalyzer,
    SmartPrefetcher,
    ClientSidePredictor,
    get_client_predictor,
    record_user_action,
    get_predicted_resources,
    get_prefetch_tasks,
)


class TestUserBehavior:
    """测试用户行为数据模型"""

    def test_user_behavior_creation(self):
        """测试用户行为对象创建"""
        behavior = UserBehavior(
            user_id="user123",
            action="view",
            resource_type="server",
            resource_id="server456",
            timestamp=time.time(),
            session_id="session789",
            context={"ip": "192.168.1.1"},
        )

        assert behavior.user_id == "user123"
        assert behavior.action == "view"
        assert behavior.resource_type == "server"
        assert behavior.resource_id == "server456"
        assert behavior.session_id == "session789"
        assert behavior.context["ip"] == "192.168.1.1"


class TestBehaviorAnalyzer:
    """测试行为分析器"""

    def setup_method(self):
        """测试前准备"""
        self.mock_redis = Mock()
        self.analyzer = BehaviorAnalyzer(redis_client=self.mock_redis)

    def test_record_behavior_with_redis(self):
        """测试记录用户行为（有Redis）"""
        behavior = UserBehavior(
            user_id="user123",
            action="view",
            resource_type="server",
            resource_id="server456",
            timestamp=time.time(),
            session_id="session789",
            context={},
        )

        self.analyzer.record_behavior(behavior)

        # 验证Redis调用
        self.mock_redis.lpush.assert_called_once()
        self.mock_redis.ltrim.assert_called_once_with("user_behavior:user123", 0, 999)
        self.mock_redis.expire.assert_called_once()

    def test_record_behavior_without_redis(self):
        """测试记录用户行为（无Redis）"""
        analyzer = BehaviorAnalyzer(redis_client=None)
        behavior = UserBehavior(
            user_id="user123",
            action="view",
            resource_type="server",
            resource_id="server456",
            timestamp=time.time(),
            session_id="session789",
            context={},
        )

        # 应该不会抛出异常
        analyzer.record_behavior(behavior)

    def test_get_user_behaviors(self):
        """测试获取用户行为历史"""
        # 模拟Redis返回的数据
        mock_data = [
            json.dumps(
                {
                    "user_id": "user123",
                    "action": "view",
                    "resource_type": "server",
                    "resource_id": "server456",
                    "timestamp": str(time.time()),
                    "session_id": "session789",
                    "context": {},
                }
            )
        ]
        self.mock_redis.lrange.return_value = mock_data

        behaviors = self.analyzer._get_user_behaviors("user123", limit=10)

        assert len(behaviors) == 1
        assert behaviors[0].user_id == "user123"
        assert behaviors[0].action == "view"

    def test_analyze_patterns(self):
        """测试行为模式分析"""
        behaviors = [
            UserBehavior(
                user_id="user123",
                action="view",
                resource_type="server",
                resource_id="server1",
                timestamp=time.time(),
                session_id="session1",
                context={},
            ),
            UserBehavior(
                user_id="user123",
                action="edit",
                resource_type="server",
                resource_id="server1",
                timestamp=time.time() + 1,
                session_id="session1",
                context={},
            ),
            UserBehavior(
                user_id="user123",
                action="view",
                resource_type="channel",
                resource_id="channel1",
                timestamp=time.time() + 2,
                session_id="session1",
                context={},
            ),
        ]

        patterns = self.analyzer._analyze_patterns(behaviors)

        assert patterns["total_behaviors"] == 3
        assert patterns["unique_sessions"] == 1
        assert len(patterns["action_sequences"]) == 1
        assert "server:server1" in patterns["resource_frequency"]
        assert "view" in patterns["action_frequency"]

    def test_predict_next_actions(self):
        """测试预测下一个操作"""
        # 模拟用户行为历史
        mock_behaviors = [
            UserBehavior(
                user_id="user123",
                action="view",
                resource_type="server",
                resource_id="server1",
                timestamp=time.time(),
                session_id="session1",
                context={},
            ),
            UserBehavior(
                user_id="user123",
                action="view",
                resource_type="server",
                resource_id="server1",
                timestamp=time.time() + 1,
                session_id="session1",
                context={},
            ),
        ]

        with patch.object(
            self.analyzer, "_get_user_behaviors", return_value=mock_behaviors
        ):
            predictions = self.analyzer.predict_next_actions("user123")

            assert len(predictions) > 0
            assert predictions[0]["resource_type"] == "server"
            assert predictions[0]["resource_id"] == "server1"
            assert "confidence" in predictions[0]
            assert "reason" in predictions[0]


class TestSmartPrefetcher:
    """测试智能预取器"""

    def setup_method(self):
        """测试前准备"""
        self.mock_analyzer = Mock()
        self.prefetcher = SmartPrefetcher(self.mock_analyzer)

    def test_should_prefetch(self):
        """测试是否应该预取"""
        # 初始状态应该可以预取
        assert self.prefetcher.should_prefetch() is True

        # 设置最近预取时间
        self.prefetcher.last_prefetch_time = time.time()
        assert self.prefetcher.should_prefetch() is False

        # 等待预取间隔后应该可以预取
        self.prefetcher.last_prefetch_time = time.time() - 70  # 超过60秒
        assert self.prefetcher.should_prefetch() is True

    def test_generate_prefetch_tasks(self):
        """测试生成预取任务"""
        mock_predictions = [
            {
                "resource_type": "server",
                "resource_id": "server1",
                "action": "view",
                "confidence": 0.8,
                "reason": "高频访问",
            },
            {
                "resource_type": "channel",
                "resource_id": "channel1",
                "action": "view",
                "confidence": 0.2,  # 低于阈值
                "reason": "低频访问",
            },
        ]

        self.mock_analyzer.predict_next_actions.return_value = mock_predictions

        tasks = self.prefetcher.generate_prefetch_tasks("user123")

        assert len(tasks) == 1  # 只有高置信度的任务
        assert tasks[0]["resource_type"] == "server"
        assert tasks[0]["resource_id"] == "server1"
        assert tasks[0]["priority"] == 0.8

    def test_add_prefetch_task(self):
        """测试添加预取任务"""
        task = {
            "user_id": "user123",
            "resource_type": "server",
            "resource_id": "server1",
            "priority": 0.8,
            "reason": "高频访问",
        }

        self.prefetcher.add_prefetch_task(task)

        assert len(self.prefetcher.prefetch_queue) == 1
        assert self.prefetcher.prefetch_queue[0]["priority"] == 0.8

    def test_get_prefetch_batch(self):
        """测试获取预取批次"""
        # 添加多个任务
        for i in range(10):
            task = {
                "user_id": "user123",
                "resource_type": "server",
                "resource_id": f"server{i}",
                "priority": 0.9 - i * 0.1,
                "reason": f"任务{i}",
            }
            self.prefetcher.add_prefetch_task(task)

        # 获取批次
        batch = self.prefetcher.get_prefetch_batch(batch_size=5)

        assert len(batch) == 5
        assert len(self.prefetcher.prefetch_queue) == 5  # 剩余5个
        # 验证按优先级排序
        assert batch[0]["priority"] >= batch[1]["priority"]

    def test_cache_prefetched_data(self):
        """测试缓存预取数据"""
        data = {"name": "测试服务器", "members": 100}

        self.prefetcher.cache_prefetched_data("user123", "server", "server1", data)

        cache_key = "prefetch:user123:server:server1"
        assert cache_key in self.prefetcher.prefetch_cache
        assert self.prefetcher.prefetch_cache[cache_key]["data"] == data

    def test_get_prefetched_data(self):
        """测试获取预取数据"""
        data = {"name": "测试服务器", "members": 100}
        cache_key = "prefetch:user123:server:server1"

        # 添加缓存数据
        self.prefetcher.prefetch_cache[cache_key] = {
            "data": data,
            "expires_at": time.time() + 300,  # 5分钟后过期
        }

        # 获取数据
        result = self.prefetcher.get_prefetched_data("user123", "server", "server1")

        assert result == data

    def test_get_prefetched_data_expired(self):
        """测试获取过期的预取数据"""
        data = {"name": "测试服务器", "members": 100}
        cache_key = "prefetch:user123:server:server1"

        # 添加过期的缓存数据
        self.prefetcher.prefetch_cache[cache_key] = {
            "data": data,
            "expires_at": time.time() - 1,  # 已过期
        }

        # 获取数据应该返回None
        result = self.prefetcher.get_prefetched_data("user123", "server", "server1")

        assert result is None
        # 过期数据应该被清理
        assert cache_key not in self.prefetcher.prefetch_cache

    def test_cleanup_expired_cache(self):
        """测试清理过期缓存"""
        # 添加有效和过期的缓存数据
        valid_key = "prefetch:user123:server:server1"
        expired_key = "prefetch:user123:server:server2"

        self.prefetcher.prefetch_cache[valid_key] = {
            "data": {"name": "有效数据"},
            "expires_at": time.time() + 300,
        }

        self.prefetcher.prefetch_cache[expired_key] = {
            "data": {"name": "过期数据"},
            "expires_at": time.time() - 1,
        }

        # 清理过期缓存
        self.prefetcher.cleanup_expired_cache()

        # 验证结果
        assert valid_key in self.prefetcher.prefetch_cache
        assert expired_key not in self.prefetcher.prefetch_cache


class TestClientSidePredictor:
    """测试客户端预测器"""

    def setup_method(self):
        """测试前准备"""
        self.mock_analyzer = Mock()
        self.mock_prefetcher = Mock()
        self.predictor = ClientSidePredictor()
        self.predictor.analyzer = self.mock_analyzer
        self.predictor.prefetcher = self.mock_prefetcher

    def test_record_user_action(self):
        """测试记录用户操作"""
        # 设置mock返回值
        self.mock_prefetcher.generate_prefetch_tasks.return_value = []

        self.predictor.record_user_action(
            user_id="user123",
            action="view",
            resource_type="server",
            resource_id="server1",
            session_id="session1",
            context={"ip": "192.168.1.1"},
        )

        # 验证行为分析器被调用
        self.mock_analyzer.record_behavior.assert_called_once()
        behavior = self.mock_analyzer.record_behavior.call_args[0][0]
        assert behavior.user_id == "user123"
        assert behavior.action == "view"
        assert behavior.resource_type == "server"

    def test_record_user_action_auto_session(self):
        """测试自动生成会话ID"""
        # 设置mock返回值
        self.mock_prefetcher.generate_prefetch_tasks.return_value = []

        self.predictor.record_user_action(
            user_id="user123",
            action="view",
            resource_type="server",
            resource_id="server1",
        )

        # 验证自动生成了会话ID
        self.mock_analyzer.record_behavior.assert_called_once()
        behavior = self.mock_analyzer.record_behavior.call_args[0][0]
        assert behavior.session_id is not None
        assert "user123_" in behavior.session_id

    def test_get_predicted_resources(self):
        """测试获取预测资源"""
        mock_predictions = [
            {
                "resource_type": "server",
                "resource_id": "server1",
                "action": "view",
                "confidence": 0.8,
                "reason": "高频访问",
            }
        ]

        self.mock_analyzer.predict_next_actions.return_value = mock_predictions

        predictions = self.predictor.get_predicted_resources("user123")

        assert predictions == mock_predictions
        self.mock_analyzer.predict_next_actions.assert_called_once_with("user123")

    def test_get_prefetch_tasks(self):
        """测试获取预取任务"""
        mock_tasks = [
            {
                "user_id": "user123",
                "resource_type": "server",
                "resource_id": "server1",
                "priority": 0.8,
            }
        ]

        self.mock_prefetcher.get_prefetch_batch.return_value = mock_tasks

        tasks = self.predictor.get_prefetch_tasks(batch_size=5)

        assert tasks == mock_tasks
        self.mock_prefetcher.get_prefetch_batch.assert_called_once_with(5)

    def test_get_optimization_stats(self):
        """测试获取优化统计"""
        # 设置模拟数据
        self.mock_prefetcher.prefetch_queue = [1, 2, 3]  # 3个任务
        self.mock_prefetcher.prefetch_cache = {
            "key1": "value1",
            "key2": "value2",
        }  # 2个缓存项
        self.predictor.user_sessions = {
            "user1": "session1",
            "user2": "session2",
        }  # 2个用户会话
        self.mock_prefetcher.last_prefetch_time = 1234567890

        stats = self.predictor.get_optimization_stats()

        assert stats["total_prefetch_tasks"] == 3
        assert stats["cached_items"] == 2
        assert stats["user_sessions"] == 2
        assert stats["last_prefetch_time"] == 1234567890


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_record_user_action_function(self):
        """测试记录用户操作便捷函数"""
        with patch("app.core.smart_prefetch.get_client_predictor") as mock_get:
            mock_predictor = Mock()
            mock_predictor.record_user_action.return_value = None
            mock_get.return_value = mock_predictor

            record_user_action(
                user_id="user123",
                action="view",
                resource_type="server",
                resource_id="server1",
            )

            mock_predictor.record_user_action.assert_called_once_with(
                "user123", "view", "server", "server1", None, None
            )

    def test_get_predicted_resources_function(self):
        """测试获取预测资源便捷函数"""
        with patch("app.core.smart_prefetch.get_client_predictor") as mock_get:
            mock_predictor = Mock()
            mock_predictor.get_predicted_resources.return_value = [{"test": "data"}]
            mock_get.return_value = mock_predictor

            result = get_predicted_resources("user123")

            assert result == [{"test": "data"}]
            mock_predictor.get_predicted_resources.assert_called_once_with("user123")

    def test_get_prefetch_tasks_function(self):
        """测试获取预取任务便捷函数"""
        with patch("app.core.smart_prefetch.get_client_predictor") as mock_get:
            mock_predictor = Mock()
            mock_predictor.get_prefetch_tasks.return_value = [{"task": "data"}]
            mock_get.return_value = mock_predictor

            result = get_prefetch_tasks(batch_size=10)

            assert result == [{"task": "data"}]
            mock_predictor.get_prefetch_tasks.assert_called_once_with(10)


if __name__ == "__main__":
    pytest.main([__file__])
