"""
监控后端模块

支持多种监控数据存储方式：
- 内存存储（开发/测试环境）
- Redis存储（生产环境）
- Prometheus推送（生产环境）
- Prometheus暴露（生产环境）
"""

from collections import defaultdict
import time
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict
from enum import Enum
import redis
import socket
from contextlib import contextmanager

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # 创建模拟类以便在没有prometheus_client时也能运行
    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    class Summary:
        def __init__(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    REGISTRY = None

logger = logging.getLogger(__name__)

# ==================== 后端类型枚举 ====================


class BackendType(Enum):
    """监控后端类型"""

    MEMORY = "memory"  # 内存存储（开发环境）
    REDIS = "redis"  # Redis存储（生产环境）
    STATSD = "statsd"  # StatsD推送（生产环境）
    PROMETHEUS = "prometheus"  # Prometheus暴露（生产环境）


# ==================== 基础后端接口 ====================


class MonitorBackend(ABC):
    """监控后端基础接口"""

    @abstractmethod
    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录指标"""
        pass

    @abstractmethod
    def record_event(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录事件"""
        pass

    @abstractmethod
    def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        pass

    @abstractmethod
    def get_events(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        pass

    @abstractmethod
    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取统计信息"""
        pass

    @abstractmethod
    def create_alert(self, alert: "Any") -> bool:
        """创建告警"""
        pass

    @abstractmethod
    def get_active_alerts(self) -> List["Any"]:
        """获取活跃告警"""
        pass

    @abstractmethod
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        pass

    @abstractmethod
    def get_alert_counters(self) -> Dict[str, int]:
        """获取告警计数器"""
        pass


# ==================== 内存后端（开发环境） ====================


class MemoryBackend(MonitorBackend):
    """内存存储后端（仅用于开发/测试）"""

    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.events: Dict[str, List[Dict[str, Any]]] = {}
        self.stats: Dict[str, Dict[str, Any]] = {}
        self.alerts: List["Any"] = []
        self.alert_counters: Dict[str, int] = defaultdict(int)

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录指标到内存"""
        if name not in self.metrics:
            self.metrics[name] = []

        metric_point = {
            "name": name,
            "value": value,
            "tags": tags or {},
            "timestamp": timestamp or time.time(),
        }

        self.metrics[name].append(metric_point)

        # 限制历史记录数量
        if len(self.metrics[name]) > self.max_history_size:
            self.metrics[name] = self.metrics[name][-self.max_history_size :]

        # 更新统计信息
        self._update_stats(name, value)

        return True

    def record_event(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录事件到内存"""
        if name not in self.events:
            self.events[name] = []

        event_point = {
            "name": name,
            "metadata": metadata or {},
            "tags": tags or {},
            "timestamp": timestamp or time.time(),
        }

        self.events[name].append(event_point)

        # 限制历史记录数量
        if len(self.events[name]) > self.max_history_size:
            self.events[name] = self.events[name][-self.max_history_size :]

        return True

    def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        return self.metrics.get(name, [])[-limit:]

    def get_events(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        return self.events.get(name, [])[-limit:]

    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.get(
            name, {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        )

    def _update_stats(self, name: str, value: float):
        """更新统计信息"""
        if name not in self.stats:
            self.stats[name] = {
                "count": 0,
                "sum": 0,
                "min": float("inf"),
                "max": float("-inf"),
            }

        stats = self.stats[name]
        stats["count"] += 1
        stats["sum"] += value
        stats["min"] = min(stats["min"], value)
        stats["max"] = max(stats["max"], value)

    def create_alert(self, alert: "Any") -> bool:
        """创建告警"""
        try:
            # 检查是否已有相同告警
            existing_alert = next(
                (
                    a
                    for a in self.alerts
                    if a.metric_type == alert.metric_type
                    and a.level == alert.level
                    and not a.resolved
                ),
                None,
            )

            if existing_alert:
                # 更新现有告警
                existing_alert.current_value = alert.current_value
                existing_alert.timestamp = alert.timestamp
                existing_alert.message = alert.message
                # 不增加计数器，因为这是更新现有告警
            else:
                # 创建新告警
                self.alerts.append(alert)
                self.alert_counters[alert.level.value] += 1

            return True
        except Exception as e:
            logger.error(f"内存后端创建告警失败: {e}")
            return False

    def get_active_alerts(self) -> List["Any"]:
        """获取活跃告警"""
        return [alert for alert in self.alerts if not alert.resolved]

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        try:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.resolved = True
                    return True
            return False
        except Exception as e:
            logger.error(f"内存后端解决告警失败: {e}")
            return False

    def get_alert_counters(self) -> Dict[str, int]:
        """获取告警计数器"""
        return dict(self.alert_counters)


# ==================== Redis后端（生产环境） ====================


class RedisBackend(MonitorBackend):
    """Redis存储后端（生产环境）"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "monitor:",
        max_history_size: int = 1000,
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_history_size = max_history_size
        self._redis = None
        self._connection_healthy = False

    @property
    def redis(self):
        """延迟初始化Redis连接 - 支持集群感知"""
        if self._redis is None:
            try:
                # 尝试创建Redis集群客户端
                from flask import current_app

                redis_config = current_app.config.get("REDIS_CONFIG", {})
                startup_nodes = redis_config.get(
                    "startup_nodes", [{"host": "localhost", "port": 6379}]
                )
                additional_nodes = redis_config.get("additional_nodes", [])
                startup_nodes.extend(additional_nodes)
                # 修正：过滤并只保留 host/port 字段
                startup_nodes = [
                    {"host": n["host"], "port": n["port"]}
                    for n in startup_nodes
                    if isinstance(n, dict) and "host" in n and "port" in n
                ]
                try:
                    self._redis = redis.RedisCluster(
                        startup_nodes=startup_nodes,
                        decode_responses=True,
                        skip_full_coverage_check=True,  # 开发环境跳过完整覆盖检查
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                    )
                    # 测试连接
                    self._redis.ping()
                    self._connection_healthy = True
                    logger.info("监控后端使用Redis集群")
                except Exception as cluster_error:
                    logger.warning(
                        f"Redis集群连接失败，降级到单节点模式: {cluster_error}"
                    )
                    # 降级到单节点Redis
                    try:
                        self._redis = redis.from_url(self.redis_url)
                        self._redis.ping()  # 测试连接
                        self._connection_healthy = True
                        logger.info("监控后端使用Redis单节点")
                    except Exception as single_error:
                        logger.error(f"Redis单节点连接也失败: {single_error}")
                        self._redis = None
                        self._connection_healthy = False
            except Exception as e:
                logger.error(f"Redis连接初始化失败: {e}")
                # 如果Redis完全不可用，返回None，系统将降级到内存存储
                self._redis = None
                self._connection_healthy = False
        return self._redis

    def _check_connection_health(self) -> bool:
        """检查Redis连接健康状态"""
        if self._redis is None:
            return False

        try:
            self._redis.ping()
            self._connection_healthy = True
            return True
        except Exception as e:
            logger.warning(f"Redis连接健康检查失败: {e}")
            self._connection_healthy = False
            return False

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录指标到Redis"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，跳过指标记录")
            return False

        try:
            metric_point = {
                "name": name,
                "value": value,
                "tags": tags or {},
                "timestamp": timestamp or time.time(),
            }

            # 使用Redis List存储历史数据
            key = f"{self.key_prefix}metrics:{name}"
            self.redis.lpush(key, json.dumps(metric_point))
            self.redis.ltrim(key, 0, self.max_history_size - 1)

            # 更新最新值
            latest_key = f"{self.key_prefix}latest:{name}"
            self.redis.set(latest_key, json.dumps(metric_point))

            # 更新统计信息
            self._update_stats(name, value)

            return True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，记录指标失败: {e}")
            self._connection_healthy = False
            return False
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，记录指标失败: {e}")
            return False
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，记录指标失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis记录指标出现意外错误: {e}")
            return False

    def record_event(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录事件到Redis"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，跳过事件记录")
            return False

        try:
            event_point = {
                "name": name,
                "metadata": metadata or {},
                "tags": tags or {},
                "timestamp": timestamp or time.time(),
            }

            # 使用Redis List存储事件历史
            key = f"{self.key_prefix}events:{name}"
            self.redis.lpush(key, json.dumps(event_point))
            self.redis.ltrim(key, 0, self.max_history_size - 1)

            return True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，记录事件失败: {e}")
            self._connection_healthy = False
            return False
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，记录事件失败: {e}")
            return False
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，记录事件失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis记录事件出现意外错误: {e}")
            return False

    def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，返回空指标列表")
            return []

        try:
            key = f"{self.key_prefix}metrics:{name}"
            data = self.redis.lrange(key, 0, limit - 1)
            return [json.loads(item) for item in data]
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，获取指标失败: {e}")
            self._connection_healthy = False
            return []
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，获取指标失败: {e}")
            return []
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，获取指标失败: {e}")
            return []
        except Exception as e:
            logger.error(f"Redis获取指标出现意外错误: {e}")
            return []

    def get_events(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，返回空事件列表")
            return []

        try:
            key = f"{self.key_prefix}events:{name}"
            data = self.redis.lrange(key, 0, limit - 1)
            return [json.loads(item) for item in data]
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，获取事件失败: {e}")
            self._connection_healthy = False
            return []
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，获取事件失败: {e}")
            return []
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，获取事件失败: {e}")
            return []
        except Exception as e:
            logger.error(f"Redis获取事件出现意外错误: {e}")
            return []

    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，返回空统计信息")
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}

        try:
            key = f"{self.key_prefix}stats:{name}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，获取统计失败: {e}")
            self._connection_healthy = False
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，获取统计失败: {e}")
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，获取统计失败: {e}")
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        except Exception as e:
            logger.error(f"Redis获取统计出现意外错误: {e}")
            return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}

    def _update_stats(self, name: str, value: float):
        """更新统计信息"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，跳过统计更新")
            return

        try:
            stats = self.get_stats(name)
            stats["count"] += 1
            stats["sum"] += value
            stats["min"] = min(stats["min"], value)
            stats["max"] = max(stats["max"], value)

            key = f"{self.key_prefix}stats:{name}"
            self.redis.set(key, json.dumps(stats))
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，更新统计失败: {e}")
            self._connection_healthy = False
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，更新统计失败: {e}")
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，更新统计失败: {e}")
        except Exception as e:
            logger.error(f"Redis更新统计出现意外错误: {e}")

    def create_alert(self, alert: "Any") -> bool:
        """创建告警到Redis"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，跳过告警创建")
            return False

        try:
            # 序列化告警对象
            alert_data = {
                "id": alert.id,
                "level": alert.level.value,
                "message": alert.message,
                "metric_type": alert.metric_type.value,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp,
                "resolved": alert.resolved,
            }

            # 存储告警
            alert_key = f"{self.key_prefix}alert:{alert.id}"
            self.redis.set(alert_key, json.dumps(alert_data))

            # 添加到活跃告警集合
            active_alerts_key = f"{self.key_prefix}active_alerts"
            self.redis.sadd(active_alerts_key, alert.id)

            # 更新告警计数器
            counter_key = f"{self.key_prefix}alert_counter:{alert.level.value}"
            self.redis.incr(counter_key)

            return True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，创建告警失败: {e}")
            self._connection_healthy = False
            return False
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，创建告警失败: {e}")
            return False
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，创建告警失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis创建告警出现意外错误: {e}")
            return False

    def get_active_alerts(self) -> List["Any"]:
        """从Redis获取活跃告警"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，返回空告警列表")
            return []

        try:
            from .permission_monitor import Alert, AlertLevel, MetricType

            active_alerts = []
            active_alerts_key = f"{self.key_prefix}active_alerts"
            alert_ids = self.redis.smembers(active_alerts_key)

            for alert_id in alert_ids:
                alert_key = f"{self.key_prefix}alert:{alert_id.decode()}"
                alert_data = self.redis.get(alert_key)
                if alert_data:
                    data = json.loads(alert_data)
                    if not data.get("resolved", False):
                        alert = Alert(
                            id=data["id"],
                            level=AlertLevel(data["level"]),
                            message=data["message"],
                            metric_type=MetricType(data["metric_type"]),
                            current_value=data["current_value"],
                            threshold=data["threshold"],
                            timestamp=data["timestamp"],
                            resolved=data["resolved"],
                        )
                        active_alerts.append(alert)

            return active_alerts
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，获取活跃告警失败: {e}")
            self._connection_healthy = False
            return []
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，获取活跃告警失败: {e}")
            return []
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，获取活跃告警失败: {e}")
            return []
        except Exception as e:
            logger.error(f"Redis获取活跃告警出现意外错误: {e}")
            return []

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，跳过告警解决")
            return False

        try:
            alert_key = f"{self.key_prefix}alert:{alert_id}"
            alert_data = self.redis.get(alert_key)

            if alert_data:
                data = json.loads(alert_data)
                data["resolved"] = True
                self.redis.set(alert_key, json.dumps(data))

                # 从活跃告警集合中移除
                active_alerts_key = f"{self.key_prefix}active_alerts"
                self.redis.srem(active_alerts_key, alert_id)

                return True
            return False
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，解决告警失败: {e}")
            self._connection_healthy = False
            return False
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，解决告警失败: {e}")
            return False
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，解决告警失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis解决告警出现意外错误: {e}")
            return False

    def get_alert_counters(self) -> Dict[str, int]:
        """获取告警计数器"""
        if not self._check_connection_health():
            logger.warning("Redis连接不可用，返回空告警计数器")
            return {}

        try:
            counters = {}
            for level in ["info", "warning", "error", "critical"]:
                counter_key = f"{self.key_prefix}alert_counter:{level}"
                count = self.redis.get(counter_key)
                counters[level] = int(count) if count else 0
            return counters
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，获取告警计数器失败: {e}")
            self._connection_healthy = False
            return {}
        except redis.AuthenticationError as e:
            logger.error(f"Redis认证失败，获取告警计数器失败: {e}")
            return {}
        except redis.RedisError as e:
            logger.error(f"Redis操作错误，获取告警计数器失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"Redis获取告警计数器出现意外错误: {e}")
            return {}


# ==================== StatsD后端（生产环境） ====================


class StatsDBackend(MonitorBackend):
    """StatsD推送后端（生产环境）"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "permission_system.",
    ):
        self.host = host
        self.port = port
        self.prefix = prefix
        self._socket = None

    @property
    def socket(self):
        """延迟初始化UDP socket"""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """推送指标到StatsD"""
        try:
            # 构建StatsD消息
            metric_name = f"{self.prefix}{name}"
            message = f"{metric_name}:{value}|g"

            # 添加标签（如果StatsD支持）
            if tags:
                tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
                message += f"|#{tag_str}"

            # 发送UDP消息
            self.socket.sendto(message.encode(), (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"StatsD推送指标失败: {e}")
            return False

    def record_event(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """推送事件到StatsD"""
        try:
            # StatsD通常不支持复杂事件，我们记录为计数器
            event_name = f"{self.prefix}event.{name}"
            message = f"{event_name}:1|c"

            if tags:
                tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
                message += f"|#{tag_str}"

            self.socket.sendto(message.encode(), (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"StatsD推送事件失败: {e}")
            return False

    def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """StatsD不支持查询，返回空列表"""
        return []

    def get_events(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """StatsD不支持查询，返回空列表"""
        return []

    def get_stats(self, name: str) -> Dict[str, Any]:
        """StatsD不支持查询，返回空统计"""
        return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}

    def create_alert(self, alert: "Any") -> bool:
        """StatsD不支持告警管理，记录为事件"""
        try:
            # 将告警记录为StatsD事件
            event_name = f"alert.{alert.level.value}"
            message = f"{self.prefix}{event_name}:1|c"
            self.socket.sendto(message.encode(), (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"StatsD创建告警失败: {e}")
            return False

    def get_active_alerts(self) -> List["Any"]:
        """StatsD不支持查询，返回空列表"""
        return []

    def resolve_alert(self, alert_id: str) -> bool:
        """StatsD不支持告警管理"""
        return False

    def get_alert_counters(self) -> Dict[str, int]:
        """StatsD不支持查询，返回空计数器"""
        return {}


# ==================== Prometheus后端（生产环境） ====================


class PrometheusBackend(MonitorBackend):
    """Prometheus后端（生产环境）"""

    def __init__(self, prefix: str = "permission_system_", registry=None):
        self.prefix = prefix
        self._metrics = {}
        self._registry = registry  # 允许传入自定义注册表
        self._initialize_metrics()

    def _initialize_metrics(self):
        """初始化Prometheus指标"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client未安装，使用模拟指标")
            return

        # 使用自定义注册表或默认注册表
        registry = self._registry if self._registry is not None else REGISTRY

        # 缓存命中率指标
        self._metrics["cache_hit_rate"] = Gauge(
            f"{self.prefix}cache_hit_rate",
            "Cache hit rate percentage",
            ["cache_level"],
            registry=registry,
        )

        # 响应时间指标
        self._metrics["response_time"] = Histogram(
            f"{self.prefix}response_time_seconds",
            "Response time in seconds",
            ["operation"],
            registry=registry,
        )

        # 错误率指标
        self._metrics["error_rate"] = Gauge(
            f"{self.prefix}error_rate",
            "Error rate percentage",
            ["error_type"],
            registry=registry,
        )

        # QPS指标
        self._metrics["qps"] = Counter(
            f"{self.prefix}requests_total",
            "Total requests",
            ["endpoint"],
            registry=registry,
        )

        # 内存使用指标
        self._metrics["memory_usage"] = Gauge(
            f"{self.prefix}memory_usage_bytes",
            "Memory usage in bytes",
            registry=registry,
        )

        # 连接池指标
        self._metrics["connection_pool"] = Gauge(
            f"{self.prefix}connection_pool_size",
            "Connection pool size",
            ["pool_type"],
            registry=registry,
        )

        # 告警指标
        self._metrics["alerts"] = Counter(
            f"{self.prefix}alerts_total",
            "Total alerts",
            ["level", "metric_type"],
            registry=registry,
        )

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录指标到Prometheus"""
        try:
            if not PROMETHEUS_AVAILABLE:
                return True

            metric_name = f"{self.prefix}{name}"

            if name == "cache_hit_rate":
                cache_level = tags.get("cache_level", "l1") if tags else "l1"
                self._metrics["cache_hit_rate"].labels(cache_level=cache_level).set(
                    value
                )

            elif name == "response_time":
                operation = (
                    tags.get("operation", "permission_check")
                    if tags
                    else "permission_check"
                )
                self._metrics["response_time"].labels(operation=operation).observe(
                    value / 1000.0
                )  # 转换为秒

            elif name == "error_rate":
                error_type = (
                    tags.get("error_type", "permission_error")
                    if tags
                    else "permission_error"
                )
                self._metrics["error_rate"].labels(error_type=error_type).set(value)

            elif name == "qps":
                endpoint = (
                    tags.get("endpoint", "permissions") if tags else "permissions"
                )
                self._metrics["qps"].labels(endpoint=endpoint).inc(value)

            elif name == "memory_usage":
                self._metrics["memory_usage"].set(value)

            elif name == "connection_pool":
                pool_type = tags.get("pool_type", "default") if tags else "default"
                self._metrics["connection_pool"].labels(pool_type=pool_type).set(value)

            return True
        except Exception as e:
            logger.error(f"Prometheus记录指标失败: {e}")
            return False

    def record_event(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        timestamp: float = None,
    ) -> bool:
        """记录事件到Prometheus"""
        try:
            if not PROMETHEUS_AVAILABLE:
                return True

            # 将事件记录为Counter指标
            event_counter = Counter(
                f"{self.prefix}events_total", "Total events", ["event_type"]
            )
            event_counter.labels(event_type=name).inc()

            return True
        except Exception as e:
            logger.error(f"Prometheus记录事件失败: {e}")
            return False

    def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Prometheus不支持查询历史数据，返回空列表"""
        return []

    def get_events(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Prometheus不支持查询历史数据，返回空列表"""
        return []

    def get_stats(self, name: str) -> Dict[str, Any]:
        """Prometheus不支持查询统计，返回空统计"""
        return {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}

    def create_alert(self, alert: "Any") -> bool:
        """记录告警到Prometheus"""
        try:
            if not PROMETHEUS_AVAILABLE:
                return True

            # 记录告警计数
            self._metrics["alerts"].labels(
                level=alert.level.value, metric_type=alert.metric_type.value
            ).inc()

            return True
        except Exception as e:
            logger.error(f"Prometheus记录告警失败: {e}")
            return False

    def get_active_alerts(self) -> List["Any"]:
        """Prometheus不支持查询告警，返回空列表"""
        return []

    def resolve_alert(self, alert_id: str) -> bool:
        """Prometheus不支持告警管理"""
        return False

    def get_alert_counters(self) -> Dict[str, int]:
        """Prometheus不支持查询告警计数器，返回空计数器"""
        return {}

    def get_metrics_endpoint(self) -> str:
        """获取Prometheus指标端点"""
        if PROMETHEUS_AVAILABLE:
            # 使用自定义注册表或默认注册表
            registry = self._registry if self._registry is not None else REGISTRY
            # generate_latest返回bytes，需要解码为str
            return generate_latest(registry).decode("utf-8")
        else:
            return "# prometheus_client not available\n"


# ==================== 后端工厂 ====================


class MonitorBackendFactory:
    """监控后端工厂"""

    @staticmethod
    def create_backend(backend_type: BackendType, **kwargs) -> MonitorBackend:
        """创建监控后端"""
        if backend_type == BackendType.MEMORY:
            return MemoryBackend(**kwargs)
        elif backend_type == BackendType.REDIS:
            return RedisBackend(**kwargs)
        elif backend_type == BackendType.STATSD:
            return StatsDBackend(**kwargs)
        elif backend_type == BackendType.PROMETHEUS:
            return PrometheusBackend(**kwargs)
        else:
            raise ValueError(f"不支持的后端类型: {backend_type}")


# ==================== 全局后端实例 ====================

_backend = None


def get_monitor_backend() -> MonitorBackend:
    """获取监控后端实例"""
    global _backend
    if _backend is None:
        # 根据环境变量选择后端
        import os

        backend_type = os.getenv("MONITOR_BACKEND", "memory")

        if backend_type == "redis":
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            _backend = MonitorBackendFactory.create_backend(
                BackendType.REDIS, redis_url=redis_url
            )
        elif backend_type == "statsd":
            statsd_host = os.getenv("STATSD_HOST", "localhost")
            statsd_port = int(os.getenv("STATSD_PORT", "8125"))
            _backend = MonitorBackendFactory.create_backend(
                BackendType.STATSD, host=statsd_host, port=statsd_port
            )
        elif backend_type == "prometheus":
            prometheus_prefix = os.getenv("PROMETHEUS_PREFIX", "permission_system_")
            _backend = MonitorBackendFactory.create_backend(
                BackendType.PROMETHEUS, prefix=prometheus_prefix
            )
        else:
            # 默认使用内存后端
            _backend = MonitorBackendFactory.create_backend(BackendType.MEMORY)

    return _backend
