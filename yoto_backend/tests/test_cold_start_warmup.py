"""
冷启动预热流程测试

测试应用启动后的预热功能，确保系统能够快速进入正常工作状态
"""

import time
import json
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# 导入测试模块
from app.core.permission import (
    initialize_permission_platform,
    get_permission_system,
    reset_platform_initialization,
)
from app.core.permission.permissions_refactored import PermissionSystem


class TestColdStartWarmup(unittest.TestCase):
    """冷启动预热流程测试类"""

    def setUp(self):
        """测试前准备"""
        # 重置平台初始化状态
        reset_platform_initialization()

        # 模拟Redis客户端
        self.mock_redis = Mock()
        self.mock_redis.keys.return_value = []
        self.mock_redis.get.return_value = None

    def tearDown(self):
        """测试后清理"""
        reset_platform_initialization()

    def test_warm_up_method_exists(self):
        """测试warm_up方法存在"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 验证warm_up方法存在
        self.assertTrue(hasattr(permission_system, "warm_up"))
        self.assertTrue(callable(permission_system.warm_up))

    def test_warm_up_basic_execution(self):
        """测试预热基本执行"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 执行预热
        result = permission_system.warm_up()

        # 验证返回结果结构
        self.assertIsInstance(result, dict)
        self.assertIn("cache_warmup", result)
        self.assertIn("ml_warmup", result)
        self.assertIn("system_warmup", result)
        self.assertIn("total_time", result)
        self.assertIn("success", result)
        self.assertIn("errors", result)

        # 验证总耗时为正数
        self.assertGreater(result["total_time"], 0)

    def test_warm_up_cache_component(self):
        """测试缓存预热组件"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 执行预热
        result = permission_system.warm_up()

        # 验证缓存预热结果
        cache_result = result["cache_warmup"]
        self.assertIn("success", cache_result)
        self.assertIn("time", cache_result)
        self.assertGreater(cache_result["time"], 0)

    def test_warm_up_ml_component(self):
        """测试ML模型预热组件"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 执行预热
        result = permission_system.warm_up()

        # 验证ML预热结果
        ml_result = result["ml_warmup"]
        self.assertIn("success", ml_result)
        self.assertIn("time", ml_result)
        self.assertIn("details", ml_result)
        self.assertGreater(ml_result["time"], 0)

        # 验证ML预热详情
        details = ml_result["details"]
        self.assertIn("historical_data_points", details)
        self.assertIn("data_time_range", details)
        self.assertIn("model_ready", details)

    def test_warm_up_system_component(self):
        """测试系统状态预热组件"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 执行预热
        result = permission_system.warm_up()

        # 验证系统预热结果
        system_result = result["system_warmup"]
        self.assertIn("success", system_result)
        self.assertIn("time", system_result)
        self.assertIn("details", system_result)
        self.assertGreater(system_result["time"], 0)

        # 验证系统预热详情
        details = system_result["details"]
        self.assertIn("component_status", details)
        self.assertIn("success_rate", details)
        self.assertIn("healthy_components", details)
        self.assertIn("total_components", details)

    @patch("app.core.permission.permissions_refactored.get_ml_performance_monitor")
    def test_warm_up_ml_with_historical_data(self, mock_ml_monitor):
        """测试ML预热加载历史数据"""
        # 模拟ML监控器
        mock_monitor = Mock()
        mock_ml_monitor.return_value = mock_monitor

        # 模拟Redis历史数据
        historical_data = [
            {
                "timestamp": time.time() - 3600,  # 1小时前
                "cache_hit_rate": 0.85,
                "response_time": 0.1,
                "memory_usage": 0.6,
                "cpu_usage": 0.4,
                "error_rate": 0.01,
                "qps": 1000,
                "lock_timeout_rate": 0.02,
                "connection_pool_usage": 0.7,
            }
        ]

        # 模拟Redis客户端
        mock_redis = Mock()
        mock_redis.keys.return_value = ["performance:metrics:test1"]
        mock_redis.get.return_value = json.dumps(historical_data[0])

        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 模拟缓存Redis客户端
        permission_system.cache.get_redis_client = Mock(return_value=mock_redis)

        # 执行预热
        result = permission_system.warm_up()

        # 验证ML预热成功
        ml_result = result["ml_warmup"]
        self.assertTrue(ml_result["success"])

        # 验证历史数据被加载
        details = ml_result["details"]
        self.assertEqual(details["historical_data_points"], 1)
        self.assertEqual(details["data_time_range"], "24h")
        self.assertTrue(details["model_ready"])

        # 验证ML监控器被调用
        mock_monitor.feed_metrics.assert_called_once()

    def test_warm_up_error_handling(self):
        """测试预热错误处理"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 模拟缓存预热失败
        with patch.object(
            permission_system, "warm_up_cache", side_effect=Exception("缓存预热失败")
        ):
            result = permission_system.warm_up()

            # 验证错误被正确记录
            self.assertFalse(result["success"])
            self.assertGreater(len(result["errors"]), 0)

            # 验证缓存预热失败
            cache_result = result["cache_warmup"]
            self.assertFalse(cache_result["success"])
            self.assertIn("error", cache_result)

    def test_warm_up_async_execution(self):
        """测试异步预热执行"""
        # 模拟初始化过程中的异步预热
        with patch(
            "app.core.permission.permissions_refactored.PermissionSystem.warm_up"
        ) as mock_warm_up:
            mock_warm_up.return_value = {
                "success": True,
                "total_time": 1.0,
                "errors": [],
            }

            # 初始化权限平台（会触发异步预热）
            initialize_permission_platform()

            # 等待异步预热完成
            time.sleep(0.1)

            # 验证预热被调用
            mock_warm_up.assert_called_once()

    def test_warm_up_performance_metrics(self):
        """测试预热性能指标"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 执行预热
        start_time = time.time()
        result = permission_system.warm_up()
        end_time = time.time()

        # 验证性能指标
        actual_time = end_time - start_time
        reported_time = result["total_time"]

        # 验证报告时间在合理范围内
        self.assertGreaterEqual(reported_time, 0)
        self.assertLessEqual(reported_time, actual_time + 0.1)  # 允许0.1秒误差

    def test_warm_up_component_isolation(self):
        """测试预热组件隔离"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 模拟部分组件失败
        with patch.object(
            permission_system, "_warm_up_ml_models", side_effect=Exception("ML预热失败")
        ):
            result = permission_system.warm_up()

            # 验证其他组件仍然正常工作
            self.assertIn("cache_warmup", result)
            self.assertIn("ml_warmup", result)
            self.assertIn("system_warmup", result)

            # 验证ML预热失败但其他组件成功
            self.assertFalse(result["ml_warmup"]["success"])
            self.assertTrue(result["cache_warmup"]["success"])
            self.assertTrue(result["system_warmup"]["success"])

    def test_warm_up_redis_unavailable(self):
        """测试Redis不可用时的预热"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 模拟Redis不可用
        permission_system.cache.get_redis_client = Mock(return_value=None)

        # 执行预热
        result = permission_system.warm_up()

        # 验证ML预热处理Redis不可用情况
        ml_result = result["ml_warmup"]
        self.assertTrue(ml_result["success"])  # 应该成功处理Redis不可用

        details = ml_result["details"]
        self.assertEqual(details["historical_data_points"], 0)
        self.assertEqual(details["data_time_range"], "none")
        self.assertFalse(details["model_ready"])
        self.assertEqual(details["reason"], "redis_unavailable")


class TestWarmUpIntegration(unittest.TestCase):
    """预热集成测试类"""

    def setUp(self):
        """测试前准备"""
        reset_platform_initialization()

    def tearDown(self):
        """测试后清理"""
        reset_platform_initialization()

    def test_platform_initialization_with_warmup(self):
        """测试平台初始化包含预热"""
        # 模拟预热方法
        with patch(
            "app.core.permission.permissions_refactored.PermissionSystem.warm_up"
        ) as mock_warm_up:
            mock_warm_up.return_value = {
                "success": True,
                "total_time": 0.5,
                "errors": [],
            }

            # 初始化平台
            success = initialize_permission_platform()

            # 验证初始化成功
            self.assertTrue(success)

            # 等待异步预热
            time.sleep(0.1)

            # 验证预热被调用
            mock_warm_up.assert_called_once()

    def test_warm_up_thread_safety(self):
        """测试预热线程安全"""
        # 初始化权限平台
        initialize_permission_platform()
        permission_system = get_permission_system()

        # 创建多个线程同时执行预热
        results = []
        threads = []

        def warm_up_worker():
            try:
                result = permission_system.warm_up()
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})

        # 启动多个线程
        for i in range(3):
            thread = threading.Thread(target=warm_up_worker)
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有预热都成功完成
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIn("success", result)
            self.assertIn("total_time", result)


if __name__ == "__main__":
    unittest.main()
