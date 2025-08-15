"""
机器学习优化模块测试
"""

import pytest
import time
import numpy as np
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.core.permission_ml import (
        MLPerformancePredictor,
        AdaptiveOptimizer,
        AnomalyDetector,
        MLPerformanceMonitor,
        PerformanceMetrics,
        OptimizationStrategy,
        get_ml_performance_monitor,
        get_ml_predictions,
        get_ml_optimized_config,
        get_ml_anomalies,
        set_ml_optimization_strategy,
    )
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在正确的目录下运行测试")
    sys.exit(1)


class TestMLPerformancePredictor:
    """机器学习性能预测器测试"""

    def test_initialization(self):
        """测试初始化"""
        predictor = MLPerformancePredictor()
        assert predictor.history_window == 1000
        assert predictor.prediction_horizon == 10
        assert len(predictor.models) > 0

    def test_add_performance_data(self):
        """测试添加性能数据"""
        predictor = MLPerformancePredictor()
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=0.85,
            response_time=50.0,
            memory_usage=0.6,
            cpu_usage=0.3,
            error_rate=0.01,
            qps=1000.0,
            lock_timeout_rate=0.02,
            connection_pool_usage=0.7,
        )

        predictor.add_performance_data(metrics)
        assert len(predictor.performance_history) == 1

    def test_predict_metric_with_insufficient_data(self):
        """测试数据不足时的预测"""
        predictor = MLPerformancePredictor()
        result = predictor.predict_metric("cache_hit_rate")
        assert result is None

    def test_predict_metric_with_sufficient_data(self):
        """测试有足够数据时的预测"""
        predictor = MLPerformancePredictor()

        # 添加足够的数据点
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + i * 0.01,
                response_time=50.0 + i * 2,
                memory_usage=0.6 + i * 0.02,
                cpu_usage=0.3 + i * 0.01,
                error_rate=0.01 + i * 0.001,
                qps=1000.0 + i * 10,
                lock_timeout_rate=0.02 + i * 0.001,
                connection_pool_usage=0.7 + i * 0.01,
            )
            predictor.add_performance_data(metrics)

        result = predictor.predict_metric("cache_hit_rate")
        assert result is not None
        assert result.metric_name == "cache_hit_rate"
        assert result.current_value > 0
        assert result.predicted_value > 0
        assert 0 <= result.confidence <= 1
        assert result.trend in ["increasing", "decreasing", "stable"]
        assert result.urgency_level in ["low", "medium", "high", "critical"]


class TestAdaptiveOptimizer:
    """自适应优化器测试"""

    def test_initialization(self):
        """测试初始化"""
        optimizer = AdaptiveOptimizer()
        assert optimizer.strategy == OptimizationStrategy.ADAPTIVE
        assert "connection_pool_size" in optimizer.current_config

    def test_get_default_config(self):
        """测试获取默认配置"""
        optimizer = AdaptiveOptimizer()
        config = optimizer._get_default_config()
        assert "connection_pool_size" in config
        assert "socket_timeout" in config
        assert "lock_timeout" in config
        assert "batch_size" in config
        assert "cache_max_size" in config

    def test_update_performance_metrics(self):
        """测试更新性能指标"""
        optimizer = AdaptiveOptimizer()
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=0.85,
            response_time=50.0,
            memory_usage=0.6,
            cpu_usage=0.3,
            error_rate=0.01,
            qps=1000.0,
            lock_timeout_rate=0.02,
            connection_pool_usage=0.7,
        )

        optimizer.update_performance_metrics(metrics)
        # 应该没有异常

    def test_get_optimized_config(self):
        """测试获取优化配置"""
        optimizer = AdaptiveOptimizer()
        config = optimizer.get_optimized_config()
        assert isinstance(config, dict)
        assert "connection_pool_size" in config

    def test_set_strategy(self):
        """测试设置优化策略"""
        optimizer = AdaptiveOptimizer()
        optimizer.set_strategy(OptimizationStrategy.AGGRESSIVE)
        assert optimizer.strategy == OptimizationStrategy.AGGRESSIVE


