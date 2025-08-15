"""
动态图表可视化测试
测试性能可视化模块和WebSocket图表服务器
"""

import pytest
import time
import threading
import sys
import os
from typing import Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 检查模块是否可用
try:
    from app.core.performance_visualization import (
        PerformanceVisualization,
        get_performance_visualization,
        get_real_time_chart_data,
        subscribe_to_performance_updates,
        unsubscribe_from_performance_updates,
    )
    from app.core.websocket_charts import (
        WebSocketChartServer,
        get_websocket_chart_server,
    )
    from app import create_app

    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"模块导入失败: {e}")
    MODULES_AVAILABLE = False


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
class TestPerformanceVisualization:
    """性能可视化测试"""

    def setup_method(self):
        """测试前准备"""
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 创建可视化实例
        self.viz = PerformanceVisualization(max_data_points=100)

    def teardown_method(self):
        """测试后清理"""
        self.viz.stop()
        self.app_context.pop()

    def test_visualization_initialization(self):
        """测试可视化模块初始化"""
        assert self.viz.max_data_points == 100
        assert "cache_hit_rate" in self.viz.data_streams
        assert "response_time" in self.viz.data_streams
        assert "operation_frequency" in self.viz.data_streams
        assert "memory_usage" in self.viz.data_streams
        assert "error_rate" in self.viz.data_streams

        # 检查数据流结构
        for stream_name, streams in self.viz.data_streams.items():
            assert isinstance(streams, dict)
            for metric_name, data_queue in streams.items():
                assert hasattr(data_queue, "maxlen")

    def test_data_collection(self):
        """测试数据收集功能"""
        # 等待数据收集
        time.sleep(2)

        # 检查是否有数据被收集
        latest_data = self.viz.get_latest_data()

        # 验证数据结构
        assert isinstance(latest_data, dict)

        # 检查至少有一个数据流有数据
        has_data = False
        for stream_name, streams in latest_data.items():
            for metric_name, data_points in streams.items():
                if data_points:
                    has_data = True
                    break
            if has_data:
                break

        assert has_data, "应该有数据被收集"

    def test_chart_configs(self):
        """测试图表配置"""
        configs = [
            "cache_hit_rate",
            "response_time",
            "operation_frequency",
            "memory_usage",
            "error_rate",
        ]

        for chart_type in configs:
            config = self.viz.get_chart_config(chart_type)
            assert isinstance(config, dict)
            assert "title" in config
            assert "type" in config
            assert "yAxis" in config
            assert "colors" in config
            assert "legend" in config

    def test_subscription_system(self):
        """测试订阅系统"""
        received_data = []

        def callback(data):
            received_data.append(data)

        # 订阅数据更新
        self.viz.subscribe(callback)

        # 等待数据更新
        time.sleep(3)

        # 验证是否收到数据
        assert len(received_data) > 0, "应该收到数据更新"

        # 取消订阅
        self.viz.unsubscribe(callback)

        # 清空接收数据
        received_data.clear()

        # 等待一段时间
        time.sleep(2)

        # 验证取消订阅后不再收到数据
        assert len(received_data) == 0, "取消订阅后不应收到数据"

    def test_real_time_chart_data(self):
        """测试实时图表数据获取"""
        chart_types = [
            "cache_hit_rate",
            "response_time",
            "operation_frequency",
            "memory_usage",
            "error_rate",
        ]

        for chart_type in chart_types:
            chart_data = get_real_time_chart_data(chart_type, time_range=60)

            assert isinstance(chart_data, dict)
            assert "config" in chart_data
            assert "data" in chart_data
            assert "timestamp" in chart_data

            # 验证配置
            config = chart_data["config"]
            assert "title" in config
            assert "type" in config

    def test_data_point_structure(self):
        """测试数据点结构"""
        # 等待数据收集
        time.sleep(2)

        latest_data = self.viz.get_latest_data()

        for stream_name, streams in latest_data.items():
            for metric_name, data_points in streams.items():
                if data_points:
                    # 检查数据点结构
                    point = data_points[0]
                    assert "timestamp" in point
                    assert "value" in point
                    assert "label" in point

                    assert isinstance(point["timestamp"], (int, float))
                    assert isinstance(point["value"], (int, float))
                    assert isinstance(point["label"], str)

    def test_performance_under_load(self):
        """测试负载下的性能"""
        # 创建多个订阅者
        callbacks = []
        received_counts = []

        def create_callback(index):
            def callback(data):
                received_counts[index] += 1

            return callback

        # 创建10个订阅者
        for i in range(10):
            callback = create_callback(i)
            callbacks.append(callback)
            received_counts.append(0)
            self.viz.subscribe(callback)

        # 运行一段时间
        time.sleep(5)

        # 验证所有订阅者都收到了数据
        for i, count in enumerate(received_counts):
            assert count > 0, f"订阅者 {i} 应该收到数据"

        # 清理订阅者
        for callback in callbacks:
            self.viz.unsubscribe(callback)


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
class TestWebSocketChartServer:
    """WebSocket图表服务器测试"""

    def setup_method(self):
        """测试前准备"""
        self.app = create_app("testing")
        self.websocket_server = get_websocket_chart_server(self.app)

    def test_websocket_server_initialization(self):
        """测试WebSocket服务器初始化"""
        assert self.websocket_server.app == self.app
        assert self.websocket_server.socketio is not None
        assert isinstance(self.websocket_server.connected_clients, set)
        assert isinstance(self.websocket_server.chart_subscribers, dict)

    def test_server_status(self):
        """测试服务器状态"""
        status = self.websocket_server.get_status()

        assert isinstance(status, dict)
        assert "connected_clients" in status
        assert "chart_subscribers" in status
        assert "available_charts" in status

        assert isinstance(status["connected_clients"], int)
        assert isinstance(status["chart_subscribers"], dict)
        assert isinstance(status["available_charts"], list)

        # 验证可用图表列表
        expected_charts = [
            "cache_hit_rate",
            "response_time",
            "operation_frequency",
            "memory_usage",
            "error_rate",
        ]

        for chart in expected_charts:
            assert chart in status["available_charts"]

    def test_chart_data_retrieval(self):
        """测试图表数据获取"""
        from app.core.websocket_charts import get_real_time_chart_data

        chart_types = [
            "cache_hit_rate",
            "response_time",
            "operation_frequency",
            "memory_usage",
            "error_rate",
        ]

        for chart_type in chart_types:
            chart_data = get_real_time_chart_data(chart_type)

            assert isinstance(chart_data, dict)
            assert "config" in chart_data
            assert "data" in chart_data
            assert "timestamp" in chart_data


