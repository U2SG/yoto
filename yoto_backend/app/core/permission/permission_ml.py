"""
机器学习预测和自适应优化模块

提供基于历史数据的性能预测、自适应配置调整、异常检测等功能
"""

import time
import json
import threading
import numpy as np
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict
from enum import Enum

from .permission_resilience import get_resilience_controller
from .permission_events import EventSubscriber, RESILIENCE_EVENTS_CHANNEL
from .permission_resilience import REDIS_AVAILABLE

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """优化策略枚举"""

    CONSERVATIVE = "conservative"  # 保守策略
    AGGRESSIVE = "aggressive"  # 激进策略
    ADAPTIVE = "adaptive"  # 自适应策略


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    timestamp: float
    cache_hit_rate: float
    response_time: float
    memory_usage: float
    cpu_usage: float
    error_rate: float
    qps: float
    lock_timeout_rate: float
    connection_pool_usage: float


@dataclass
class PredictionResult:
    """
    预测结果数据类

    用于存储机器学习模型对系统性能指标的预测结果，包括当前值、预测值、置信度等信息，
    以及基于预测结果生成的建议和紧急程度评估。

    Attributes:
        metric_name (str): 指标名称
        current_value (float): 当前值
        predicted_value (float): 预测值
        confidence (float): 预测置信度，范围通常在0-1之间
        trend (str): 趋势方向，可能的值包括"increasing"(上升)、"decreasing"(下降)、"stable"(稳定)
        recommendation (str): 基于预测结果的建议操作
        urgency_level (str): 紧急程度分级，可能的值包括"low"(低)、"medium"(中)、"high"(高)、"critical"(紧急)
        confidence_score (float): 信心分数，用于自动应用决策，范围0-1
    """

    metric_name: str
    current_value: float
    predicted_value: float
    confidence: float
    trend: str  # "increasing", "decreasing", "stable"
    recommendation: str
    urgency_level: str  # "low", "medium", "high", "critical"
    confidence_score: float = 0.0  # 信心分数，用于自动应用决策