class TestAnomalyDetector:
    """异常检测器测试"""

    def test_initialization(self):
        """测试初始化"""
        detector = AnomalyDetector()
        assert detector.window_size == 100
        assert detector.threshold_std == 2.0

    def test_detect_anomalies_with_normal_data(self):
        """测试正常数据的异常检测"""
        detector = AnomalyDetector()

        # 添加正常数据
        for i in range(20):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + np.random.normal(0, 0.02),
                response_time=50.0 + np.random.normal(0, 5),
                memory_usage=0.6 + np.random.normal(0, 0.05),
                cpu_usage=0.3 + np.random.normal(0, 0.05),
                error_rate=0.01 + np.random.normal(0, 0.002),
                qps=1000.0 + np.random.normal(0, 50),
                lock_timeout_rate=0.02 + np.random.normal(0, 0.005),
                connection_pool_usage=0.7 + np.random.normal(0, 0.05),
            )
            anomalies = detector.detect_anomalies(metrics)
            # 正常数据应该很少检测到异常
            assert len(anomalies) <= 2  # 允许少量误报

    def test_detect_anomalies_with_anomalous_data(self):
        """测试异常数据的异常检测"""
        detector = AnomalyDetector()

        # 添加正常数据
        for i in range(15):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + np.random.normal(0, 0.02),
                response_time=50.0 + np.random.normal(0, 5),
                memory_usage=0.6 + np.random.normal(0, 0.05),
                cpu_usage=0.3 + np.random.normal(0, 0.05),
                error_rate=0.01 + np.random.normal(0, 0.002),
                qps=1000.0 + np.random.normal(0, 50),
                lock_timeout_rate=0.02 + np.random.normal(0, 0.005),
                connection_pool_usage=0.7 + np.random.normal(0, 0.05),
            )
            detector.detect_anomalies(metrics)

        # 添加异常数据
        anomalous_metrics = PerformanceMetrics(
            timestamp=time.time() + 20,
            cache_hit_rate=0.3,  # 异常低的缓存命中率
            response_time=500.0,  # 异常高的响应时间
            memory_usage=0.95,  # 异常高的内存使用
            cpu_usage=0.9,  # 异常高的CPU使用
            error_rate=0.1,  # 异常高的错误率
            qps=100.0,  # 异常低的QPS
            lock_timeout_rate=0.2,  # 异常高的锁超时率
            connection_pool_usage=0.95,  # 异常高的连接池使用
        )

        anomalies = detector.detect_anomalies(anomalous_metrics)
        assert len(anomalies) > 0  # 应该检测到异常

    def test_get_anomaly_history(self):
        """测试获取异常历史"""
        detector = AnomalyDetector()
        history = detector.get_anomaly_history()
        assert isinstance(history, list)


class TestMLPerformanceMonitor:
    """机器学习性能监控器测试"""

    def test_initialization(self):
        """测试初始化"""
        monitor = MLPerformanceMonitor()
        assert monitor.predictor is not None
        assert monitor.optimizer is not None
        assert monitor.anomaly_detector is not None
        assert monitor.monitoring_active is True

    def test_get_predictions(self):
        """测试获取预测"""
        monitor = MLPerformanceMonitor()
        predictions = monitor.get_predictions()
        assert isinstance(predictions, list)

    def test_get_optimized_config(self):
        """测试获取优化配置"""
        monitor = MLPerformanceMonitor()
        config = monitor.get_optimized_config()
        assert isinstance(config, dict)
        assert "connection_pool_size" in config

    def test_get_anomalies(self):
        """测试获取异常"""
        monitor = MLPerformanceMonitor()
        anomalies = monitor.get_anomalies()
        assert isinstance(anomalies, list)

    def test_get_optimization_history(self):
        """测试获取优化历史"""
        monitor = MLPerformanceMonitor()
        history = monitor.get_optimization_history()
        assert isinstance(history, list)

    def test_set_optimization_strategy(self):
        """测试设置优化策略"""
        monitor = MLPerformanceMonitor()
        monitor.set_optimization_strategy(OptimizationStrategy.AGGRESSIVE)
        assert monitor.optimizer.strategy == OptimizationStrategy.AGGRESSIVE

    def test_feed_metrics(self):
        """测试注入性能指标数据"""
        monitor = MLPerformanceMonitor()
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=0.85,
            response_time=50.0,
            memory_usage=0.6,
            cpu_usage=0.3,
            error_rate=0.01,
            qps=1000.0,
            lock_timeout_rate=0.02,
            connection_pool_usage=0.7,
        )

        # 测试注入性能指标
        monitor.feed_metrics(metrics)

        # 验证数据已被处理
        assert len(monitor.predictor.performance_history) > 0