def test_visualization_integration():
    """测试可视化集成"""
    if not MODULES_AVAILABLE:
        pytest.skip("模块不可用")

    # 测试可视化模块启动
    viz = get_performance_visualization()
    assert viz is not None

    # 测试数据收集
    time.sleep(2)
    latest_data = viz.get_latest_data()
    assert isinstance(latest_data, dict)

    # 测试图表数据获取
    chart_data = get_real_time_chart_data("cache_hit_rate")
    assert isinstance(chart_data, dict)

    # 测试订阅系统
    received_data = []

    def callback(data):
        received_data.append(data)

    subscribe_to_performance_updates(callback)
    time.sleep(2)

    assert len(received_data) > 0

    unsubscribe_from_performance_updates(callback)

    # 清理
    viz.stop()


if __name__ == "__main__":
    print("开始动态图表可视化测试...")

    if MODULES_AVAILABLE:
        print("✓ 模块导入成功")

        # 测试可视化模块
        test_viz = TestPerformanceVisualization()
        test_viz.setup_method()

        test_viz.test_visualization_initialization()
        test_viz.test_data_collection()
        test_viz.test_chart_configs()
        test_viz.test_subscription_system()
        test_viz.test_real_time_chart_data()
        test_viz.test_data_point_structure()
        test_viz.test_performance_under_load()

        test_viz.teardown_method()

        # 测试WebSocket服务器
        test_ws = TestWebSocketChartServer()
        test_ws.setup_method()

        test_ws.test_websocket_server_initialization()
        test_ws.test_server_status()
        test_ws.test_chart_data_retrieval()

        # 测试集成
        test_visualization_integration()

        print("✓ 所有动态图表可视化测试完成")
    else:
        print("✗ 模块导入失败")
        print("请检查模块依赖和配置")