class MLPerformancePredictor:
    """机器学习性能预测器"""

    def __init__(self, history_window: int = 1000, prediction_horizon: int = 10):
        self.history_window = history_window
        self.prediction_horizon = prediction_horizon
        self.performance_history = deque(maxlen=history_window)
        self.models = {}
        self.lock = threading.Lock()

        # 初始化预测模型
        self._initialize_models()

    def _initialize_models(self):
        """初始化预测模型"""
        metrics = [
            "cache_hit_rate",
            "response_time",
            "memory_usage",
            "cpu_usage",
            "error_rate",
            "qps",
            "lock_timeout_rate",
        ]

        for metric in metrics:
            self.models[metric] = {
                "weights": np.array([0.0, 0.0]),  # 线性模型权重 [斜率, 截距]
                "bias": 0.0,
                "last_update": time.time(),
                "accuracy": 0.0,
            }

    def add_performance_data(self, metrics: PerformanceMetrics):
        """添加性能数据"""
        with self.lock:
            self.performance_history.append(metrics)
            self._update_models()

    def _update_models(self):
        """更新预测模型"""
        if len(self.performance_history) < 10:
            return

        # 转换为numpy数组
        data = list(self.performance_history)
        timestamps = np.array([m.timestamp for m in data])

        for metric_name in self.models.keys():
            values = np.array([getattr(m, metric_name) for m in data])

            # 简单的线性回归模型
            if len(values) >= 5:
                # 使用最近5个点进行预测
                recent_values = values[-5:]
                recent_times = timestamps[-5:]

                # 计算趋势 - np.polyfit返回 [斜率, 截距]
                if len(recent_values) >= 2:
                    trend = np.polyfit(recent_times, recent_values, 1)
                    self.models[metric_name]["weights"] = trend  # [斜率, 截距]
                    self.models[metric_name]["last_update"] = time.time()

    def predict_metric(self, metric_name: str, horizon: int = None) -> PredictionResult:
        """预测单个指标"""
        if horizon is None:
            horizon = self.prediction_horizon

        if metric_name not in self.models:
            return None

        with self.lock:
            if len(self.performance_history) < 5:
                return None

            current_time = time.time()
            current_value = getattr(self.performance_history[-1], metric_name)

            # 使用模型进行预测
            model = self.models[metric_name]
            weights = model["weights"]  # [斜率, 截距]

            # 简单线性预测: y = slope * x + intercept
            future_time = current_time + horizon
            predicted_value = (
                weights[0] * future_time + weights[1]
            )  # slope * time + intercept

            # 修复：添加合理的边界检查
            if metric_name == "response_time":
                predicted_value = max(
                    0.001, min(predicted_value, 10.0)
                )  # 响应时间在1ms到10s之间
            elif metric_name == "memory_usage":
                predicted_value = max(
                    0.0, min(predicted_value, 1.0)
                )  # 内存使用率在0-100%之间
            elif metric_name == "cache_hit_rate":
                predicted_value = max(
                    0.0, min(predicted_value, 1.0)
                )  # 缓存命中率在0-100%之间
            elif metric_name == "error_rate":
                predicted_value = max(
                    0.0, min(predicted_value, 1.0)
                )  # 错误率在0-100%之间
            elif metric_name == "qps":
                predicted_value = max(
                    0.0, min(predicted_value, 10000.0)
                )  # QPS在0-10000之间
            else:
                # 其他指标使用默认边界
                predicted_value = max(0.0, min(predicted_value, 1000.0))

            # 计算趋势
            if len(self.performance_history) >= 2:
                recent_values = [
                    getattr(m, metric_name) for m in list(self.performance_history)[-5:]
                ]
                if len(recent_values) >= 2:
                    trend_slope = np.polyfit(
                        range(len(recent_values)), recent_values, 1
                    )[0]
                    if trend_slope > 0.01:
                        trend = "increasing"
                    elif trend_slope < -0.01:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # 计算置信度（基于历史准确性）
            confidence = min(0.95, model["accuracy"] + 0.5)

            # 生成建议
            recommendation = self._generate_recommendation(
                metric_name, current_value, predicted_value, trend
            )

            # 计算紧急程度
            urgency_level = self._calculate_urgency_level(
                metric_name, current_value, predicted_value
            )

            # 计算信心分数
            confidence_score = self._calculate_confidence_score(
                metric_name, current_value, predicted_value, confidence, urgency_level
            )

            return PredictionResult(
                metric_name=metric_name,
                current_value=current_value,
                predicted_value=predicted_value,
                confidence=confidence,
                trend=trend,
                recommendation=recommendation,
                urgency_level=urgency_level,
                confidence_score=confidence_score,
            )

    def _generate_recommendation(
        self, metric_name: str, current: float, predicted: float, trend: str
    ) -> str:
        """生成优化建议"""
        recommendations = {
            "cache_hit_rate": {
                "decreasing": "建议增加缓存大小或优化缓存策略",
                "increasing": "缓存性能良好，可考虑进一步优化",
                "stable": "缓存性能稳定",
            },
            "response_time": {
                "increasing": "建议优化数据库查询或增加连接池大小",
                "decreasing": "响应时间改善中",
                "stable": "响应时间稳定",
            },
            "memory_usage": {
                "increasing": "建议检查内存泄漏或增加内存限制",
                "decreasing": "内存使用优化中",
                "stable": "内存使用稳定",
            },
            "error_rate": {
                "increasing": "建议检查系统错误日志并修复问题",
                "decreasing": "错误率下降中",
                "stable": "错误率稳定",
            },
            "qps": {
                "decreasing": "建议优化系统性能或增加资源",
                "increasing": "系统吞吐量提升中",
                "stable": "系统吞吐量稳定",
            },
        }

        return recommendations.get(metric_name, {}).get(trend, "建议监控该指标")

    def _calculate_urgency_level(
        self, metric_name: str, current: float, predicted: float
    ) -> str:
        """计算紧急程度"""
        thresholds = {
            "cache_hit_rate": {"critical": 0.5, "high": 0.7, "medium": 0.8},
            "response_time": {"critical": 1000, "high": 500, "medium": 200},
            "memory_usage": {"critical": 0.9, "high": 0.8, "medium": 0.7},
            "error_rate": {"critical": 0.1, "high": 0.05, "medium": 0.02},
            "qps": {"critical": 100, "high": 500, "medium": 1000},
        }

        if metric_name not in thresholds:
            return "low"

        threshold = thresholds[metric_name]

        lower_is_better_metrics = frozenset(["cache_hit_rate", "qps"])

        if metric_name in lower_is_better_metrics:
            if current <= threshold.get("critical", -1):
                return "critical"
            if current <= threshold.get("high", -1):
                return "high"
            if current <= threshold.get("medium", -1):
                return "medium"
        else:
            if current > threshold.get("critical", float("inf")):
                return "critical"
            if current > threshold.get("high", float("inf")):
                return "high"
            if current > threshold.get("medium", float("inf")):
                return "medium"

        return "low"

    def _calculate_confidence_score(
        self,
        metric_name: str,
        current: float,
        predicted: float,
        confidence: float,
        urgency_level: str,
    ) -> float:
        """
        计算信心分数，用于自动应用决策

        Args:
            metric_name: 指标名称
            current: 当前值
            predicted: 预测值
            confidence: 预测置信度
            urgency_level: 紧急程度

        Returns:
            float: 信心分数，范围0-1
        """
        # 基础信心分数基于预测置信度
        base_confidence = confidence

        # 根据紧急程度调整信心分数
        urgency_multipliers = {
            "critical": 1.2,  # 紧急情况下提高信心
            "high": 1.1,
            "medium": 1.0,
            "low": 0.8,  # 低紧急情况下降低信心
        }

        urgency_multiplier = urgency_multipliers.get(urgency_level, 1.0)

        # 根据预测变化幅度调整信心分数
        if current > 0:
            change_ratio = abs(predicted - current) / current
            if change_ratio > 0.5:  # 变化幅度大，降低信心
                change_multiplier = 0.8
            elif change_ratio > 0.2:  # 中等变化
                change_multiplier = 0.9
            else:  # 小变化，保持信心
                change_multiplier = 1.0
        else:
            change_multiplier = 1.0

        # 计算最终信心分数
        final_confidence = base_confidence * urgency_multiplier * change_multiplier

        # 确保在0-1范围内
        return max(0.0, min(1.0, final_confidence))


