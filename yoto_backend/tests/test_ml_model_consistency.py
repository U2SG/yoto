"""
测试ML模型权重初始化的一致性

验证模型权重的初始化与实际使用是否一致
"""

import pytest
import numpy as np
import time
from app.core.permission_ml import MLPerformancePredictor, PerformanceMetrics


class TestMLModelConsistency:
    """测试ML模型一致性"""

    def test_weights_initialization(self):
        """测试权重初始化的正确性"""
        predictor = MLPerformancePredictor()

        # 验证所有模型的权重都被正确初始化为2元素数组
        for metric_name, model in predictor.models.items():
            weights = model["weights"]
            assert isinstance(weights, np.ndarray)
            assert weights.shape == (2,)  # 应该是2元素数组 [斜率, 截距]
            assert weights[0] == 0.0  # 初始斜率
            assert weights[1] == 0.0  # 初始截距

    def test_weights_update_consistency(self):
        """测试权重更新的一致性"""
        predictor = MLPerformancePredictor()

        # 添加一些测试数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.8 + i * 0.01,  # 递增趋势
                response_time=50.0 + i * 2,  # 递增趋势
                memory_usage=0.6 + i * 0.02,  # 递增趋势
                cpu_usage=0.3 + i * 0.01,
                error_rate=0.01 + i * 0.001,
                qps=1000.0 + i * 10,
                lock_timeout_rate=0.02 + i * 0.001,
                connection_pool_usage=0.7 + i * 0.01,
            )
            predictor.add_performance_data(metrics)

        # 验证权重更新后仍然是2元素数组
        for metric_name, model in predictor.models.items():
            weights = model["weights"]
            assert isinstance(weights, np.ndarray)
            assert weights.shape == (2,)  # 仍然是2元素数组
            assert len(weights) == 2  # 确保长度正确

    def test_polyfit_consistency(self):
        """测试np.polyfit返回值的正确性"""
        # 创建测试数据
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([2, 4, 6, 8, 10])  # 线性关系 y = 2x

        # 使用np.polyfit拟合
        coefficients = np.polyfit(x, y, 1)

        # 验证返回值
        assert isinstance(coefficients, np.ndarray)
        assert coefficients.shape == (2,)  # 应该是2元素数组
        assert len(coefficients) == 2  # 长度应该是2

        # 验证系数值（应该接近 [2, 0] 因为 y = 2x）
        assert abs(coefficients[0] - 2.0) < 0.1  # 斜率接近2
        assert abs(coefficients[1] - 0.0) < 0.1  # 截距接近0

    def test_prediction_consistency(self):
        """测试预测的一致性"""
        predictor = MLPerformancePredictor()

        # 添加足够的数据来触发模型更新
        for i in range(15):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.8 + i * 0.01,
                response_time=50.0 + i * 2,
                memory_usage=0.6 + i * 0.02,
                cpu_usage=0.3 + i * 0.01,
                error_rate=0.01 + i * 0.001,
                qps=1000.0 + i * 10,
                lock_timeout_rate=0.02 + i * 0.001,
                connection_pool_usage=0.7 + i * 0.01,
            )
            predictor.add_performance_data(metrics)

        # 测试预测
        result = predictor.predict_metric("cache_hit_rate")
        assert result is not None
        assert hasattr(result, "predicted_value")
        assert hasattr(result, "current_value")
        assert hasattr(result, "confidence")
        assert hasattr(result, "trend")

    def test_model_structure_consistency(self):
        """测试模型结构的一致性"""
        predictor = MLPerformancePredictor()

        # 验证每个模型都有正确的结构
        expected_metrics = [
            "cache_hit_rate",
            "response_time",
            "memory_usage",
            "cpu_usage",
            "error_rate",
            "qps",
            "lock_timeout_rate",
        ]

        for metric_name in expected_metrics:
            assert metric_name in predictor.models

            model = predictor.models[metric_name]
            assert "weights" in model
            assert "bias" in model
            assert "last_update" in model
            assert "accuracy" in model

            # 验证权重是2元素数组
            weights = model["weights"]
            assert isinstance(weights, np.ndarray)
            assert weights.shape == (2,)

    def test_weights_usage_consistency(self):
        """测试权重使用的一致性"""
        predictor = MLPerformancePredictor()

        # 添加数据
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.8 + i * 0.01,
                response_time=50.0 + i * 2,
                memory_usage=0.6 + i * 0.02,
                cpu_usage=0.3 + i * 0.01,
                error_rate=0.01 + i * 0.001,
                qps=1000.0 + i * 10,
                lock_timeout_rate=0.02 + i * 0.001,
                connection_pool_usage=0.7 + i * 0.01,
            )
            predictor.add_performance_data(metrics)

        # 验证预测时权重使用正确
        for metric_name in predictor.models.keys():
            model = predictor.models[metric_name]
            weights = model["weights"]

            # 验证权重可以用于线性预测
            current_time = time.time()
            future_time = current_time + 10

            # 这应该不会抛出异常
            predicted_value = weights[0] * future_time + weights[1]
            assert isinstance(predicted_value, (int, float, np.number))


def test_numpy_polyfit_behavior():
    """测试numpy.polyfit的行为"""
    # 创建简单的线性数据
    x = np.array([1, 2, 3])
    y = np.array([3, 5, 7])  # y = 2x + 1

    # 使用polyfit
    coefficients = np.polyfit(x, y, 1)

    # 验证返回值
    assert isinstance(coefficients, np.ndarray)
    assert coefficients.shape == (2,)
    assert len(coefficients) == 2

    # 验证系数
    slope = coefficients[0]
    intercept = coefficients[1]

    # 应该接近 y = 2x + 1
    assert abs(slope - 2.0) < 0.1
    assert abs(intercept - 1.0) < 0.1

    # 验证预测
    predicted_y = slope * 4 + intercept  # 预测 x=4 时的值
    expected_y = 2 * 4 + 1  # 应该是 9
    assert abs(predicted_y - expected_y) < 0.1


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