class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_ml_performance_monitor(self):
        """测试获取机器学习性能监控器"""
        monitor = get_ml_performance_monitor()
        assert isinstance(monitor, MLPerformanceMonitor)

    def test_get_ml_predictions(self):
        """测试获取机器学习预测"""
        predictions = get_ml_predictions()
        assert isinstance(predictions, list)

    def test_get_ml_optimized_config(self):
        """测试获取机器学习优化配置"""
        config = get_ml_optimized_config()
        assert isinstance(config, dict)
        assert "connection_pool_size" in config

    def test_get_ml_anomalies(self):
        """测试获取机器学习异常"""
        anomalies = get_ml_anomalies()
        assert isinstance(anomalies, list)

    def test_set_ml_optimization_strategy(self):
        """测试设置机器学习优化策略"""
        set_ml_optimization_strategy("aggressive")
        monitor = get_ml_performance_monitor()
        assert monitor.optimizer.strategy == OptimizationStrategy.AGGRESSIVE


class TestIntegration:
    """集成测试"""

    def test_end_to_end_workflow(self):
        """测试端到端工作流程"""
        # 获取监控器
        monitor = get_ml_performance_monitor()

        # 设置优化策略
        monitor.set_optimization_strategy(OptimizationStrategy.ADAPTIVE)

        # 获取初始配置
        initial_config = monitor.get_optimized_config()

        # 模拟性能数据收集
        for i in range(5):
            time.sleep(1)  # 等待数据收集

        # 获取预测
        predictions = monitor.get_predictions()
        assert isinstance(predictions, list)

        # 获取异常
        anomalies = monitor.get_anomalies()
        assert isinstance(anomalies, list)

        # 获取优化历史
        history = monitor.get_optimization_history()
        assert isinstance(history, list)

        # 获取最终配置
        final_config = monitor.get_optimized_config()
        assert isinstance(final_config, dict)

    def test_performance_metrics_serialization(self):
        """测试性能指标序列化"""
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=0.85,
            response_time=50.0,
            memory_usage=0.6,
            cpu_usage=0.3,
            error_rate=0.01,
            qps=1000.0,
            lock_timeout_rate=0.02,
            connection_pool_usage=0.7,
        )

        # 测试转换为字典
        metrics_dict = {
            "timestamp": metrics.timestamp,
            "cache_hit_rate": metrics.cache_hit_rate,
            "response_time": metrics.response_time,
            "memory_usage": metrics.memory_usage,
            "cpu_usage": metrics.cpu_usage,
            "error_rate": metrics.error_rate,
            "qps": metrics.qps,
            "lock_timeout_rate": metrics.lock_timeout_rate,
            "connection_pool_usage": metrics.connection_pool_usage,
        }

        assert isinstance(metrics_dict, dict)
        assert metrics_dict["cache_hit_rate"] == 0.85
        assert metrics_dict["response_time"] == 50.0


if __name__ == "__main__":
    pytest.main([__file__])
