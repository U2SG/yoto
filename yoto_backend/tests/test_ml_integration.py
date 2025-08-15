"""
测试ML模块与主监控模块的集成

验证数据注入和ML功能是否正常工作
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.permission_monitor import (
    get_permission_monitor,
    record_cache_hit_rate,
    record_response_time,
    record_error_rate,
    record_qps,
)
from app.core.permission_ml import (
    get_ml_performance_monitor,
    PerformanceMetrics,
    MLPerformancePredictor,
    AdaptiveOptimizer,
    AnomalyDetector,
)


class TestMLIntegration:
    """测试ML模块集成"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = get_permission_monitor()
        self.ml_monitor = get_ml_performance_monitor()

    def test_ml_monitor_initialization(self):
        """测试ML监控器初始化"""
        assert self.ml_monitor is not None
        assert hasattr(self.ml_monitor, "predictor")
        assert hasattr(self.ml_monitor, "optimizer")
        assert hasattr(self.ml_monitor, "anomaly_detector")
        assert hasattr(self.ml_monitor, "feed_metrics")

    def test_feed_metrics_method(self):
        """测试feed_metrics方法"""
        # 创建测试性能指标
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

        # 调用feed_metrics
        self.ml_monitor.feed_metrics(metrics)

        # 验证数据已被处理
        # 注意：由于ML模块需要足够的历史数据才能产生预测，这里只验证方法调用成功
        assert True  # 如果没有异常，说明调用成功

    @patch("app.core.permission_monitor.ML_AVAILABLE", True)
    def test_monitor_record_integrates_with_ml(self):
        """测试监控记录与ML模块的集成"""
        # 记录一些性能指标
        record_cache_hit_rate(0.85)
        record_response_time(50.0)
        record_error_rate(0.01)
        record_qps(1000.0)

        # 验证ML模块已接收到数据
        # 这里主要验证没有异常发生
        assert True

    def test_ml_predictor_functionality(self):
        """测试ML预测器功能"""
        predictor = MLPerformancePredictor()

        # 添加一些测试数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + (i * 0.01),
                response_time=50.0 + (i * 2),
                memory_usage=0.6 + (i * 0.02),
                cpu_usage=0.3 + (i * 0.01),
                error_rate=0.01 + (i * 0.001),
                qps=1000.0 + (i * 10),
                lock_timeout_rate=0.02 + (i * 0.001),
                connection_pool_usage=0.7 + (i * 0.01),
            )
            predictor.add_performance_data(metrics)

        # 测试预测功能
        prediction = predictor.predict_metric("cache_hit_rate")
        assert prediction is not None
        assert hasattr(prediction, "metric_name")
        assert hasattr(prediction, "current_value")
        assert hasattr(prediction, "predicted_value")
        assert hasattr(prediction, "confidence")
        assert hasattr(prediction, "trend")
        assert hasattr(prediction, "recommendation")
        assert hasattr(prediction, "urgency_level")

    def test_adaptive_optimizer_functionality(self):
        """测试自适应优化器功能"""
        optimizer = AdaptiveOptimizer()

        # 添加一些测试数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + (i * 0.01),
                response_time=50.0 + (i * 2),
                memory_usage=0.6 + (i * 0.02),
                cpu_usage=0.3 + (i * 0.01),
                error_rate=0.01 + (i * 0.001),
                qps=1000.0 + (i * 10),
                lock_timeout_rate=0.02 + (i * 0.001),
                connection_pool_usage=0.7 + (i * 0.01),
            )
            optimizer.update_performance_metrics(metrics)

        # 测试获取优化配置
        config = optimizer.get_optimized_config()
        assert isinstance(config, dict)
        assert "connection_pool_size" in config
        assert "socket_timeout" in config
        assert "lock_timeout" in config
        assert "batch_size" in config
        assert "cache_max_size" in config

    def test_anomaly_detector_functionality(self):
        """测试异常检测器功能"""
        detector = AnomalyDetector()

        # 添加一些正常数据
        for i in range(20):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85,
                response_time=50.0,
                memory_usage=0.6,
                cpu_usage=0.3,
                error_rate=0.01,
                qps=1000.0,
                lock_timeout_rate=0.02,
                connection_pool_usage=0.7,
            )
            detector.detect_anomalies(metrics)

        # 添加一个异常数据
        anomaly_metrics = PerformanceMetrics(
            timestamp=time.time() + 100,
            cache_hit_rate=0.3,  # 异常低的缓存命中率
            response_time=500.0,  # 异常高的响应时间
            memory_usage=0.9,  # 异常高的内存使用
            cpu_usage=0.8,  # 异常高的CPU使用
            error_rate=0.1,  # 异常高的错误率
            qps=100.0,  # 异常低的QPS
            lock_timeout_rate=0.1,
            connection_pool_usage=0.9,
        )

        anomalies = detector.detect_anomalies(anomaly_metrics)

        # 验证检测到异常
        assert len(anomalies) > 0
        for anomaly in anomalies:
            assert "metric" in anomaly
            assert "value" in anomaly
            assert "expected_range" in anomaly
            assert "z_score" in anomaly
            assert "timestamp" in anomaly
            assert "severity" in anomaly

    def test_ml_monitor_get_predictions(self):
        """测试ML监控器获取预测"""
        # 添加一些测试数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + (i * 0.01),
                response_time=50.0 + (i * 2),
                memory_usage=0.6 + (i * 0.02),
                cpu_usage=0.3 + (i * 0.01),
                error_rate=0.01 + (i * 0.001),
                qps=1000.0 + (i * 10),
                lock_timeout_rate=0.02 + (i * 0.001),
                connection_pool_usage=0.7 + (i * 0.01),
            )
            self.ml_monitor.feed_metrics(metrics)

        # 获取预测
        predictions = self.ml_monitor.get_predictions()
        assert isinstance(predictions, list)

        # 验证预测结果
        if predictions:  # 如果有预测结果
            for prediction in predictions:
                assert hasattr(prediction, "metric_name")
                assert hasattr(prediction, "current_value")
                assert hasattr(prediction, "predicted_value")
                assert hasattr(prediction, "confidence")
                assert hasattr(prediction, "trend")
                assert hasattr(prediction, "recommendation")
                assert hasattr(prediction, "urgency_level")

    def test_ml_monitor_get_optimized_config(self):
        """测试ML监控器获取优化配置"""
        # 添加一些测试数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85 + (i * 0.01),
                response_time=50.0 + (i * 2),
                memory_usage=0.6 + (i * 0.02),
                cpu_usage=0.3 + (i * 0.01),
                error_rate=0.01 + (i * 0.001),
                qps=1000.0 + (i * 10),
                lock_timeout_rate=0.02 + (i * 0.001),
                connection_pool_usage=0.7 + (i * 0.01),
            )
            self.ml_monitor.feed_metrics(metrics)

        # 获取优化配置
        config = self.ml_monitor.get_optimized_config()
        assert isinstance(config, dict)
        assert "connection_pool_size" in config
        assert "socket_timeout" in config
        assert "lock_timeout" in config
        assert "batch_size" in config
        assert "cache_max_size" in config

    def test_ml_monitor_get_anomalies(self):
        """测试ML监控器获取异常"""
        # 添加一些测试数据
        for i in range(20):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.85,
                response_time=50.0,
                memory_usage=0.6,
                cpu_usage=0.3,
                error_rate=0.01,
                qps=1000.0,
                lock_timeout_rate=0.02,
                connection_pool_usage=0.7,
            )
            self.ml_monitor.feed_metrics(metrics)

        # 获取异常历史
        anomalies = self.ml_monitor.get_anomalies()
        assert isinstance(anomalies, list)

        # 验证异常数据结构
        if anomalies:
            for anomaly in anomalies:
                assert "metric" in anomaly
                assert "value" in anomaly
                assert "expected_range" in anomaly
                assert "z_score" in anomaly
                assert "timestamp" in anomaly
                assert "severity" in anomaly