class AdaptiveOptimizer:
    """自适应优化器"""

    def __init__(self, strategy: OptimizationStrategy = OptimizationStrategy.ADAPTIVE):
        self.strategy = strategy
        self.predictor = MLPerformancePredictor()
        self.current_config = self._get_default_config()
        self.optimization_history = []
        self.config_update_callbacks = []  # 配置更新回调列表
        self.lock = threading.Lock()

        # 优化参数范围
        self.parameter_ranges = {
            "connection_pool_size": (10, 200),
            "socket_timeout": (0.1, 2.0),
            "lock_timeout": (1.0, 10.0),
            "batch_size": (50, 500),
            "cache_max_size": (500, 2000),
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "connection_pool_size": 100,
            "socket_timeout": 0.5,
            "lock_timeout": 3.0,
            "batch_size": 200,
            "cache_max_size": 1000,
        }

    def update_performance_metrics(self, metrics: PerformanceMetrics):
        """更新性能指标"""
        self.predictor.add_performance_data(metrics)
        self._check_and_optimize()

    def _check_and_optimize(self):
        """检查并执行优化"""
        predictions = []

        # 获取所有指标的预测
        for metric_name in [
            "cache_hit_rate",
            "response_time",
            "memory_usage",
            "error_rate",
            "qps",
        ]:
            prediction = self.predictor.predict_metric(metric_name)
            if prediction:
                predictions.append(prediction)

        # 分析预测结果
        critical_issues = [
            p for p in predictions if p.urgency_level in ["critical", "high"]
        ]

        if critical_issues:
            self._perform_optimization(critical_issues)

    def _perform_optimization(self, issues: List[PredictionResult]):
        """执行优化"""
        with self.lock:
            # 计算所有问题的平均信心分数
            avg_confidence_score = sum(
                issue.confidence_score for issue in issues
            ) / len(issues)

            # 检查是否存在手动配置覆盖
            controller = get_resilience_controller()
            overrides = controller.get_config_overrides()
            has_manual_overrides = len(overrides) > 0

            # 自动应用阈值（可配置）
            auto_apply_threshold = 0.95  # 95%信心分数

            # 判断是否自动应用优化
            should_auto_apply = (
                avg_confidence_score >= auto_apply_threshold
                and not has_manual_overrides
            )

            optimization_plan = self._create_optimization_plan(issues)

            if optimization_plan:
                if should_auto_apply:
                    # 自动应用优化
                    self._apply_optimization(optimization_plan)

                    # 发布自动应用事件
                    self._publish_auto_applied_event(
                        issues, optimization_plan, avg_confidence_score
                    )

                    logger.info(
                        f"自动应用ML优化: {optimization_plan}, 平均信心分数: {avg_confidence_score:.3f}"
                    )
                else:
                    # 仅记录建议，不自动应用
                    logger.info(
                        f"ML优化建议（未自动应用）: {optimization_plan}, 平均信心分数: {avg_confidence_score:.3f}"
                    )
                    if has_manual_overrides:
                        logger.info(
                            f"存在手动配置覆盖，阻止自动应用: {list(overrides.keys())}"
                        )
                    else:
                        logger.info(
                            f"信心分数不足，需要人工确认: {avg_confidence_score:.3f} < {auto_apply_threshold}"
                        )

                # 记录优化历史
                self.optimization_history.append(
                    {
                        "timestamp": time.time(),
                        "issues": [asdict(issue) for issue in issues],
                        "optimization_plan": optimization_plan,
                        "strategy": self.strategy.value,
                        "auto_applied": should_auto_apply,
                        "avg_confidence_score": avg_confidence_score,
                        "has_manual_overrides": has_manual_overrides,
                    }
                )

    def _create_optimization_plan(
        self, issues: List[PredictionResult]
    ) -> Dict[str, Any]:
        """创建优化计划"""
        plan = {}

        for issue in issues:
            if issue.metric_name == "cache_hit_rate" and issue.trend == "decreasing":
                if self.strategy == OptimizationStrategy.AGGRESSIVE:
                    plan["cache_max_size"] = min(
                        2000, self.current_config["cache_max_size"] * 1.5
                    )
                elif self.strategy == OptimizationStrategy.CONSERVATIVE:
                    plan["cache_max_size"] = min(
                        1500, self.current_config["cache_max_size"] * 1.2
                    )
                else:  # ADAPTIVE
                    plan["cache_max_size"] = min(
                        1800, self.current_config["cache_max_size"] * 1.3
                    )

            elif issue.metric_name == "response_time" and issue.trend == "increasing":
                if self.strategy == OptimizationStrategy.AGGRESSIVE:
                    plan["connection_pool_size"] = min(
                        200, self.current_config["connection_pool_size"] * 1.5
                    )
                    plan["socket_timeout"] = max(
                        0.1, self.current_config["socket_timeout"] * 0.8
                    )
                elif self.strategy == OptimizationStrategy.CONSERVATIVE:
                    plan["connection_pool_size"] = min(
                        150, self.current_config["connection_pool_size"] * 1.2
                    )
                    plan["socket_timeout"] = max(
                        0.2, self.current_config["socket_timeout"] * 0.9
                    )
                else:  # ADAPTIVE
                    plan["connection_pool_size"] = min(
                        180, self.current_config["connection_pool_size"] * 1.3
                    )
                    plan["socket_timeout"] = max(
                        0.15, self.current_config["socket_timeout"] * 0.85
                    )

            elif issue.metric_name == "error_rate" and issue.trend == "increasing":
                if self.strategy == OptimizationStrategy.AGGRESSIVE:
                    plan["lock_timeout"] = min(
                        10.0, self.current_config["lock_timeout"] * 1.5
                    )
                elif self.strategy == OptimizationStrategy.CONSERVATIVE:
                    plan["lock_timeout"] = min(
                        8.0, self.current_config["lock_timeout"] * 1.2
                    )
                else:  # ADAPTIVE
                    plan["lock_timeout"] = min(
                        9.0, self.current_config["lock_timeout"] * 1.3
                    )

        return plan

    def _apply_optimization(self, plan: Dict[str, Any]):
        """
        应用优化计划

        在应用ML优化配置前，检查是否存在手动配置覆盖
        """
        with self.lock:
            # 获取韧性控制器，检查配置覆盖
            controller = get_resilience_controller()

            # 检查是否存在手动配置覆盖
            overrides = controller.get_config_overrides()
            if overrides:
                logger.warning(
                    f"检测到手动配置覆盖，ML优化将被限制。覆盖项: {list(overrides.keys())}"
                )

                # 过滤掉有覆盖的配置项
                filtered_plan = {}
                for param, value in plan.items():
                    # 检查该参数是否有手动覆盖
                    has_override = False
                    for override_key in overrides.keys():
                        if param in override_key:  # 简单匹配，实际可能需要更精确的匹配
                            has_override = True
                            logger.info(f"跳过ML优化参数 '{param}'，存在手动覆盖")
                            break

                    if not has_override:
                        filtered_plan[param] = value

                plan = filtered_plan

            # 应用优化配置
            for param, value in plan.items():
                if param in self.parameter_ranges:
                    min_val, max_val = self.parameter_ranges[param]
                    self.current_config[param] = max(min_val, min(max_val, value))

            # 通知所有注册的回调函数
            if plan:
                self._notify_config_update(plan)
                logger.info(f"应用ML优化配置: {plan}")
            else:
                logger.info("由于存在手动配置覆盖，未应用任何ML优化配置")

    def get_optimized_config(self) -> Dict[str, Any]:
        """获取优化后的配置"""
        with self.lock:
            return self.current_config.copy()

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        with self.lock:
            return self.optimization_history.copy()

    def set_strategy(self, strategy: OptimizationStrategy):
        """设置优化策略"""
        self.strategy = strategy

    def register_config_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        注册配置更新回调函数

        Args:
            callback: 回调函数，接收优化配置字典作为参数
        """
        with self.lock:
            if callback not in self.config_update_callbacks:
                self.config_update_callbacks.append(callback)
                logger.info(
                    f"注册配置更新回调函数: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
                )

    def unregister_config_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        注销配置更新回调函数

        Args:
            callback: 要注销的回调函数
        """
        with self.lock:
            if callback in self.config_update_callbacks:
                self.config_update_callbacks.remove(callback)
                logger.info(
                    f"注销配置更新回调函数: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
                )

    def _notify_config_update(self, plan: Dict[str, Any]):
        """
        通知所有注册的回调函数配置已更新

        Args:
            plan: 优化配置计划
        """
        with self.lock:
            for callback in self.config_update_callbacks:
                try:
                    callback(plan)
                    logger.debug(
                        f"成功调用配置更新回调: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
                    )
                except Exception as e:
                    logger.error(
                        f"配置更新回调执行失败: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}, 错误: {e}"
                    )

    def _publish_auto_applied_event(
        self,
        issues: List[PredictionResult],
        optimization_plan: Dict[str, Any],
        avg_confidence_score: float,
    ):
        """发布自动应用事件"""
        try:
            from .permission_events import get_event_publisher

            event_publisher = get_event_publisher()
            if event_publisher:
                event_data = {
                    "issues": [asdict(issue) for issue in issues],
                    "optimization_plan": optimization_plan,
                    "avg_confidence_score": avg_confidence_score,
                    "timestamp": time.time(),
                    "auto_applied": True,
                }

                event_publisher.publish(
                    channel="ml:optimization:auto_applied",
                    event_name="ml.optimization.auto_applied",
                    payload=event_data,
                    source_module="ml_optimizer",
                )

                logger.info(
                    f"发布ML自动应用事件: {len(issues)}个问题, 平均信心分数: {avg_confidence_score:.3f}"
                )

        except Exception as e:
            logger.error(f"发布ML自动应用事件失败: {e}")


