"""
监控系统配置模块

支持通过环境变量配置监控后端和连接参数
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class MonitorBackendType(Enum):
    """监控后端类型"""

    MEMORY = "memory"
    REDIS = "redis"
    STATSD = "statsd"
    PROMETHEUS = "prometheus"


class MonitorConfig:
    """监控系统配置"""

    def __init__(self):
        self.backend_type = self._get_backend_type()
        self.redis_config = self._get_redis_config()
        self.statsd_config = self._get_statsd_config()
        self.prometheus_config = self._get_prometheus_config()
        self.memory_config = self._get_memory_config()

    def _get_backend_type(self) -> MonitorBackendType:
        """获取后端类型"""
        backend_str = os.getenv("MONITOR_BACKEND", "memory").lower()
        try:
            return MonitorBackendType(backend_str)
        except ValueError:
            logger.warning(f"无效的后端类型: {backend_str}, 使用默认值: memory")
            return MonitorBackendType.MEMORY

    def _get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return {
            "url": os.getenv("REDIS_URL", "redis://localhost:6379"),
            "key_prefix": os.getenv("MONITOR_REDIS_PREFIX", "monitor:"),
            "max_history_size": int(os.getenv("MONITOR_MAX_HISTORY", "1000")),
        }

    def _get_statsd_config(self) -> Dict[str, Any]:
        """获取StatsD配置"""
        return {
            "host": os.getenv("STATSD_HOST", "localhost"),
            "port": int(os.getenv("STATSD_PORT", "8125")),
            "prefix": os.getenv("MONITOR_STATSD_PREFIX", "permission_system."),
        }

    def _get_prometheus_config(self) -> Dict[str, Any]:
        """获取Prometheus配置"""
        return {
            "prefix": os.getenv("PROMETHEUS_PREFIX", "permission_system_"),
            "metrics_path": os.getenv("PROMETHEUS_METRICS_PATH", "/metrics"),
        }

    def _get_memory_config(self) -> Dict[str, Any]:
        """获取内存配置"""
        return {"max_history_size": int(os.getenv("MONITOR_MAX_HISTORY", "1000"))}

    def get_backend_config(self) -> Dict[str, Any]:
        """获取当前后端的配置"""
        if self.backend_type == MonitorBackendType.REDIS:
            return self.redis_config
        elif self.backend_type == MonitorBackendType.STATSD:
            return self.statsd_config
        elif self.backend_type == MonitorBackendType.PROMETHEUS:
            return self.prometheus_config
        else:
            return self.memory_config

    def is_redis_enabled(self) -> bool:
        """检查是否启用Redis"""
        return self.backend_type == MonitorBackendType.REDIS

    def is_statsd_enabled(self) -> bool:
        """检查是否启用StatsD"""
        return self.backend_type == MonitorBackendType.STATSD

    def is_prometheus_enabled(self) -> bool:
        """检查是否启用Prometheus"""
        return self.backend_type == MonitorBackendType.PROMETHEUS

    def is_memory_enabled(self) -> bool:
        """检查是否启用内存存储"""
        return self.backend_type == MonitorBackendType.MEMORY


# 全局配置实例
_monitor_config = None


def get_monitor_config() -> MonitorConfig:
    """获取监控配置实例"""
    global _monitor_config
    if _monitor_config is None:
        _monitor_config = MonitorConfig()
    return _monitor_config