def test_ml_module_import():
    """测试ML模块导入"""
    try:
        from app.core.permission_ml import (
            MLPerformancePredictor,
            AdaptiveOptimizer,
            AnomalyDetector,
            MLPerformanceMonitor,
            PerformanceMetrics,
            PredictionResult,
            OptimizationStrategy,
        )

        assert True
    except ImportError as e:
        pytest.skip(f"ML模块导入失败: {e}")


def test_ml_convenience_functions():
    """测试ML便捷函数"""
    try:
        from app.core.permission_ml import (
            get_ml_performance_monitor,
            get_ml_predictions,
            get_ml_optimized_config,
            get_ml_anomalies,
            set_ml_optimization_strategy,
            feed_ml_metrics,
        )

        # 测试便捷函数调用
        monitor = get_ml_performance_monitor()
        assert monitor is not None

        predictions = get_ml_predictions()
        assert isinstance(predictions, list)

        config = get_ml_optimized_config()
        assert isinstance(config, dict)

        anomalies = get_ml_anomalies()
        assert isinstance(anomalies, list)

        # 测试设置优化策略
        set_ml_optimization_strategy("adaptive")

        # 测试注入指标数据
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
        feed_ml_metrics(metrics)

        assert True
    except ImportError as e:
        pytest.skip(f"ML模块导入失败: {e}")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
