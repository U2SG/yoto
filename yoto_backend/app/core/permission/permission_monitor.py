"""
权限系统监控和告警模块

提供实时的权限系统健康状态监控，包括：
- 性能指标收集和聚合
- 异常检测和告警
- 健康状态检查
- 监控数据持久化

使用SOTA的监控技术，支持：
- 实时指标收集
- 智能阈值检测
- 分级告警系统
- 性能分析报告

支持多种后端存储：
- 内存存储（开发环境）
- Redis存储（生产环境）
- Prometheus推送（生产环境）
- Prometheus暴露（生产环境）
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics

from .permission_events import EventSubscriber, RESILIENCE_EVENTS_CHANNEL
from .metrics_aggregator import get_metrics_aggregator, stage_metric

from .monitor_backends import get_monitor_backend, MonitorBackend

# 导入ML模块
try:
    from .permission_ml import get_ml_performance_monitor, PerformanceMetrics

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.getLogger(__name__).warning("ML模块不可用，将跳过ML功能")

logger = logging.getLogger(__name__)

# ==================== 监控指标枚举 ====================


class MetricType(Enum):
    """监控指标类型"""

    CACHE_HIT_RATE = "cache_hit_rate"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CONNECTION_POOL = "connection_pool"
    QPS = "qps"


class RecordType(Enum):
    """记录类型"""

    GAUGE = "gauge"  # 仪表盘指标（如缓存命中率、响应时间）
    COUNTER = "counter"  # 计数器（如QPS、错误次数）
    EVENT = "event"  # 事件（如缓存失效、维护完成）
    HISTOGRAM = "histogram"  # 直方图（如响应时间分布）


class AlertLevel(Enum):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ==================== 监控数据结构 ====================


@dataclass
class MetricPoint:
    """监控指标数据点"""

    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class RecordPoint:
    """统一记录数据点"""

    name: str
    value: float
    record_type: RecordType
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """告警信息"""

    id: str
    level: AlertLevel
    message: str
    metric_type: MetricType
    current_value: float
    threshold: float
    timestamp: float
    resolved: bool = False


@dataclass
class HealthStatus:
    """健康状态"""

    overall_status: str  # healthy, warning, error
    cache_status: str
    performance_status: str
    error_status: str
    alerts: List[Alert]
    metrics: Dict[str, Any]


# ==================== 权限系统监控器 ====================


class PermissionMonitor:
    """权限系统监控器"""

    LOWER_IS_BETTER_METRICS = frozenset(
        [MetricType.RESPONSE_TIME, MetricType.ERROR_RATE, MetricType.MEMORY_USAGE]
    )

    def __init__(self, max_history_size: int = 1000):
        """
        初始化权限监控器

        Args:
            max_history_size: 历史记录最大大小
        """
        self.max_history_size = max_history_size
        self.metrics_history = []
        self.alerts = []

        # 使用后端存储系统
        self.backend: MonitorBackend = get_monitor_backend()

        # 获取指标聚合器
        self.metrics_aggregator = get_metrics_aggregator(
            redis_client=(
                self.backend.redis_client
                if hasattr(self.backend, "redis_client")
                else None
            )
        )

        if hasattr(self.backend, "redis_client") and self.backend.redis_client:
            self.subscriber = EventSubscriber(self.backend.redis_client)
            self.subscriber.subscribe(
                RESILIENCE_EVENTS_CHANNEL, self._handle_resilience_event
            )
            self.subscriber.start()

        # 告警相关（委托给后端管理）
        # 注意：告警状态现在由后端统一管理，解决多进程数据孤岛问题
        self.lock = threading.RLock()

        # 告警阈值配置
        self.thresholds = {
            MetricType.CACHE_HIT_RATE: {"warning": 0.8, "error": 0.6, "critical": 0.4},
            MetricType.RESPONSE_TIME: {"warning": 100, "error": 200, "critical": 500},
            MetricType.ERROR_RATE: {"warning": 0.05, "error": 0.1, "critical": 0.2},
            MetricType.MEMORY_USAGE: {"warning": 0.7, "error": 0.85, "critical": 0.95},
            MetricType.QPS: {"warning": 1000, "error": 500, "critical": 100},
        }

    def _handle_resilience_event(self, event: Dict[str, Any]):
        """处理从韧性模块接收到的事件。"""
        event_name = event.get("event_name")
        payload = event.get("payload", {})

        if event_name == "resilience.circuit_breaker.opened":
            # 收到熔断事件，记录一个带有特殊标签的指标
            self.record(
                name="degraded_requests",
                value=1,
                record_type=RecordType.COUNTER,
                tags={
                    "reason": "circuit_breaker",
                    "breaker_name": payload.get("breaker_name"),
                },
            )
        if event_name == "resilence.rate_limit.triggered":
            # 收到限流事件，记录一个带有特殊标签的指标
            self.record(
                name="rate_limited_requests",
                value=1,
                record_type=RecordType.COUNTER,
                tags={
                    "reason": "rate_limit",
                    "limiter_name": payload.get("limiter_name"),
                },
            )

        if event_name == "resilence.degradation.activated":
            # 收到降级事件，记录一个带有特殊标签的指标
            self.record(
                name="degraded_requests",
                value=1,
                record_type=RecordType.COUNTER,
                tags={
                    "reason": "degradation",
                    "degradation_name": payload.get("degradation_name"),
                },
            )

    def record(
        self,
        name: str,
        value: float = None,
        record_type: RecordType = RecordType.GAUGE,
        tags: Dict[str, str] = None,
        metadata: Dict[str, Any] = None,
        check_alerts: bool = False,
        metric_type: MetricType = None,
    ):
        """
        统一记录接口

        Args:
            name: 记录名称
            value: 记录值（对于事件类型可以为None）
            record_type: 记录类型
            tags: 标签信息
            metadata: 元数据（用于事件等）
            check_alerts: 是否检查告警
            metric_type: 对应的指标类型（用于告警检查）
        """
        with self.lock:
            timestamp = time.time()

            # 创建记录点
            record_point = RecordPoint(
                name=name,
                value=value or 0.0,
                record_type=record_type,
                timestamp=timestamp,
                tags=tags or {},
                metadata=metadata or {},
            )

            # 存储到后端
            if record_type == RecordType.EVENT:
                self.backend.record_event(name, metadata, tags, timestamp)
            else:
                self.backend.record_metric(name, value, tags, timestamp)

            # 检查告警
            if check_alerts and metric_type:
                self._check_alerts(metric_type, value)

            # 记录日志
            logger.debug(f"记录 {record_type.value}: {name} = {value}")

            # 暂存指标到聚合器（用于ML模块）
            if value is not None and record_type != RecordType.EVENT:
                stage_metric(name, value, tags)

    def record_cache_hit_rate(self, hit_rate: float, cache_level: str = "l1"):
        """记录缓存命中率"""
        self.record(
            name="cache_hit_rate",
            value=hit_rate,
            record_type=RecordType.GAUGE,
            tags={"cache_level": cache_level},
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )

    def record_response_time(
        self, response_time: float, operation: str = "permission_check"
    ):
        """记录响应时间"""
        self.record(
            name="response_time",
            value=response_time,
            record_type=RecordType.HISTOGRAM,
            tags={"operation": operation},
            check_alerts=True,
            metric_type=MetricType.RESPONSE_TIME,
        )

    def record_error_rate(
        self, error_rate: float, error_type: str = "permission_error"
    ):
        """记录错误率"""
        self.record(
            name="error_rate",
            value=error_rate,
            record_type=RecordType.GAUGE,
            tags={"error_type": error_type},
            check_alerts=True,
            metric_type=MetricType.ERROR_RATE,
        )

    def record_qps(self, qps: float, endpoint: str = "permissions"):
        """记录QPS指标"""
        self.record(
            name="qps",
            value=qps,
            record_type=RecordType.COUNTER,
            tags={"endpoint": endpoint},
            check_alerts=True,
            metric_type=MetricType.QPS,
        )

    def _check_alerts(self, metric_type: MetricType, value: float):
        """检查告警阈值"""
        if metric_type not in self.thresholds:
            return

        thresholds = self.thresholds[metric_type]

        for level_name, threshold in thresholds.items():
            # 直接使用level_name，因为AlertLevel枚举值是小写
            level = AlertLevel(level_name)

            # 检查是否超过阈值
            if self._is_threshold_exceeded(metric_type, value, threshold):
                self._create_alert(metric_type, value, threshold, level)

    def _is_threshold_exceeded(
        self, metric_type: MetricType, value: float, threshold: float
    ) -> bool:
        """检查是否超过阈值"""
        if metric_type in self.LOWER_IS_BETTER_METRICS:
            return value < threshold
        else:
            # 对于其他所有指标 (RESPONSE_TIME, ERROR_RATE, MEMORY_USAGE)，都是越高越糟
            return value > threshold

    def _create_alert(
        self, metric_type: MetricType, value: float, threshold: float, level: AlertLevel
    ):
        """创建告警"""
        alert_id = f"{metric_type.value}_{level.value}_{int(time.time())}"

        # 从后端检查是否已有相同告警
        existing_alerts = self.backend.get_active_alerts()
        existing_alert = next(
            (
                alert
                for alert in existing_alerts
                if alert.metric_type == metric_type
                and alert.level == level
                and not alert.resolved
            ),
            None,
        )

        if metric_type in self.LOWER_IS_BETTER_METRICS:
            comparison_op = "<"
            message_template = (
                "{metric_name} 指标过低: 当前值 {value:.2f} {op} 阈值 {threshold:.2f}"
            )
        else:
            comparison_op = ">"
            message_template = (
                "{metric_name} 指标过高: 当前值 {value:.2f} {op} 阈值 {threshold:.2f}"
            )

        dynamic_message = message_template.format(
            metric_name=metric_type.name,
            value=value,
            op=comparison_op,
            threshold=threshold,
        )

        # 创建告警对象
        alert = Alert(
            id=alert_id,
            level=level,
            message=dynamic_message,
            metric_type=metric_type,
            current_value=value,
            threshold=threshold,
            timestamp=time.time(),
        )

        # 委托给后端管理告警
        if self.backend.create_alert(alert):
            # 记录告警日志
            logger.warning(f"权限系统告警 [{level.name.upper()}]: {alert.message}")
        else:
            logger.error(f"创建告警失败: {alert.message}")

    def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        with self.lock:
            # 从后端获取最新数据
            cache_metrics = self.backend.get_metrics("cache_hit_rate", 10)
            response_metrics = self.backend.get_metrics("response_time", 10)
            error_metrics = self.backend.get_metrics("error_rate", 10)

            # 计算各指标状态
            cache_status = self._calculate_cache_status_from_backend(cache_metrics)
            performance_status = self._calculate_performance_status_from_backend(
                response_metrics
            )
            error_status = self._calculate_error_status_from_backend(error_metrics)

            # 确定整体状态
            overall_status = self._calculate_overall_status(
                cache_status, performance_status, error_status
            )

            # 从后端获取活跃告警
            active_alerts = self.backend.get_active_alerts()

            # 计算指标统计
            metrics_summary = self._calculate_metrics_summary_from_backend()

            return HealthStatus(
                overall_status=overall_status,
                cache_status=cache_status,
                performance_status=performance_status,
                error_status=error_status,
                alerts=active_alerts,
                metrics=metrics_summary,
            )

    def _calculate_cache_status_from_backend(
        self, cache_metrics: List[Dict[str, Any]]
    ) -> str:
        """从后端数据计算缓存状态"""
        if not cache_metrics:
            return "unknown"

        values = [point["value"] for point in cache_metrics]
        avg_hit_rate = statistics.mean(values)

        if avg_hit_rate >= 0.9:
            return "excellent"
        elif avg_hit_rate >= 0.8:
            return "good"
        elif avg_hit_rate >= 0.6:
            return "warning"
        else:
            return "error"

    def _calculate_performance_status_from_backend(
        self, response_metrics: List[Dict[str, Any]]
    ) -> str:
        """从后端数据计算性能状态"""
        if not response_metrics:
            return "unknown"

        values = [point["value"] for point in response_metrics]
        avg_response_time = statistics.mean(values)

        if avg_response_time <= 50:
            return "excellent"
        elif avg_response_time <= 100:
            return "good"
        elif avg_response_time <= 200:
            return "warning"
        else:
            return "error"

    def _calculate_error_status_from_backend(
        self, error_metrics: List[Dict[str, Any]]
    ) -> str:
        """从后端数据计算错误状态"""
        if not error_metrics:
            return "unknown"

        values = [point["value"] for point in error_metrics]
        avg_error_rate = statistics.mean(values)

        if avg_error_rate <= 0.01:
            return "excellent"
        elif avg_error_rate <= 0.05:
            return "good"
        elif avg_error_rate <= 0.1:
            return "warning"
        else:
            return "error"

    def _calculate_overall_status(
        self, cache_status: str, performance_status: str, error_status: str
    ) -> str:
        """计算整体状态"""
        status_priority = {
            "error": 3,
            "warning": 2,
            "good": 1,
            "excellent": 0,
            "unknown": 1,
        }

        max_priority = max(
            status_priority[cache_status],
            status_priority[performance_status],
            status_priority[error_status],
        )

        if max_priority == 3:
            return "error"
        elif max_priority == 2:
            return "warning"
        else:
            return "healthy"

    def _calculate_metrics_summary_from_backend(self) -> Dict[str, Any]:
        """从后端数据计算指标摘要"""
        summary = {}

        # 获取主要指标的统计信息
        for metric_name in ["cache_hit_rate", "response_time", "error_rate", "qps"]:
            stats = self.backend.get_stats(metric_name)
            if stats["count"] > 0:
                summary[metric_name] = {
                    "current": stats.get("latest", 0),
                    "average": stats["sum"] / stats["count"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "count": stats["count"],
                }

        return summary

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        with self.lock:
            health_status = self.get_health_status()

            return {
                "health_status": health_status.overall_status,
                "alerts_count": self.backend.get_alert_counters(),
                "active_alerts": len(self.backend.get_active_alerts()),
                "metrics_summary": health_status.metrics,
                "recent_alerts": [
                    {
                        "id": alert.id,
                        "level": alert.level.value,
                        "message": alert.message,
                        "timestamp": alert.timestamp,
                    }
                    for alert in self.backend.get_active_alerts()[-10:]  # 最近10个告警
                ],
            }

    def clear_alerts(self, level: Optional[AlertLevel] = None):
        """清除告警"""
        with self.lock:
            # 从后端获取活跃告警
            active_alerts = self.backend.get_active_alerts()

            if level:
                # 清除指定级别的告警
                for alert in active_alerts:
                    if alert.level == level:
                        self.backend.resolve_alert(alert.id)
            else:
                # 清除所有告警
                for alert in active_alerts:
                    self.backend.resolve_alert(alert.id)

    def get_events_summary(self) -> Dict[str, Any]:
        """
        获取事件摘要

        Returns:
            事件摘要信息
        """
        with self.lock:
            # 从后端获取事件数据
            all_events = []
            event_types = defaultdict(int)

            # 获取所有事件类型的记录
            for event_name in [
                "cache_invalidation",
                "maintenance_completed",
                "permission_change",
            ]:
                events = self.backend.get_events(event_name, 10)
                all_events.extend(events)
                if events:
                    event_types[event_name] = len(events)

            return {
                "total_events": sum(event_types.values()),
                "event_types": dict(event_types),
                "recent_events": all_events[-10:],
            }

    def get_values_summary(self) -> Dict[str, Any]:
        """
        获取数值摘要

        Returns:
            数值摘要信息
        """
        with self.lock:
            summary = {}

            # 从后端获取所有指标的统计信息
            for metric_name in ["cache_hit_rate", "response_time", "error_rate", "qps"]:
                stats = self.backend.get_stats(metric_name)
                if stats["count"] > 0:
                    summary[metric_name] = {
                        "count": stats["count"],
                        "sum": stats["sum"],
                        "min": stats["min"],
                        "max": stats["max"],
                        "avg": stats["sum"] / stats["count"],
                    }

            return summary

    def get_stats(self) -> Dict[str, Any]:
        """获取统一监控统计信息"""
        try:
            # 获取各个组件的统计信息
            health_status = self.get_health_status()
            performance_report = self.get_performance_report()
            events_summary = self.get_events_summary()
            values_summary = self.get_values_summary()

            # 组合统计信息
            stats = {
                "health_status": {
                    "overall_status": health_status.overall_status,
                    "cache_status": health_status.cache_status,
                    "performance_status": health_status.performance_status,
                    "error_status": health_status.error_status,
                    "alerts_count": (
                        len(health_status.alerts) if health_status.alerts else 0
                    ),
                },
                "performance": performance_report,
                "events": events_summary,
                "values": values_summary,
                "timestamp": time.time(),
            }

            return stats
        except Exception as e:
            logger.error(f"获取监控统计失败: {e}")
            return {
                "health_status": {
                    "overall_status": "error",
                    "cache_status": "error",
                    "performance_status": "error",
                    "error_status": "error",
                    "alerts_count": 0,
                },
                "performance": {},
                "events": {},
                "values": {},
                "timestamp": time.time(),
                "error": str(e),
            }


# ==================== 全局监控器实例 ====================

_permission_monitor = None


def get_permission_monitor() -> PermissionMonitor:
    """获取权限系统监控器实例"""
    global _permission_monitor
    if _permission_monitor is None:
        _permission_monitor = PermissionMonitor()
    return _permission_monitor


# ==================== 便捷函数 ====================


def record(
    name: str,
    value: float = None,
    record_type: RecordType = RecordType.GAUGE,
    tags: Dict[str, str] = None,
    metadata: Dict[str, Any] = None,
    check_alerts: bool = False,
    metric_type: MetricType = None,
):
    """
    统一记录接口

    Args:
        name: 记录名称
        value: 记录值（对于事件类型可以为None）
        record_type: 记录类型
        tags: 标签信息
        metadata: 元数据（用于事件等）
        check_alerts: 是否检查告警
        metric_type: 对应的指标类型（用于告警检查）
    """
    monitor = get_permission_monitor()
    monitor.record(name, value, record_type, tags, metadata, check_alerts, metric_type)


def record_cache_hit_rate(hit_rate: float, cache_level: str = "l1"):
    """记录缓存命中率"""
    monitor = get_permission_monitor()
    monitor.record_cache_hit_rate(hit_rate, cache_level)


def record_response_time(response_time: float, operation: str = "permission_check"):
    """记录响应时间"""
    monitor = get_permission_monitor()
    monitor.record_response_time(response_time, operation)


def record_error_rate(error_rate: float, error_type: str = "permission_error"):
    """记录错误率"""
    monitor = get_permission_monitor()
    monitor.record_error_rate(error_rate, error_type)


def record_qps(qps: float, endpoint: str = "permissions"):
    """记录QPS"""
    monitor = get_permission_monitor()
    monitor.record_qps(qps, endpoint)


def record_event(event_type: str, event_data: Dict[str, Any]):
    """记录事件"""
    monitor = get_permission_monitor()
    monitor.record_event(event_type, event_data)


def record_value(value_name: str, value: float, tags: Dict[str, str] = None):
    """记录数值指标"""
    monitor = get_permission_monitor()
    monitor.record_value(value_name, value, tags)


def get_health_status() -> HealthStatus:
    """获取健康状态"""
    monitor = get_permission_monitor()
    return monitor.get_health_status()


def get_performance_report() -> Dict[str, Any]:
    """获取性能报告"""
    monitor = get_permission_monitor()
    return monitor.get_performance_report()


def get_events_summary() -> Dict[str, Any]:
    """获取事件摘要"""
    monitor = get_permission_monitor()
    return monitor.get_events_summary()


def get_values_summary() -> Dict[str, Any]:
    """获取数值摘要"""
    monitor = get_permission_monitor()
    return monitor.get_values_summary()


def get_stats() -> Dict[str, Any]:
    """获取统一监控统计信息"""
    monitor = get_permission_monitor()
    return monitor.get_stats()


def clear_alerts(level: Optional[AlertLevel] = None):
    """清除告警"""
    monitor = get_permission_monitor()
    monitor.clear_alerts(level)


# ==================== 新的统一接口便捷函数 ====================


def record_gauge(
    name: str,
    value: float,
    tags: Dict[str, str] = None,
    check_alerts: bool = False,
    metric_type: MetricType = None,
):
    """记录仪表盘指标"""
    record(
        name,
        value,
        RecordType.GAUGE,
        tags,
        check_alerts=check_alerts,
        metric_type=metric_type,
    )


def record_counter(
    name: str,
    value: float,
    tags: Dict[str, str] = None,
    check_alerts: bool = False,
    metric_type: MetricType = None,
):
    """记录计数器指标"""
    record(
        name,
        value,
        RecordType.COUNTER,
        tags,
        check_alerts=check_alerts,
        metric_type=metric_type,
    )


def record_histogram(
    name: str,
    value: float,
    tags: Dict[str, str] = None,
    check_alerts: bool = False,
    metric_type: MetricType = None,
):
    """记录直方图指标"""
    record(
        name,
        value,
        RecordType.HISTOGRAM,
        tags,
        check_alerts=check_alerts,
        metric_type=metric_type,
    )


def record_event(
    name: str, metadata: Dict[str, Any] = None, tags: Dict[str, str] = None
):
    """记录事件"""
    record(name, 1.0, RecordType.EVENT, tags, metadata)
