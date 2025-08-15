"""
指标聚合器模块

解决异步数据聚合问题：
- 收集一分钟内的所有指标
- 验证数据完整性
- 提供高质量的PerformanceMetrics快照
"""

import time
import json
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""

    CACHE_HIT_RATE = "cache_hit_rate"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    QPS = "qps"
    CONNECTION_POOL = "connection_pool"


@dataclass
class PerformanceMetrics:
    """性能指标快照"""

    timestamp: float
    cache_hit_rate: float
    response_time: float
    error_rate: float
    memory_usage: float
    qps: float
    connection_pool_usage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "cache_hit_rate": self.cache_hit_rate,
            "response_time": self.response_time,
            "error_rate": self.error_rate,
            "memory_usage": self.memory_usage,
            "qps": self.qps,
            "connection_pool_usage": self.connection_pool_usage,
        }


class MetricsAggregator:
    """指标聚合器"""

    def __init__(self, redis_client, ml_monitor=None):
        """
        初始化指标聚合器

        Args:
            redis_client: Redis客户端
            ml_monitor: ML性能监控器
        """
        self.redis_client = redis_client
        self.ml_monitor = ml_monitor
        self.aggregation_interval = 60  # 聚合间隔（秒）
        self.staging_ttl = 120  # 暂存数据TTL（秒）
        self.required_metrics = {
            MetricType.CACHE_HIT_RATE.value,
            MetricType.RESPONSE_TIME.value,
            MetricType.ERROR_RATE.value,
            MetricType.MEMORY_USAGE.value,
            MetricType.QPS.value,
        }

        # 启动聚合线程
        self.stop_event = threading.Event()
        self.aggregation_thread = threading.Thread(
            target=self._aggregation_loop, daemon=True, name="MetricsAggregator"
        )
        self.aggregation_thread.start()

        logger.info("指标聚合器已启动")

    def stage_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """
        暂存单个指标

        Args:
            metric_name: 指标名称
            value: 指标值
            tags: 标签信息
        """
        try:
            if not self.redis_client:
                logger.warning("Redis客户端不可用，跳过指标暂存")
                return

            # 计算当前分钟的时间戳
            current_minute = (
                int(time.time() // self.aggregation_interval)
                * self.aggregation_interval
            )
            staging_key = f"monitor:metrics_snapshot:{current_minute}"

            # 构建指标数据
            metric_data = {"value": value, "timestamp": time.time(), "tags": tags or {}}

            # 使用HSET暂存指标
            self.redis_client.hset(staging_key, metric_name, json.dumps(metric_data))
            self.redis_client.expire(staging_key, self.staging_ttl)

            logger.debug(f"指标已暂存: {metric_name} = {value} -> {staging_key}")

        except Exception as e:
            logger.error(f"暂存指标失败: {metric_name} = {value}, error: {e}")

    def _aggregation_loop(self):
        """聚合循环"""
        logger.info("指标聚合循环已启动")

        while not self.stop_event.is_set():
            try:
                # 等待聚合间隔
                time.sleep(5)  # 每5秒检查一次

                # 计算前一分钟的时间戳
                current_time = time.time()
                previous_minute = (
                    int(
                        (current_time - self.aggregation_interval)
                        // self.aggregation_interval
                    )
                    * self.aggregation_interval
                )
                staging_key = f"monitor:metrics_snapshot:{previous_minute}"

                # 获取前一分钟的完整指标快照
                snapshot = self._get_metrics_snapshot(staging_key)

                if snapshot:
                    # 验证快照完整性
                    if self._validate_snapshot_completeness(snapshot):
                        # 创建高质量的PerformanceMetrics对象
                        metrics = self._create_performance_metrics(snapshot)

                        # 喂给ML模块
                        if self.ml_monitor:
                            self.ml_monitor.feed_metrics(metrics)
                            logger.info(f"高质量指标已喂给ML模块: {metrics.timestamp}")

                        # 清理暂存数据
                        self._cleanup_staging_data(staging_key)
                    else:
                        logger.warning(f"指标快照不完整，丢弃: {staging_key}")
                        self._cleanup_staging_data(staging_key)

            except Exception as e:
                logger.error(f"指标聚合循环错误: {e}")

    def _get_metrics_snapshot(self, staging_key: str) -> Optional[Dict[str, Any]]:
        """
        获取指标快照

        Args:
            staging_key: 暂存键名

        Returns:
            指标快照字典，如果不存在则返回None
        """
        try:
            if not self.redis_client:
                return None

            # 获取所有暂存的指标
            snapshot_data = self.redis_client.hgetall(staging_key)

            if not snapshot_data:
                return None

            # 解析指标数据
            snapshot = {}
            for metric_name, metric_json in snapshot_data.items():
                try:
                    metric_data = json.loads(metric_json)
                    snapshot[metric_name] = metric_data["value"]
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"解析指标数据失败: {metric_name}, error: {e}")
                    continue

            return snapshot

        except Exception as e:
            logger.error(f"获取指标快照失败: {staging_key}, error: {e}")
            return None

    def _validate_snapshot_completeness(self, snapshot: Dict[str, Any]) -> bool:
        """
        验证快照完整性

        Args:
            snapshot: 指标快照

        Returns:
            是否完整
        """
        # 检查是否包含所有必需的指标
        missing_metrics = self.required_metrics - set(snapshot.keys())

        if missing_metrics:
            logger.warning(f"指标快照缺少必需指标: {missing_metrics}")
            return False

        # 检查指标值的有效性
        for metric_name, value in snapshot.items():
            if not isinstance(value, (int, float)):
                logger.warning(f"指标值类型无效: {metric_name} = {value}")
                return False

            if value < 0:
                logger.warning(f"指标值为负数: {metric_name} = {value}")
                return False

        logger.debug(f"指标快照验证通过，包含 {len(snapshot)} 个指标")
        return True

    def _create_performance_metrics(
        self, snapshot: Dict[str, Any]
    ) -> PerformanceMetrics:
        """
        创建PerformanceMetrics对象

        Args:
            snapshot: 指标快照

        Returns:
            PerformanceMetrics对象
        """
        return PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=snapshot.get(MetricType.CACHE_HIT_RATE.value, 0.0),
            response_time=snapshot.get(MetricType.RESPONSE_TIME.value, 0.0),
            error_rate=snapshot.get(MetricType.ERROR_RATE.value, 0.0),
            memory_usage=snapshot.get(MetricType.MEMORY_USAGE.value, 0.0),
            qps=snapshot.get(MetricType.QPS.value, 0.0),
            connection_pool_usage=snapshot.get(MetricType.CONNECTION_POOL.value, 0.0),
        )

    def _cleanup_staging_data(self, staging_key: str):
        """
        清理暂存数据

        Args:
            staging_key: 暂存键名
        """
        try:
            if self.redis_client:
                self.redis_client.delete(staging_key)
                logger.debug(f"暂存数据已清理: {staging_key}")
        except Exception as e:
            logger.error(f"清理暂存数据失败: {staging_key}, error: {e}")

    def stop(self):
        """停止聚合器"""
        self.stop_event.set()
        if self.aggregation_thread.is_alive():
            self.aggregation_thread.join(timeout=5)
        logger.info("指标聚合器已停止")


# 全局聚合器实例
_metrics_aggregator = None


def get_metrics_aggregator(redis_client=None, ml_monitor=None) -> MetricsAggregator:
    """
    获取指标聚合器实例

    Args:
        redis_client: Redis客户端
        ml_monitor: ML性能监控器

    Returns:
        MetricsAggregator实例
    """
    global _metrics_aggregator

    if _metrics_aggregator is None:
        _metrics_aggregator = MetricsAggregator(redis_client, ml_monitor)

    return _metrics_aggregator


def stage_metric(metric_name: str, value: float, tags: Dict[str, str] = None):
    """
    暂存指标的便捷函数

    Args:
        metric_name: 指标名称
        value: 指标值
        tags: 标签信息
    """
    aggregator = get_metrics_aggregator()
    aggregator.stage_metric(metric_name, value, tags)