class AnomalyDetector:
    """异常检测器"""

    def __init__(self, window_size: int = 100, threshold_std: float = 2.0):
        self.window_size = window_size
        self.threshold_std = threshold_std
        self.metric_windows = defaultdict(lambda: deque(maxlen=window_size))
        self.anomaly_history = []
        self.lock = threading.Lock()

    def detect_anomalies(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """检测异常"""
        anomalies = []

        with self.lock:
            for metric_name in [
                "cache_hit_rate",
                "response_time",
                "memory_usage",
                "error_rate",
                "qps",
            ]:
                value = getattr(metrics, metric_name)
                window = self.metric_windows[metric_name]

                if len(window) >= 10:  # 需要足够的数据点
                    mean = np.mean(window)
                    std = np.std(window)

                    if std > 0:  # 避免除零
                        z_score = abs(value - mean) / std

                        if z_score > self.threshold_std:
                            anomalies.append(
                                {
                                    "metric": metric_name,
                                    "value": value,
                                    "expected_range": (mean - 2 * std, mean + 2 * std),
                                    "z_score": z_score,
                                    "timestamp": metrics.timestamp,
                                    "severity": "high" if z_score > 3 else "medium",
                                }
                            )

                window.append(value)

        if anomalies:
            self.anomaly_history.extend(anomalies)

        return anomalies

    def get_anomaly_history(self) -> List[Dict[str, Any]]:
        """获取异常历史"""
        with self.lock:
            return self.anomaly_history.copy()


class MLPerformanceMonitor:
    """机器学习性能监控器"""

    def __init__(self):
        self.predictor = MLPerformancePredictor()
        self.optimizer = AdaptiveOptimizer()
        self.anomaly_detector = AnomalyDetector()
        self.lock = threading.RLock()  # 使用RLock以支持重入

        # 核心：系统损伤状态管理器
        # 存储当前活跃的韧性事件及其预计的恢复时间戳
        self.active_impairments: Dict[str, float] = {}

        controller = get_resilience_controller()
        if controller.config_source and REDIS_AVAILABLE:
            self.subscriber = EventSubscriber(controller.config_source)
            self.subscriber.subscribe(
                RESILIENCE_EVENTS_CHANNEL, self._handle_resilience_event
            )
            self.subscriber.start()
            logger.info("MLPerformanceMonitor has subscribed to resilience events.")

    # in ml_optimizer.py -> MLPerformanceMonitor class

    def _handle_resilience_event(self, event: Dict[str, Any]):
        """
        处理从韧性模块接收到的事件，并更新系统的“损伤状态”。
        """
        try:
            event_name = event.get("event_name")
            payload = event.get("payload", {})
            impairment_key = f"{event_name}:{payload.get('name')}"  # e.g., "resilience.circuit_breaker.opened:db_query"

            # 默认的损伤持续时间（例如5分钟）
            DEFAULT_IMPAIRMENT_DURATION = 300

            expiry_time = 0

            if (
                "opened" in event_name
                or "activated" in event_name
                or "triggered" in event_name
            ):
                # --- 这是一个“系统受损”的信号 ---
                recovery_timeout = payload.get(
                    "recovery_timeout", DEFAULT_IMPAIRMENT_DURATION
                )
                # 我们设置的过期时间应该比实际恢复时间稍长，以确保覆盖整个恢复期
                expiry_time = time.time() + recovery_timeout + 15  # 增加15秒的缓冲

                with self.lock:
                    self.active_impairments[impairment_key] = expiry_time
                logger.warning(
                    f"System impairment detected: {impairment_key}. "
                    f"ML module will treat data cautiously until {time.ctime(expiry_time)}."
                )

            elif "closed" in event_name or "deactivated" in event_name:
                # --- 这是一个“系统恢复”的信号 ---
                with self.lock:
                    if impairment_key in self.active_impairments:
                        del self.active_impairments[impairment_key]
                logger.info(
                    f"System impairment resolved: {impairment_key}. ML module resumes normal data processing."
                )

        except Exception as e:
            logger.error(f"Error handling resilience event: {e}", exc_info=True)

    # in ml_optimizer.py -> MLPerformanceMonitor class

    def is_system_impaired(self) -> bool:
        """检查当前是否存在任何活跃的系统损伤。"""
        with self.lock:
            current_time = time.time()
            # 找出所有已过期的损伤
            expired_keys = [
                key
                for key, expiry in self.active_impairments.items()
                if current_time > expiry
            ]
            # 清理过期的损伤
            for key in expired_keys:
                del self.active_impairments[key]
                logger.info(f"System impairment expired: {key}.")

            # 如果清理后仍有损伤，则系统处于受损状态
            return bool(self.active_impairments)

    # in ml_optimizer.py -> MLPerformanceMonitor class

    def feed_metrics(self, metrics: PerformanceMetrics):
        """
        注入性能指标数据。
        如果系统当前处于受损状态，则忽略本次数据以避免模型污染。
        """
        # 在所有操作之前，首先检查系统状态
        if self.is_system_impaired():
            logger.warning(
                f"System is impaired. Ignoring performance metrics at {metrics.timestamp} to prevent model pollution."
            )
            return  # 直接返回，不进行任何处理

        # --- 只有在系统健康时，才执行以下逻辑 ---
        with self.lock:
            try:
                self.predictor.add_performance_data(metrics)
                anomalies = self.anomaly_detector.detect_anomalies(metrics)
                if anomalies:
                    logger.warning(f"Detected anomalies: {anomalies}")
                self.optimizer.update_performance_metrics(metrics)
                logger.debug(
                    f"ML module processed performance metrics: {metrics.timestamp}"
                )
            except Exception as e:
                logger.error(f"ML module failed to process performance metrics: {e}")

    def get_predictions(self) -> List[PredictionResult]:
        """获取所有指标的预测"""
        predictions = []
        metrics = [
            "cache_hit_rate",
            "response_time",
            "memory_usage",
            "error_rate",
            "qps",
        ]

        for metric in metrics:
            prediction = self.predictor.predict_metric(metric)
            if prediction:
                predictions.append(prediction)

        return predictions

    def get_optimized_config(self) -> Dict[str, Any]:
        """获取优化后的配置"""
        return self.optimizer.get_optimized_config()

    def get_anomalies(self) -> List[Dict[str, Any]]:
        """获取异常检测结果"""
        return self.anomaly_detector.get_anomaly_history()

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        return self.optimizer.get_optimization_history()

    def set_optimization_strategy(self, strategy: OptimizationStrategy):
        """设置优化策略"""
        self.optimizer.set_strategy(strategy)

    def register_config_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        注册配置更新回调函数

        Args:
            callback: 回调函数，接收优化配置字典作为参数
        """
        self.optimizer.register_config_update_callback(callback)

    def unregister_config_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        注销配置更新回调函数

        Args:
            callback: 要注销的回调函数
        """
        self.optimizer.unregister_config_update_callback(callback)


# 全局实例
_ml_monitor = None


def get_ml_performance_monitor() -> MLPerformanceMonitor:
    """获取机器学习性能监控器实例"""
    global _ml_monitor
    if _ml_monitor is None:
        _ml_monitor = MLPerformanceMonitor()
    return _ml_monitor


def get_ml_predictions() -> List[Dict[str, Any]]:
    """获取机器学习预测结果"""
    monitor = get_ml_performance_monitor()
    predictions = monitor.get_predictions()
    return [asdict(p) for p in predictions]


def get_ml_optimized_config() -> Dict[str, Any]:
    """获取机器学习优化的配置"""
    monitor = get_ml_performance_monitor()
    return monitor.get_optimized_config()


def get_ml_anomalies() -> List[Dict[str, Any]]:
    """获取机器学习异常检测结果"""
    monitor = get_ml_performance_monitor()
    return monitor.get_anomalies()


def set_ml_optimization_strategy(strategy: str):
    """设置机器学习优化策略"""
    monitor = get_ml_performance_monitor()
    strategy_enum = OptimizationStrategy(strategy)
    monitor.set_optimization_strategy(strategy_enum)


def feed_ml_metrics(metrics: PerformanceMetrics):
    """向机器学习模块注入性能指标数据"""
    monitor = get_ml_performance_monitor()
    monitor.feed_metrics(metrics)


def register_ml_config_callback(callback: Callable[[Dict[str, Any]], None]):
    """注册ML配置更新回调函数"""
    monitor = get_ml_performance_monitor()
    monitor.register_config_update_callback(callback)


def unregister_ml_config_callback(callback: Callable[[Dict[str, Any]], None]):
    """注销ML配置更新回调函数"""
    monitor = get_ml_performance_monitor()
    monitor.unregister_config_update_callback(callback)
