"""
权限系统韧性模块

提供熔断器、限流器、降级等韧性策略的集中配置与控制
支持动态配置，无需重启即可生效
"""

import time
import json
import logging
import threading
from typing import Callable, Dict, Any, Optional, List, Union, TYPE_CHECKING
from functools import wraps
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
from .permission_events import RESILIENCE_EVENTS_CHANNEL, EventPublisher
from app.core.common.distributed_lock import OptimizedDistributedLock

# 导入Redis客户端
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

# ==================== 应用工厂模式支持 ====================


class Resilience:
    """一个封装了韧性控制器的扩展类，用于支持 init_app 模式"""

    def __init__(self, app=None):
        self.controller = None
        self.redis_client = None  # 添加redis_client实例变量
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        使用 Flask app 对象来初始化韧性控制器。
        这会从 app.config 读取配置并创建 Redis 连接。
        """
        # 防止重复初始化
        if self.controller:
            return

        redis_client = None
        if REDIS_AVAILABLE:
            try:
                # 优先从 Flask 扩展中获取 Redis 客户端，这是最佳实践
                # 假设你使用了 Flask-Redis 或类似的扩展
                if "redis" in app.extensions:
                    redis_client = app.extensions["redis"]
                    logger.info("从 Flask 扩展中获取 Redis 客户端")
                # 否则，从 app.config 读取配置来创建
                else:
                    redis_host = app.config.get("REDIS_HOST", "localhost")
                    redis_port = app.config.get("REDIS_PORT", 6379)

                    # 【修正】修复 'dict' object has no attribute 'name' 错误
                    # 在这里处理集群和单节点逻辑
                    try:
                        # 尝试Redis集群连接
                        startup_nodes = app.config.get(
                            "REDIS_CLUSTER_NODES",
                            [{"host": "127.0.0.1", "port": redis_port}],
                        )

                        # 确保节点配置格式正确
                        valid_startup_nodes = []
                        for node in startup_nodes:
                            if (
                                isinstance(node, dict)
                                and "host" in node
                                and "port" in node
                            ):
                                valid_startup_nodes.append(
                                    {"host": node["host"], "port": node["port"]}
                                )

                        if valid_startup_nodes:
                            try:
                                redis_client = redis.RedisCluster(
                                    startup_nodes=valid_startup_nodes,
                                    decode_responses=True,
                                    skip_full_coverage_check=True,
                                )
                                redis_client.ping()
                                logger.info("使用Redis集群作为配置源")
                            except Exception as cluster_error:
                                logger.warning(
                                    f"Redis集群连接失败，降级到单节点模式: {str(cluster_error)}"
                                )
                                # 降级到单节点模式
                                redis_config = app.config.get(
                                    "REDIS_SINGLE_NODE_CONFIG",
                                    {
                                        "host": "127.0.0.1",
                                        "port": redis_port,
                                        "db": 0,
                                        "decode_responses": True,
                                    },
                                )
                                redis_client = redis.Redis(**redis_config)
                                redis_client.ping()
                                logger.info("使用Redis单节点作为配置源")
                        else:
                            # 如果没有有效的集群节点，直接使用单节点
                            redis_config = app.config.get(
                                "REDIS_SINGLE_NODE_CONFIG",
                                {
                                    "host": "127.0.0.1",
                                    "port": redis_port,
                                    "db": 0,
                                    "decode_responses": True,
                                },
                            )
                            redis_client = redis.Redis(**redis_config)
                            redis_client.ping()
                            logger.info("使用Redis单节点作为配置源")
                    except Exception as redis_error:
                        logger.warning(f"Redis连接失败: {str(redis_error)}")
                        # 如果连接失败，创建None客户端，应用仍可启动
                        redis_client = None

            except Exception as e:
                logger.error(f"初始化 Redis 客户端失败: {e}", exc_info=True)
                redis_client = None

        # 保存Redis客户端到实例变量
        self.redis_client = redis_client

        # 【新增】将Redis客户端存储到app.extensions中，供其他扩展使用
        app.extensions["redis_client"] = redis_client

        # 创建控制器实例并将其存储起来
        self.controller = ResilienceController(redis_client)

        # 将自身实例存入 app 扩展中，方便全局访问
        app.extensions["resilience"] = self


# ==================== 全局控制器实例 ====================
# 【核心修改】创建一个未初始化的全局实例
resilience = Resilience()

# ==================== 韧性策略枚举 ====================


class CircuitBreakerState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


class RateLimitType(Enum):
    """限流类型"""

    TOKEN_BUCKET = "token_bucket"  # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"  # 漏桶
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    FIXED_WINDOW = "fixed_window"  # 固定窗口


class DegradationLevel(Enum):
    """降级级别"""

    NONE = "none"  # 无降级
    LIGHT = "light"  # 轻度降级
    MEDIUM = "medium"  # 中度降级
    HEAVY = "heavy"  # 重度降级


# ==================== 多维限流数据结构 ====================


@dataclass
class MultiDimensionalKey:
    """多维限流键"""

    user_id: Optional[str] = None
    server_id: Optional[str] = None
    ip_address: Optional[str] = None

    def __hash__(self):
        return hash((self.user_id, self.server_id, self.ip_address))

    def __eq__(self, other):
        if not isinstance(other, MultiDimensionalKey):
            return False
        return (
            self.user_id == other.user_id
            and self.server_id == other.server_id
            and self.ip_address == other.ip_address
        )

    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        result = {}
        if self.user_id:
            result["user_id"] = self.user_id
        if self.server_id:
            result["server_id"] = self.server_id
        if self.ip_address:
            result["ip_address"] = self.ip_address
        return result


# ==================== 配置数据结构 ====================


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    name: str
    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 60.0  # 恢复超时（秒）
    expected_exception: str = "Exception"  # 预期异常类型
    monitor_interval: float = 10.0  # 监控间隔（秒）
    state: CircuitBreakerState = CircuitBreakerState.CLOSED


@dataclass
class RateLimitConfig:
    """限流器配置"""

    name: str
    limit_type: RateLimitType = RateLimitType.TOKEN_BUCKET
    max_requests: int = 100  # 最大请求数
    time_window: float = 60.0  # 时间窗口（秒）
    burst_size: int = 10  # 突发大小
    tokens_per_second: float = 10.0  # 每秒令牌数
    enabled: bool = True

    # 多维限流配置
    multi_dimensional: bool = False  # 是否启用多维限流
    user_id_limit: int = 50  # 用户ID维度限制
    server_id_limit: int = 200  # 服务器ID维度限制
    ip_limit: int = 100  # IP地址维度限制
    combined_limit: int = 300  # 组合维度限制


@dataclass
class DegradationConfig:
    """降级配置"""

    name: str
    level: DegradationLevel = DegradationLevel.NONE
    fallback_function: str = ""  # 降级函数名
    timeout: float = 5.0  # 超时时间（秒）
    enabled: bool = False


# ==================== 集中配置控制器 ====================


class ResilienceController:
    """韧性控制器 - 集中管理所有韧性策略的配置和状态"""

    # 配置键前缀
    CIRCUIT_BREAKER_KEY = "resilience:{circuit_breaker}"
    RATE_LIMIT_KEY = "resilience:{rate_limit}"
    DEGRADATION_KEY = "resilience:{degradation}"
    BULKHEAD_KEY = "resilience:{bulkhead}"
    GLOBAL_SWITCH_KEY = "resilience:{global_switch}"

    # 配置覆盖层键
    CONFIG_OVERRIDES_KEY = "resilience:{config_overrides}"

    def __init__(self, config_source: Optional[redis.Redis] = None):
        """
        初始化韧性控制器

        Args:
            config_source: Redis客户端，用于配置存储
        """
        self.config_source = config_source
        self.cache_ttl = 300  # 5分钟缓存
        self.lua_scripts = {}
        self.config_overrides = {}
        self.local_cache = {}

        # 缓存相关属性
        self.cache_lock = threading.Lock()
        self.last_cache_update = time.time()

        # 配置热更新相关
        self.event_publisher = None
        if config_source:
            self.event_publisher = EventPublisher(config_source)

        # 延迟启动配置热更新订阅者，避免初始化时的递归
        # self._start_config_hot_reload_subscriber()

        # 注册Lua脚本
        self._register_lua_scripts()

        logger.info("韧性控制器已初始化")

    def _register_lua_scripts(self):
        """注册所有Lua脚本"""
        if self.config_source and REDIS_AVAILABLE:
            try:
                # CircuitBreaker Lua脚本
                self.circuit_breaker_execute_script = (
                    self.config_source.register_script(
                        CircuitBreaker.EXECUTE_OR_RECORD_FAILURE_SCRIPT
                    )
                )

                # RateLimiter Lua脚本
                self.token_bucket_script = self.config_source.register_script(
                    RateLimiter.TOKEN_BUCKET_ATOMIC_SCRIPT
                )
                self.sliding_window_script = self.config_source.register_script(
                    RateLimiter.SLIDING_WINDOW_ATOMIC_SCRIPT
                )
                self.fixed_window_script = self.config_source.register_script(
                    RateLimiter.FIXED_WINDOW_ATOMIC_SCRIPT
                )

                # Bulkhead Lua脚本
                self.bulkhead_script = self.config_source.register_script(
                    Bulkhead.BULKHEAD_ATOMIC_SCRIPT
                )

                logger.info("所有Lua脚本注册成功")
            except Exception as e:
                logger.error(f"注册Lua脚本失败: {e}")

    # ==================== CircuitBreaker 原子操作 ====================

    def circuit_breaker_execute_atomic_operation(
        self,
        name: str,
        operation: str,
        failure_threshold: int,
        recovery_timeout: float,
        current_time: float,
    ) -> tuple:
        """执行熔断器原子操作"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                result = self.circuit_breaker_execute_script(
                    keys=[name],
                    args=[operation, failure_threshold, recovery_timeout, current_time],
                )
                return result
            else:
                logger.warning("Redis不可用，使用内存存储")
                return (1, b"closed", b"no_event")
        except Exception as e:
            logger.error(f"熔断器原子操作失败: {e}")
            return (1, b"closed", b"no_event")

    def get_circuit_breaker_state(self, name: str) -> CircuitBreakerState:
        """获取熔断器状态"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                state_key = f"circuit_breaker:{{{name}}}:state"
                state_value = self.config_source.get(state_key)
                if state_value:
                    return CircuitBreakerState(state_value.decode("utf-8"))
        except Exception as e:
            logger.error(f"获取熔断器状态失败: {e}")
        return CircuitBreakerState.CLOSED

    def get_circuit_breaker_failure_count(self, name: str) -> int:
        """获取熔断器失败计数"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                failure_count_key = f"circuit_breaker:{{{name}}}:failure_count"
                value = self.config_source.get(failure_count_key)
                return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取失败计数失败: {e}")
        return 0

    def get_circuit_breaker_last_failure_time(self, name: str) -> float:
        """获取熔断器最后失败时间"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                last_failure_time_key = f"circuit_breaker:{{{name}}}:last_failure_time"
                value = self.config_source.get(last_failure_time_key)
                return float(value) if value else 0.0
        except Exception as e:
            logger.error(f"获取最后失败时间失败: {e}")
        return 0.0

    def get_circuit_breaker_half_open_calls(self, name: str) -> int:
        """获取熔断器半开调用次数"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                half_open_calls_key = f"circuit_breaker:{{{name}}}:half_open_calls"
                value = self.config_source.get(half_open_calls_key)
                return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取半开调用次数失败: {e}")
        return 0

    # ==================== RateLimiter 原子操作 ====================

    def rate_limiter_token_bucket_check(
        self,
        name: str,
        key: str,
        max_requests: int,
        tokens_per_second: float,
        current_time: float,
    ) -> bool:
        """令牌桶限流检查"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                result = self.token_bucket_script(
                    keys=[name],
                    args=[key, max_requests, tokens_per_second, current_time],
                )
                return bool(result[0])
            else:
                logger.warning("Redis不可用，使用内存存储")
                return True
        except Exception as e:
            logger.error(f"令牌桶检查失败: {e}")
            return False

    def rate_limiter_sliding_window_check(
        self,
        name: str,
        key: str,
        max_requests: int,
        time_window: float,
        current_time: float,
    ) -> bool:
        """滑动窗口限流检查"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                result = self.sliding_window_script(
                    keys=[name], args=[key, max_requests, time_window, current_time]
                )
                return bool(result[0])
            else:
                logger.warning("Redis不可用，使用内存存储")
                return True
        except Exception as e:
            logger.error(f"滑动窗口检查失败: {e}")
            return False

    def rate_limiter_fixed_window_check(
        self,
        name: str,
        key: str,
        max_requests: int,
        time_window: float,
        current_time: float,
    ) -> bool:
        """固定窗口限流检查 - 使用Lua脚本保证原子性"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                result = self.fixed_window_script(
                    keys=[name], args=[key, max_requests, time_window, current_time]
                )
                return bool(result[0])
            else:
                # 降级到内存存储（仅用于测试）
                logger.warning("Redis不可用，使用内存存储")
                return True
        except Exception as e:
            logger.error(f"固定窗口检查失败: {e}")
            return False

    # ==================== Bulkhead 原子操作 ====================

    def bulkhead_execute_atomic_operation(
        self, name: str, operation: str, max_concurrent_calls: int, current_time: float
    ) -> tuple:
        """执行舱壁隔离器原子操作"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                result = self.bulkhead_script(
                    keys=[name], args=[operation, max_concurrent_calls, current_time]
                )
                return result
            else:
                logger.warning("Redis不可用，使用内存存储")
                return (1, 0)
        except Exception as e:
            logger.error(f"舱壁隔离器原子操作失败: {e}")
            return (0, 0)

    def get_bulkhead_active_calls(self, name: str) -> int:
        """获取舱壁隔离器活跃调用数"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                active_calls_key = f"bulkhead:{{{name}}}:active_calls"
                value = self.config_source.get(active_calls_key)
                return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取活跃调用数失败: {e}")
        return 0

    def get_bulkhead_total_calls(self, name: str) -> int:
        """获取舱壁隔离器总调用数"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                total_calls_key = f"bulkhead:{{{name}}}:total_calls"
                value = self.config_source.get(total_calls_key)
                return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取总调用数失败: {e}")
        return 0

    def get_bulkhead_failed_calls(self, name: str) -> int:
        """获取舱壁隔离器失败调用数"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                failed_calls_key = f"bulkhead:{{{name}}}:failed_calls"
                value = self.config_source.get(failed_calls_key)
                return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取失败调用数失败: {e}")
        return 0

    def get_bulkhead_last_call_time(self, name: str) -> float:
        """获取舱壁隔离器最后调用时间"""
        try:
            if self.config_source and REDIS_AVAILABLE:
                last_call_time_key = f"bulkhead:{{{name}}}:last_call_time"
                value = self.config_source.get(last_call_time_key)
                return float(value) if value else 0.0
        except Exception as e:
            logger.error(f"获取最后调用时间失败: {e}")
        return 0.0

    def _get_from_cache_or_source(self, key: str, default: Any = None) -> Any:
        """从缓存或数据源获取配置"""
        current_time = time.time()

        with self.cache_lock:
            # 检查缓存是否已过期
            if current_time - self.last_cache_update > self.cache_ttl:
                logger.debug(f"缓存已过期，清空缓存")
                self.local_cache.clear()
                self.last_cache_update = current_time

            # 从缓存获取
            if key in self.local_cache:
                return self.local_cache[key]

            # 从数据源获取
            if self.config_source and REDIS_AVAILABLE:
                try:
                    value = self.config_source.hgetall(key)
                    if value:
                        # 将字节字符串转换为字符串
                        decoded_value = {}
                        for k, v in value.items():
                            if isinstance(k, bytes):
                                k = k.decode("utf-8")
                            if isinstance(v, bytes):
                                v = v.decode("utf-8")
                            decoded_value[k] = v

                        # 更新缓存和更新时间
                        self.local_cache[key] = decoded_value
                        self.last_cache_update = current_time
                        logger.debug(f"从Redis获取并缓存配置: {key}")
                        return decoded_value
                    else:
                        # Redis中没有数据，不缓存空值
                        logger.debug(f"Redis中没有找到key: {key}")
                        return default
                except Exception as e:
                    logger.error(f"从Redis获取配置失败: {e}")

            # 返回默认值
            return default

    def _set_to_source(self, key: str, field: str, value: str) -> bool:
        """设置配置到数据源"""
        current_time = time.time()

        if self.config_source and REDIS_AVAILABLE:
            lock_key = f"lock:resilience:source:{key}:{field}"
            lock = OptimizedDistributedLock(self.config_source, lock_key, timeout=2.0)
            with lock:
                try:
                    self.config_source.hset(key, field, value)
                    with self.cache_lock:
                        if key not in self.local_cache:
                            self.local_cache[key] = {}
                        self.local_cache[key][field] = value
                        self.last_cache_update = current_time
                    logger.debug(f"设置Redis配置并更新缓存: {key}.{field}")
                    return True
                except Exception as e:
                    logger.error(f"设置Redis配置失败: {e}")
                    return False
        else:
            with self.cache_lock:
                if key not in self.local_cache:
                    self.local_cache[key] = {}
                self.local_cache[key][field] = value
                self.last_cache_update = current_time
            return True

    def get_circuit_breaker_config(self, name: str) -> Optional[CircuitBreakerConfig]:
        """获取熔断器配置"""
        # 首先检查是否存在有效的配置覆盖
        override_config = self._check_config_override("circuit_breaker", name)

        if override_config:
            # 使用覆盖配置
            try:
                return CircuitBreakerConfig(
                    name=name,
                    failure_threshold=override_config.get("failure_threshold", 5),
                    recovery_timeout=override_config.get("recovery_timeout", 60.0),
                    expected_exception=override_config.get(
                        "expected_exception", "Exception"
                    ),
                    monitor_interval=override_config.get("monitor_interval", 10.0),
                    state=CircuitBreakerState(override_config.get("state", "closed")),
                )
            except Exception as e:
                logger.error(f"解析熔断器覆盖配置失败: {e}")

        # 从主配置源获取配置
        config_data = self._get_from_cache_or_source(self.CIRCUIT_BREAKER_KEY, {})

        if name in config_data:
            try:
                data = json.loads(config_data[name])
                return CircuitBreakerConfig(
                    name=name,
                    failure_threshold=data.get("failure_threshold", 5),
                    recovery_timeout=data.get("recovery_timeout", 60.0),
                    expected_exception=data.get("expected_exception", "Exception"),
                    monitor_interval=data.get("monitor_interval", 10.0),
                    state=CircuitBreakerState(data.get("state", "closed")),
                )
            except Exception as e:
                logger.error(f"解析熔断器配置失败: {e}")

        # 返回默认配置
        return CircuitBreakerConfig(name=name)

    def set_circuit_breaker_config(
        self, name: str, config: CircuitBreakerConfig, use_override: bool = True
    ) -> bool:
        """
        设置熔断器配置

        Args:
            name: 配置名称
            config: 熔断器配置
            use_override: 是否使用覆盖层（运维人员手动配置时使用）
        """
        try:
            # 安全地访问配置属性，支持字典和对象两种格式
            if isinstance(config, dict):
                config_data = {
                    "name": config.get("name", name),
                    "failure_threshold": config.get("failure_threshold", 5),
                    "recovery_timeout": config.get("recovery_timeout", 60.0),
                    "expected_exception": config.get("expected_exception", "Exception"),
                    "monitor_interval": config.get("monitor_interval", 10.0),
                    "state": config.get("state", "closed"),
                }
            else:
                # 配置对象格式
                try:
                    config_data = {
                        "name": config.name,
                        "failure_threshold": config.failure_threshold,
                        "recovery_timeout": config.recovery_timeout,
                        "expected_exception": config.expected_exception,
                        "monitor_interval": config.monitor_interval,
                        "state": config.state.value,
                    }
                except AttributeError as e:
                    # 如果无法访问对象属性，使用默认值
                    logger.warning(f"无法访问配置对象属性，使用默认值: {e}")
                    config_data = {
                        "name": name,
                        "failure_threshold": 5,
                        "recovery_timeout": 60.0,
                        "expected_exception": "Exception",
                        "monitor_interval": 10.0,
                        "state": "closed",
                    }

            if use_override:
                # 运维人员手动配置，使用覆盖层
                success = self._set_config_override(
                    "circuit_breaker", name, config_data
                )
                if success:
                    logger.info(f"熔断器配置覆盖已设置: {name}")
                return success
            else:
                # ML模块自动配置，直接修改主配置
                success = self._set_to_source(
                    self.CIRCUIT_BREAKER_KEY, name, json.dumps(config_data)
                )

                if success:
                    # 发布配置更新消息
                    self._publish_config_update("circuit_breaker", name)
                    logger.info(f"熔断器配置已更新: {name}")

                return success

        except Exception as e:
            logger.error(f"设置熔断器配置失败: {name}, error: {e}")
            return False

    def get_rate_limit_config(self, name: str) -> Optional[RateLimitConfig]:
        """获取限流器配置"""
        # 首先检查是否存在有效的配置覆盖
        override_config = self._check_config_override("rate_limiter", name)

        if override_config:
            # 使用覆盖配置
            try:
                return RateLimitConfig(
                    name=name,
                    limit_type=RateLimitType(
                        override_config.get("limit_type", "token_bucket")
                    ),
                    max_requests=override_config.get("max_requests", 100),
                    time_window=override_config.get("time_window", 60.0),
                    burst_size=override_config.get("burst_size", 10),
                    tokens_per_second=override_config.get("tokens_per_second", 10.0),
                    enabled=override_config.get("enabled", True),
                    multi_dimensional=override_config.get("multi_dimensional", False),
                    user_id_limit=override_config.get("user_id_limit", 50),
                    server_id_limit=override_config.get("server_id_limit", 200),
                    ip_limit=override_config.get("ip_limit", 100),
                    combined_limit=override_config.get("combined_limit", 300),
                )
            except Exception as e:
                logger.error(f"解析限流器覆盖配置失败: {e}")

        # 从主配置源获取配置
        config_data = self._get_from_cache_or_source(self.RATE_LIMIT_KEY, {})

        if name in config_data:
            try:
                data = json.loads(config_data[name])
                return RateLimitConfig(
                    name=name,
                    limit_type=RateLimitType(data.get("limit_type", "token_bucket")),
                    max_requests=data.get("max_requests", 100),
                    time_window=data.get("time_window", 60.0),
                    burst_size=data.get("burst_size", 10),
                    tokens_per_second=data.get("tokens_per_second", 10.0),
                    enabled=data.get("enabled", True),
                    multi_dimensional=data.get("multi_dimensional", False),
                    user_id_limit=data.get("user_id_limit", 50),
                    server_id_limit=data.get("server_id_limit", 200),
                    ip_limit=data.get("ip_limit", 100),
                    combined_limit=data.get("combined_limit", 300),
                )
            except Exception as e:
                logger.error(f"解析限流器配置失败: {e}")

        # 返回默认配置
        return RateLimitConfig(name=name)

    def set_rate_limit_config(
        self, name: str, config: RateLimitConfig, use_override: bool = True
    ) -> bool:
        """
        设置限流器配置

        Args:
            name: 配置名称
            config: 限流器配置
            use_override: 是否使用覆盖层（运维人员手动配置时使用）
        """
        try:
            if not self._validate_rate_limit_config(config):
                logger.error(f"限流器配置验证失败: {name}")
                return False

            # 安全地访问配置属性，支持字典和对象两种格式
            if isinstance(config, dict):
                config_data = {
                    "name": config.get("name", name),
                    "limit_type": config.get("limit_type", "token_bucket"),
                    "max_requests": config.get("max_requests", 100),
                    "time_window": config.get("time_window", 60.0),
                    "burst_size": config.get("burst_size", 10),
                    "tokens_per_second": config.get("tokens_per_second", 10.0),
                    "enabled": config.get("enabled", True),
                    "multi_dimensional": config.get("multi_dimensional", False),
                    "user_id_limit": config.get("user_id_limit", 50),
                    "server_id_limit": config.get("server_id_limit", 200),
                    "ip_limit": config.get("ip_limit", 100),
                    "combined_limit": config.get("combined_limit", 300),
                }
            else:
                # 配置对象格式
                try:
                    config_data = {
                        "name": config.name,
                        "limit_type": config.limit_type.value,
                        "max_requests": config.max_requests,
                        "time_window": config.time_window,
                        "burst_size": config.burst_size,
                        "tokens_per_second": config.tokens_per_second,
                        "enabled": config.enabled,
                        "multi_dimensional": config.multi_dimensional,
                        "user_id_limit": config.user_id_limit,
                        "server_id_limit": config.server_id_limit,
                        "ip_limit": config.ip_limit,
                        "combined_limit": config.combined_limit,
                    }
                except AttributeError as e:
                    # 如果无法访问对象属性，使用默认值
                    logger.warning(f"无法访问限流器配置对象属性，使用默认值: {e}")
                    config_data = {
                        "name": name,
                        "limit_type": "token_bucket",
                        "max_requests": 100,
                        "time_window": 60.0,
                        "burst_size": 10,
                        "tokens_per_second": 10.0,
                        "enabled": True,
                        "multi_dimensional": False,
                        "user_id_limit": 50,
                        "server_id_limit": 200,
                        "ip_limit": 100,
                        "combined_limit": 300,
                    }

            if use_override:
                # 运维人员手动配置，使用覆盖层
                success = self._set_config_override("rate_limiter", name, config_data)
                if success:
                    logger.info(f"限流器配置覆盖已设置: {name}")
                return success
            else:
                # ML模块自动配置，直接修改主配置
                success = self._set_to_source(
                    self.RATE_LIMIT_KEY, name, json.dumps(config_data)
                )

                if success:
                    # 发布配置更新消息
                    self._publish_config_update("rate_limiter", name)
                    logger.info(f"限流器配置已更新: {name}")

                return success

        except Exception as e:
            logger.error(f"设置限流器配置失败: {name}, error: {e}")
            return False

    def _validate_rate_limit_config(self, config: RateLimitConfig) -> bool:
        """验证限流器配置的有效性"""
        # 基本参数验证
        if config.max_requests <= 0:
            logger.error("max_requests 必须大于0")
            return False

        if config.time_window <= 0:
            logger.error("time_window 必须大于0")
            return False

        if config.burst_size < 0:
            logger.error("burst_size 不能为负数")
            return False

        if config.tokens_per_second < 0:
            logger.error("tokens_per_second 不能为负数")
            return False

        # 多维限流配置验证
        if config.multi_dimensional:
            if config.user_id_limit < 0:
                logger.error("user_id_limit 不能为负数")
                return False

            if config.server_id_limit < 0:
                logger.error("server_id_limit 不能为负数")
                return False

            if config.ip_limit < 0:
                logger.error("ip_limit 不能为负数")
                return False

            if config.combined_limit < 0:
                logger.error("combined_limit 不能为负数")
                return False

            # 至少有一个维度限制大于0
            if (
                config.user_id_limit == 0
                and config.server_id_limit == 0
                and config.ip_limit == 0
                and config.combined_limit == 0
            ):
                logger.error("多维限流至少需要启用一个维度的限制")
                return False

        return True

    def get_degradation_config(self, name: str) -> Optional[DegradationConfig]:
        """获取降级配置"""
        # 首先检查是否存在有效的配置覆盖
        override_config = self._check_config_override("degradation", name)

        if override_config:
            # 使用覆盖配置
            try:
                return DegradationConfig(
                    name=name,
                    level=DegradationLevel(override_config.get("level", "none")),
                    fallback_function=override_config.get("fallback_function", ""),
                    timeout=override_config.get("timeout", 5.0),
                    enabled=override_config.get("enabled", False),
                )
            except Exception as e:
                logger.error(f"解析降级覆盖配置失败: {e}")

        # 从主配置源获取配置
        config_data = self._get_from_cache_or_source(self.DEGRADATION_KEY, {})

        if name in config_data:
            try:
                data = json.loads(config_data[name])
                return DegradationConfig(
                    name=name,
                    level=DegradationLevel(data.get("level", "none")),
                    fallback_function=data.get("fallback_function", ""),
                    timeout=data.get("timeout", 5.0),
                    enabled=data.get("enabled", False),
                )
            except Exception as e:
                logger.error(f"解析降级配置失败: {e}")

        # 返回默认配置
        return DegradationConfig(name=name)

    def set_degradation_config(
        self, name: str, config: DegradationConfig, use_override: bool = True
    ) -> bool:
        """
        设置降级配置

        Args:
            name: 配置名称
            config: 降级配置
            use_override: 是否使用覆盖层（运维人员手动配置时使用）
        """
        try:
            # 安全地访问配置属性，支持字典和对象两种格式
            if isinstance(config, dict):
                config_data = {
                    "name": config.get("name", name),
                    "level": config.get("level", "none"),
                    "fallback_function": config.get("fallback_function", ""),
                    "timeout": config.get("timeout", 5.0),
                    "enabled": config.get("enabled", False),
                }
            else:
                # 配置对象格式
                try:
                    config_data = {
                        "name": config.name,
                        "level": config.level.value,
                        "fallback_function": config.fallback_function,
                        "timeout": config.timeout,
                        "enabled": config.enabled,
                    }
                except AttributeError as e:
                    # 如果无法访问对象属性，使用默认值
                    logger.warning(f"无法访问降级配置对象属性，使用默认值: {e}")
                    config_data = {
                        "name": name,
                        "level": "none",
                        "fallback_function": "",
                        "timeout": 5.0,
                        "enabled": False,
                    }

            if use_override:
                # 运维人员手动配置，使用覆盖层
                success = self._set_config_override("degradation", name, config_data)
                if success:
                    logger.info(f"降级配置覆盖已设置: {name}")
                return success
            else:
                # ML模块自动配置，直接修改主配置
                success = self._set_to_source(
                    self.DEGRADATION_KEY, name, json.dumps(config_data)
                )

                if success:
                    # 发布配置更新消息
                    self._publish_config_update("degradation", name)
                    logger.info(f"降级配置已更新: {name}")

                return success

        except Exception as e:
            logger.error(f"设置降级配置失败: {name}, error: {e}")
            return False

    def is_global_switch_enabled(self, switch_name: str) -> bool:
        """检查全局开关状态"""
        config_data = self._get_from_cache_or_source(self.GLOBAL_SWITCH_KEY, {})
        return config_data.get(switch_name, "false").lower() == "true"

    def set_global_switch(self, switch_name: str, enabled: bool) -> bool:
        """设置全局开关"""
        try:
            success = self._set_to_source(
                self.GLOBAL_SWITCH_KEY, switch_name, str(enabled)
            )

            if success:
                # 发布配置更新消息
                self._publish_config_update("global_switch", switch_name)
                logger.info(f"全局开关已更新: {switch_name} = {enabled}")

            return success

        except Exception as e:
            logger.error(f"设置全局开关失败: {switch_name}, error: {e}")
            return False

    def get_bulkhead_config(self, name: str) -> Optional["BulkheadConfig"]:
        """获取舱壁隔离配置"""
        # 首先检查是否存在有效的配置覆盖
        override_config = self._check_config_override("bulkhead", name)

        if override_config:
            # 使用覆盖配置
            try:
                return BulkheadConfig(
                    name=name,
                    strategy=IsolationStrategy(override_config.get("strategy", "user")),
                    max_concurrent_calls=override_config.get(
                        "max_concurrent_calls", 10
                    ),
                    max_wait_time=override_config.get("max_wait_time", 5.0),
                    timeout=override_config.get("timeout", 30.0),
                    enabled=override_config.get("enabled", True),
                    monitor_interval=override_config.get("monitor_interval", 10.0),
                    alert_threshold=override_config.get("alert_threshold", 0.8),
                )
            except Exception as e:
                logger.error(f"解析舱壁隔离覆盖配置失败: {e}")

        # 从主配置源获取配置
        config_data = self._get_from_cache_or_source(self.BULKHEAD_KEY, {})

        if name in config_data:
            try:
                data = json.loads(config_data[name])
                return BulkheadConfig(
                    name=name,
                    strategy=IsolationStrategy(data.get("strategy", "user")),
                    max_concurrent_calls=data.get("max_concurrent_calls", 10),
                    max_wait_time=data.get("max_wait_time", 5.0),
                    timeout=data.get("timeout", 30.0),
                    enabled=data.get("enabled", True),
                    monitor_interval=data.get("monitor_interval", 10.0),
                    alert_threshold=data.get("alert_threshold", 0.8),
                )
            except Exception as e:
                logger.error(f"解析舱壁隔离配置失败: {e}")

        # 返回默认配置
        return BulkheadConfig(name=name)

    def set_bulkhead_config(
        self, name: str, config: "BulkheadConfig", use_override: bool = True
    ) -> bool:
        """
        设置舱壁隔离配置

        Args:
            name: 配置名称
            config: 舱壁隔离配置
            use_override: 是否使用覆盖层（运维人员手动配置时使用）
        """
        try:
            # 安全地访问配置属性，支持字典和对象两种格式
            if isinstance(config, dict):
                config_data = {
                    "name": config.get("name", name),
                    "strategy": config.get("strategy", "user"),
                    "max_concurrent_calls": config.get("max_concurrent_calls", 10),
                    "max_wait_time": config.get("max_wait_time", 5.0),
                    "timeout": config.get("timeout", 30.0),
                    "enabled": config.get("enabled", True),
                    "monitor_interval": config.get("monitor_interval", 10.0),
                    "alert_threshold": config.get("alert_threshold", 0.8),
                }
            else:
                # 配置对象格式
                try:
                    config_data = {
                        "name": config.name,
                        "strategy": config.strategy.value,
                        "max_concurrent_calls": config.max_concurrent_calls,
                        "max_wait_time": config.max_wait_time,
                        "timeout": config.timeout,
                        "enabled": config.enabled,
                        "monitor_interval": config.monitor_interval,
                        "alert_threshold": config.alert_threshold,
                    }
                except AttributeError as e:
                    # 如果无法访问对象属性，使用默认值
                    logger.warning(f"无法访问舱壁隔离配置对象属性，使用默认值: {e}")
                    config_data = {
                        "name": name,
                        "strategy": "user",
                        "max_concurrent_calls": 10,
                        "max_wait_time": 5.0,
                        "timeout": 30.0,
                        "enabled": True,
                        "monitor_interval": 10.0,
                        "alert_threshold": 0.8,
                    }

            if use_override:
                # 运维人员手动配置，使用覆盖层
                success = self._set_config_override("bulkhead", name, config_data)
                if success:
                    logger.info(f"舱壁隔离配置覆盖已设置: {name}")
                return success
            else:
                # ML模块自动配置，直接修改主配置
                success = self._set_to_source(
                    self.BULKHEAD_KEY, name, json.dumps(config_data)
                )

                if success:
                    # 发布配置更新消息
                    self._publish_config_update("bulkhead", name)
                    logger.info(f"舱壁隔离配置已更新: {name}")

                return success

        except Exception as e:
            logger.error(f"设置舱壁隔离配置失败: {name}, error: {e}")
            return False

    def get_all_configs(self) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            "circuit_breakers": self._get_from_cache_or_source(
                self.CIRCUIT_BREAKER_KEY, {}
            ),
            "rate_limits": self._get_from_cache_or_source(self.RATE_LIMIT_KEY, {}),
            "degradations": self._get_from_cache_or_source(self.DEGRADATION_KEY, {}),
            "bulkheads": self._get_from_cache_or_source(self.BULKHEAD_KEY, {}),
            "global_switches": self._get_from_cache_or_source(
                self.GLOBAL_SWITCH_KEY, {}
            ),
        }

    def clear_cache(self):
        """清除本地缓存"""
        with self.cache_lock:
            self.local_cache.clear()
        self.last_cache_update = 0
        logger.info("韧性控制器缓存已清除")

    def set_cache_ttl(self, ttl_seconds: float):
        """设置缓存TTL（秒）"""
        with self.cache_lock:
            self.cache_ttl = ttl_seconds
        logger.info(f"缓存TTL已设置为 {ttl_seconds} 秒")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        with self.cache_lock:
            return {
                "cache_size": len(self.local_cache),
                "cache_ttl": self.cache_ttl,
                "cached_keys": list(self.local_cache.keys()),
                "last_cache_update": self.last_cache_update,
            }

    def refresh_cache_for_key(self, key: str) -> bool:
        """强制刷新特定key的缓存"""
        try:
            with self.cache_lock:
                # 从缓存中移除该key
                if key in self.local_cache:
                    del self.local_cache[key]
                    logger.debug(f"已从缓存中移除key: {key}")

                # 强制从数据源重新获取
                if self.config_source and REDIS_AVAILABLE:
                    value = self.config_source.hgetall(key)
                    if value:
                        # 将字节字符串转换为字符串
                        decoded_value = {}
                        for k, v in value.items():
                            if isinstance(k, bytes):
                                k = k.decode("utf-8")
                            if isinstance(v, bytes):
                                v = v.decode("utf-8")
                            decoded_value[k] = v

                        # 更新缓存
                        self.local_cache[key] = decoded_value
                        logger.debug(f"已刷新缓存key: {key}")
                        return True
                return False
        except Exception as e:
            logger.error(f"刷新缓存失败: {e}")
            return False

    def invalidate_cache(self):
        """使缓存失效 - 下次获取时会重新从数据源加载"""
        with self.cache_lock:
            self.local_cache.clear()
            self.last_cache_update = 0
            logger.info("缓存已失效")

    def _start_config_hot_reload_subscriber(self):
        """启动配置热更新订阅者"""
        if not self.config_source or not REDIS_AVAILABLE:
            return

        def config_subscriber():
            """配置订阅者线程"""
            try:
                pubsub = self.config_source.pubsub()
                pubsub.subscribe("resilience:config_updated")

                logger.info("配置热更新订阅者已启动")

                for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            # 解析配置更新消息
                            config_data = json.loads(message["data"])
                            config_type = config_data.get("type")
                            config_name = config_data.get("name")

                            logger.info(
                                f"收到配置更新通知: {config_type} - {config_name}"
                            )

                            # 立即清除本地缓存
                            self.invalidate_cache()

                            # 发布缓存失效事件
                            if self.event_publisher:
                                self.event_publisher.publish(
                                    channel="resilience:cache_invalidated",
                                    event_name="cache_invalidated",
                                    payload={
                                        "config_type": config_type,
                                        "config_name": config_name,
                                        "timestamp": time.time(),
                                    },
                                    source_module="resilience_controller",
                                )

                        except Exception as e:
                            logger.error(f"处理配置更新消息失败: {e}")

            except Exception as e:
                logger.error(f"配置订阅者错误: {e}")

        # 启动订阅者线程
        subscriber_thread = threading.Thread(target=config_subscriber, daemon=True)
        subscriber_thread.start()
        logger.info("配置热更新订阅者线程已启动")

    def _publish_config_update(self, config_type: str, config_name: str):
        """发布配置更新消息"""
        if not self.config_source or not REDIS_AVAILABLE:
            return

        try:
            if self.event_publisher:
                self.event_publisher.publish(
                    channel="resilience:config_updated",
                    event_name="config_updated",
                    payload={
                        "config_type": config_type,
                        "config_name": config_name,
                        "timestamp": time.time(),
                    },
                    source_module="resilience_controller",
                )
                logger.info(f"配置更新消息已发布: {config_type} - {config_name}")
        except Exception as e:
            logger.error(f"发布配置更新消息失败: {e}")

    def _check_config_override(
        self, config_type: str, config_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        检查是否存在有效的配置覆盖

        Args:
            config_type: 配置类型 (circuit_breaker, rate_limit, degradation, bulkhead)
            config_name: 配置名称

        Returns:
            覆盖配置字典，如果不存在或已过期则返回None
        """
        if not self.config_source or not REDIS_AVAILABLE:
            return None

        try:
            override_key = f"{config_type}:{config_name}"
            override_data = self.config_source.hget(
                self.CONFIG_OVERRIDES_KEY, override_key
            )

            if not override_data:
                return None

            override_info = json.loads(override_data)
            current_time = time.time()

            # 检查是否过期
            if current_time > override_info.get("expires_at", 0):
                # 删除过期覆盖
                self.config_source.hdel(self.CONFIG_OVERRIDES_KEY, override_key)
                return None

            return override_info.get("config", None)

        except Exception as e:
            logger.error(f"检查配置覆盖失败: {config_type}:{config_name}, error: {e}")
            return None

    def _set_config_override(
        self,
        config_type: str,
        config_name: str,
        config_data: Dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        设置配置覆盖

        Args:
            config_type: 配置类型
            config_name: 配置名称
            config_data: 配置数据
            ttl_seconds: 覆盖有效期（秒），默认1小时

        Returns:
            是否设置成功
        """
        if not self.config_source or not REDIS_AVAILABLE:
            return False

        lock_key = f"lock:resilience:override:{config_type}:{config_name}"
        lock = OptimizedDistributedLock(self.config_source, lock_key, timeout=2.0)
        with lock:
            try:
                override_key = f"{config_type}:{config_name}"
                override_info = {
                    "config": config_data,
                    "created_at": time.time(),
                    "expires_at": time.time() + ttl_seconds,
                    "source": "manual_override",
                }

                result = self.config_source.hset(
                    self.CONFIG_OVERRIDES_KEY, override_key, json.dumps(override_info)
                )

                success = result == 1

                if success:
                    logger.info(
                        f"配置覆盖已设置: {config_type}:{config_name}, TTL: {ttl_seconds}秒"
                    )
                    self._publish_config_update(config_type, config_name)

                return success

            except Exception as e:
                logger.error(
                    f"设置配置覆盖失败: {config_type}:{config_name}, error: {e}"
                )
                return False

    def _clear_config_override(self, config_type: str, config_name: str) -> bool:
        """
        清除配置覆盖

        Args:
            config_type: 配置类型
            config_name: 配置名称

        Returns:
            是否清除成功
        """
        if not self.config_source or not REDIS_AVAILABLE:
            return False

        lock_key = f"lock:resilience:override:{config_type}:{config_name}"
        lock = OptimizedDistributedLock(self.config_source, lock_key, timeout=2.0)
        with lock:
            try:
                override_key = f"{config_type}:{config_name}"
                result = self.config_source.hdel(
                    self.CONFIG_OVERRIDES_KEY, override_key
                )

                success = result > 0

                if success:
                    logger.info(f"配置覆盖已清除: {config_type}:{config_name}")
                    self._publish_config_update(config_type, config_name)

                return success

            except Exception as e:
                logger.error(
                    f"清除配置覆盖失败: {config_type}:{config_name}, error: {e}"
                )
                return False

    def get_config_overrides(self) -> Dict[str, Any]:
        """
        获取所有配置覆盖

        Returns:
            配置覆盖字典
        """
        if not self.config_source or not REDIS_AVAILABLE:
            return {}

        try:
            overrides = self.config_source.hgetall(self.CONFIG_OVERRIDES_KEY)
            result = {}

            for key, value in overrides.items():
                try:
                    override_info = json.loads(value)
                    current_time = time.time()

                    # 过滤过期覆盖
                    if current_time <= override_info.get("expires_at", 0):
                        result[key] = override_info
                    else:
                        # 删除过期覆盖
                        self.config_source.hdel(self.CONFIG_OVERRIDES_KEY, key)

                except json.JSONDecodeError:
                    continue

            return result

        except Exception as e:
            logger.error(f"获取配置覆盖失败: {e}")
            return {}

    def clear_expired_overrides(self) -> int:
        """
        清除所有过期的配置覆盖

        Returns:
            清除的覆盖数量
        """
        if not self.config_source or not REDIS_AVAILABLE:
            return 0

        lock_key = f"lock:resilience:{self.CONFIG_OVERRIDES_KEY}:clear_expired"
        lock = OptimizedDistributedLock(self.config_source, lock_key, timeout=2.0)
        with lock:
            try:
                overrides = self.config_source.hgetall(self.CONFIG_OVERRIDES_KEY)
                expired_count = 0
                current_time = time.time()

                for key, value in overrides.items():
                    try:
                        override_info = json.loads(value)
                        if current_time > override_info.get("expires_at", 0):
                            self.config_source.hdel(self.CONFIG_OVERRIDES_KEY, key)
                            expired_count += 1

                    except json.JSONDecodeError:
                        self.config_source.hdel(self.CONFIG_OVERRIDES_KEY, key)
                        expired_count += 1

                if expired_count > 0:
                    logger.info(f"已清除 {expired_count} 个过期配置覆盖")

                return expired_count

            except Exception as e:
                logger.error(f"清除过期配置覆盖失败: {e}")
                return 0


# ==================== 熔断器实现 ====================


class CircuitBreaker:
    """熔断器实现 - 使用Redis Lua脚本保证原子性"""

    # Lua脚本：完整的熔断器业务流程 - 原子性执行
    EXECUTE_OR_RECORD_FAILURE_SCRIPT = """
    local name = KEYS[1]
    local operation = ARGV[1]  -- "check", "success", "failure"
    local failure_threshold = tonumber(ARGV[2])
    local recovery_timeout = tonumber(ARGV[3])
    local current_time = tonumber(ARGV[4])
    
    local state_key = "circuit_breaker:{" .. name .. "}:state"
    local failure_count_key = "circuit_breaker:{" .. name .. "}:failure_count"
    local last_failure_time_key = "circuit_breaker:{" .. name .. "}:last_failure_time"
    local half_open_calls_key = "circuit_breaker:{" .. name .. "}:half_open_calls"

    -- 默认事件意图，表示没有发生需要通知的状态转换
    local event_to_publish = "no_event"
    
    -- 获取当前状态
    local current_state = redis.call("GET", state_key)
    if not current_state then
        current_state = "closed"
    end
    
    -- 检查是否需要转换到半开状态
    if current_state == "open" then
        local last_failure_time = redis.call("GET", last_failure_time_key)
        if last_failure_time then
            last_failure_time = tonumber(last_failure_time)
            if current_time - last_failure_time >= recovery_timeout then
                redis.call("SET", state_key, "half_open")
                redis.call("SET", half_open_calls_key, 0)
                current_state = "half_open"
                event_to_publish = "state_changed_to_half_open"
            end
        end
    end
    
    -- 根据操作类型执行相应的逻辑
    if operation == "check" then
        -- 检查是否可以执行
        if current_state == "closed" then
            return {1, current_state, event_to_publish}  -- 可以执行
        elseif current_state == "half_open" then
            return {1, current_state, event_to_publish}  -- 在HALF_OPEN状态下允许执行
        else
            return {0, current_state, event_to_publish}  -- 不能执行
        end
    elseif operation == "success" then
        -- 记录成功
        if current_state == "closed" then
            -- 重置失败计数
            redis.call("SET", failure_count_key, 0)
            return {1, current_state, event_to_publish}
        elseif current_state == "half_open" then
            -- 在HALF_OPEN状态下，一次成功就立即切换到CLOSED状态
            redis.call("SET", state_key, "closed")
            redis.call("SET", failure_count_key, 0)
            redis.call("SET", half_open_calls_key, 0)
            current_state = "closed"
            event_to_publish = "state_changed_to_closed"
            return {1, current_state, event_to_publish}
        end
        return {1, current_state, event_to_publish}
    elseif operation == "failure" then
        -- 记录失败
        if current_state == "open" then
            -- 如果已经是开启状态，只更新失败时间
            redis.call("SET", last_failure_time_key, current_time)
            return {0, current_state, event_to_publish}
        end
        
        -- 获取当前失败计数
        local failure_count = redis.call("GET", failure_count_key)
        if not failure_count then
            failure_count = 0
        else
            failure_count = tonumber(failure_count)
        end
        
        -- 增加失败计数
        failure_count = failure_count + 1
        redis.call("SET", failure_count_key, failure_count)
        redis.call("SET", last_failure_time_key, current_time)
        
        -- 检查是否需要开启熔断器
        if current_state == "closed" and failure_count >= failure_threshold then
            redis.call("SET", state_key, "open")
            current_state = "open"
            event_to_publish = "state_changed_to_open"
        elseif current_state == "half_open" then
            -- 在HALF_OPEN状态下，一次失败就立即切换到OPEN状态
            redis.call("SET", state_key, "open")
            current_state = "open"
            event_to_publish = "state_changed_to_open"
        end
        
        return {0, current_state, event_to_publish}
    end
    
    return {0, current_state, event_to_publish}
    """

    def __init__(self, name: str, controller: ResilienceController):
        self.name = name
        self.controller = controller
        logger.info(f"熔断器 '{name}' 已初始化")

    def get_config(self) -> CircuitBreakerConfig:
        # 避免递归调用，直接返回默认配置
        return CircuitBreakerConfig(name=self.name)

    def get_state(self) -> CircuitBreakerState:
        return self.controller.get_circuit_breaker_state(self.name)

    def execute_atomic_operation(self, operation: str) -> tuple:
        """执行原子操作 - 统一的入口点，与EXECUTE_OR_RECORD_FAILURE_SCRIPT交互"""
        config = self.get_config()
        current_time = time.time()

        result = self.controller.circuit_breaker_execute_atomic_operation(
            self.name,
            operation,
            config.failure_threshold,
            config.recovery_timeout,
            current_time,
        )

        # Lua脚本返回的是一个列表，我们需要处理它
        # [can_execute, state, event_intent]
        if result and isinstance(result, list) and len(result) == 3:
            can_execute = bool(result[0])
            state = (
                result[1].decode("utf-8") if isinstance(result[1], bytes) else result[1]
            )
            event_intent = (
                result[2].decode("utf-8") if isinstance(result[2], bytes) else result[2]
            )
            return can_execute, state, event_intent

        # 发生错误或Redis不可用时的降级路径
        logger.warning(f"熔断器原子操作失败，使用降级路径: {operation}")
        return True, "closed", "no_event"

    def execute_with_atomic_check(self) -> bool:
        """原子执行检查并记录成功 - 解决竞态条件"""
        can_execute, state, event_intent = self.execute_atomic_operation("check")

        if can_execute:
            if state == "closed":
                logger.info(f"熔断器 '{self.name}' 已关闭")
            return True
        else:
            return False

    def get_failure_count(self) -> int:
        """从Redis获取失败计数"""
        return self.controller.get_circuit_breaker_failure_count(self.name)

    def get_last_failure_time(self) -> float:
        """从Redis获取最后失败时间"""
        return self.controller.get_circuit_breaker_last_failure_time(self.name)

    def get_half_open_calls(self) -> int:
        """从Redis获取半开调用次数"""
        return self.controller.get_circuit_breaker_half_open_calls(self.name)


# ==================== 限流器实现 ====================


class RateLimiter:
    """限流器实现 - 修复状态隔离问题"""

    # Lua脚本：令牌桶原子检查
    TOKEN_BUCKET_ATOMIC_SCRIPT = """
    local name = KEYS[1]
    local key = ARGV[1]
    local max_requests = tonumber(ARGV[2])
    local tokens_per_second = tonumber(ARGV[3])
    local current_time = tonumber(ARGV[4])
    
    local tokens_key = "rate_limiter:{" .. name .. "}:tokens:" .. key
    local last_update_key = "rate_limiter:{" .. name .. "}:last_update:" .. key
    
    -- 获取当前令牌数和最后更新时间
    local current_tokens = redis.call("GET", tokens_key)
    local last_update = redis.call("GET", last_update_key)
    
    if not current_tokens then
        current_tokens = 0
    else
        current_tokens = tonumber(current_tokens)
    end
    
    if not last_update then
        last_update = 0
    else
        last_update = tonumber(last_update)
    end
    
    -- 计算新令牌
    local time_passed = current_time - last_update
    local new_tokens = time_passed * tokens_per_second
    
    -- 更新令牌数量
    current_tokens = current_tokens + new_tokens
    if current_tokens > max_requests then
        current_tokens = max_requests
    end
    
    -- 检查是否有可用令牌
    if current_tokens >= 1 then
        current_tokens = current_tokens - 1
        redis.call("SET", tokens_key, current_tokens)
        redis.call("SET", last_update_key, current_time)
        return {1}  -- 允许
    else
        redis.call("SET", last_update_key, current_time)
        return {0}  -- 拒绝
    end
    """

    # Lua脚本：滑动窗口原子检查 - 使用ZSET高性能实现
    SLIDING_WINDOW_ATOMIC_SCRIPT = """
    local name = KEYS[1]
    local key = ARGV[1]
    local max_requests = tonumber(ARGV[2])
    local time_window = tonumber(ARGV[3])
    local current_time = tonumber(ARGV[4])
    
    local zset_key = "rate_limiter:{" .. name .. "}:sliding_window:" .. key
    
    -- 移除窗口外的旧记录 (O(log(N)+M))
    local window_start = current_time - time_window
    redis.call("ZREMRANGEBYSCORE", zset_key, "-inf", window_start)
    
    -- 获取当前窗口内的请求数 (O(1))
    local current_count = redis.call("ZCARD", zset_key)
    
    -- 检查是否超过限制
    if current_count < max_requests then
        -- 添加当前请求记录 (O(log(N)))
        redis.call("ZADD", zset_key, current_time, current_time .. ":" .. math.random())
        return {1}  -- 允许
    else
        return {0}  -- 拒绝
    end
    """

    # Lua脚本：固定窗口原子检查 - 使用原子操作保证一致性
    FIXED_WINDOW_ATOMIC_SCRIPT = """
    local name = KEYS[1]
    local key = ARGV[1]
    local max_requests = tonumber(ARGV[2])
    local time_window = tonumber(ARGV[3])
    local current_time = tonumber(ARGV[4])
    
    local window_key = "rate_limiter:{" .. name .. "}:fixed_window:" .. key
    local counter_key = "rate_limiter:{" .. name .. "}:counter:" .. key
    
    -- 计算当前窗口开始时间
    local window_start = math.floor(current_time / time_window) * time_window
    
    -- 获取当前窗口和计数器
    local current_window = redis.call("GET", window_key)
    local current_count = redis.call("GET", counter_key)
    
    if not current_window then
        current_window = 0
    else
        current_window = tonumber(current_window)
    end
    
    if not current_count then
        current_count = 0
    else
        current_count = tonumber(current_count)
    end
    
    -- 检查是否是新窗口
    if window_start > current_window then
        -- 新窗口，重置计数器
        redis.call("SET", window_key, window_start)
        redis.call("SET", counter_key, 1)
        return {1}  -- 允许
    else
        -- 当前窗口，检查并递增计数器
        if current_count < max_requests then
            redis.call("INCR", counter_key)
            return {1}  -- 允许
        else
            return {0}  -- 拒绝
        end
    end
    """

    def __init__(self, name: str, controller: ResilienceController):
        self.name = name
        self.controller = controller
        logger.info(f"限流器 '{name}' 已初始化")

    def get_config(self) -> RateLimitConfig:
        """获取当前配置"""
        # 避免递归调用，直接返回默认配置
        return RateLimitConfig(name=self.name)

    def get_tokens(self, key: str) -> float:
        """获取令牌数 - 从Redis获取"""
        try:
            tokens_key = f"rate_limiter:{{{self.name}}}:tokens:{key}"
            tokens_value = self.controller.config_source.get(tokens_key)
            return float(tokens_value) if tokens_value else 0.0
        except Exception as e:
            logger.error(f"获取令牌数失败: {e}")
            return 0.0

    def set_tokens(self, key: str, tokens: float):
        """设置令牌数 - 存储到Redis"""
        try:
            tokens_key = f"rate_limiter:{{{self.name}}}:tokens:{key}"
            self.controller.config_source.set(tokens_key, str(tokens))
        except Exception as e:
            logger.error(f"设置令牌数失败: {e}")

    def get_last_update_time(self, key: str) -> float:
        """获取最后更新时间 - 从Redis获取"""
        try:
            time_key = f"rate_limiter:{{{self.name}}}:last_update:{key}"
            time_value = self.controller.config_source.get(time_key)
            return float(time_value) if time_value else 0.0
        except Exception as e:
            logger.error(f"获取最后更新时间失败: {e}")
            return 0.0

    def set_last_update_time(self, key: str, timestamp: float):
        """设置最后更新时间 - 存储到Redis"""
        try:
            time_key = f"rate_limiter:{{{self.name}}}:last_update:{key}"
            self.controller.config_source.set(time_key, str(timestamp))
        except Exception as e:
            logger.error(f"设置最后更新时间失败: {e}")

    def get_request_times(self, key: str) -> List[float]:
        """获取请求时间列表 - 从Redis获取"""
        try:
            times_key = f"rate_limiter:{{{self.name}}}:request_times:{key}"
            times_data = self.controller.config_source.get(times_key)
            if times_data:
                return json.loads(times_data)
            return []
        except Exception as e:
            logger.error(f"获取请求时间列表失败: {e}")
            return []

    def set_request_times(self, key: str, times: List[float]):
        """设置请求时间列表 - 存储到Redis"""
        try:
            times_key = f"rate_limiter:{{{self.name}}}:request_times:{key}"
            self.controller.config_source.set(times_key, json.dumps(times))
        except Exception as e:
            logger.error(f"设置请求时间列表失败: {e}")

    def is_allowed(
        self, key: str = "default", multi_key: Optional[MultiDimensionalKey] = None
    ) -> bool:
        """检查是否允许请求"""
        config = self.get_config()
        if not config.enabled:
            return True

        # 多维限流检查
        if config.multi_dimensional and multi_key:
            logger.debug(f"执行多维限流检查: {multi_key}")
            if not self._check_multi_dimensional_limits(multi_key, config):
                logger.debug(f"多维限流检查失败")
                return False
            logger.debug(f"多维限流检查通过")

        # 单维限流检查（仅在非多维限流时执行）
        # 使用精确的类型分发逻辑
        if config.limit_type == RateLimitType.TOKEN_BUCKET:
            return self._token_bucket_atomic_check(key, config)
        elif config.limit_type == RateLimitType.SLIDING_WINDOW:
            return self._sliding_window_atomic_check(key, config)
        elif config.limit_type == RateLimitType.FIXED_WINDOW:
            return self._fixed_window_check(key, config)
        elif config.limit_type == RateLimitType.LEAKY_BUCKET:
            # LEAKY_BUCKET 类型尚未实现
            raise NotImplementedError(f"限流类型 {config.limit_type.value} 尚未实现")
        else:
            # 未知的限流类型
            # 安全地获取类型值，处理非枚举类型的情况
            try:
                limit_type_value = (
                    config.limit_type.value
                    if hasattr(config.limit_type, "value")
                    else str(config.limit_type)
                )
            except Exception:
                limit_type_value = str(config.limit_type)
            raise ValueError(f"不支持的限流类型: {limit_type_value}")

    def _token_bucket_atomic_check(self, key: str, config: RateLimitConfig) -> bool:
        """令牌桶原子检查 - 解决竞态条件"""
        current_time = time.time()

        return self.controller.rate_limiter_token_bucket_check(
            self.name, key, config.max_requests, config.tokens_per_second, current_time
        )

    def _sliding_window_atomic_check(self, key: str, config: RateLimitConfig) -> bool:
        """滑动窗口原子检查 - 解决竞态条件"""
        current_time = time.time()

        return self.controller.rate_limiter_sliding_window_check(
            self.name, key, config.max_requests, config.time_window, current_time
        )

    def _fixed_window_check(self, key: str, config: RateLimitConfig) -> bool:
        """固定窗口检查 - 使用Redis原子计数器"""
        current_time = time.time()

        return self.controller.rate_limiter_fixed_window_check(
            self.name, key, config.max_requests, config.time_window, current_time
        )

    def _check_multi_dimensional_limits(
        self, multi_key: MultiDimensionalKey, config: RateLimitConfig
    ) -> bool:
        """检查多维限流限制 - 使用控制器原子操作"""
        current_time = time.time()

        # 检查用户ID维度
        if multi_key.user_id and config.user_id_limit > 0:
            user_key = f"user_{multi_key.user_id}"
            if not self.controller.rate_limiter_sliding_window_check(
                self.name,
                user_key,
                config.user_id_limit,
                config.time_window,
                current_time,
            ):
                logger.warning(f"用户ID {multi_key.user_id} 超过限流限制")
                return False

        # 检查服务器ID维度
        if multi_key.server_id and config.server_id_limit > 0:
            server_key = f"server_{multi_key.server_id}"
            if not self.controller.rate_limiter_sliding_window_check(
                self.name,
                server_key,
                config.server_id_limit,
                config.time_window,
                current_time,
            ):
                logger.warning(f"服务器ID {multi_key.server_id} 超过限流限制")
                return False

        # 检查IP地址维度
        if multi_key.ip_address and config.ip_limit > 0:
            ip_key = f"ip_{multi_key.ip_address}"
            if not self.controller.rate_limiter_sliding_window_check(
                self.name, ip_key, config.ip_limit, config.time_window, current_time
            ):
                logger.warning(f"IP地址 {multi_key.ip_address} 超过限流限制")
                return False

        # 检查组合维度
        if config.combined_limit > 0:
            # 构建组合键，处理None值
            user_part = multi_key.user_id or "none"
            server_part = multi_key.server_id or "none"
            ip_part = multi_key.ip_address or "none"
            combined_key = f"combined_{user_part}_{server_part}_{ip_part}"
            if not self.controller.rate_limiter_sliding_window_check(
                self.name,
                combined_key,
                config.combined_limit,
                config.time_window,
                current_time,
            ):
                logger.warning(f"组合维度 {combined_key} 超过限流限制")
                return False

        return True


# ==================== 全局韧性组件注册表 ====================

# 全局韧性组件注册表 - 线程安全
_resilience_instances = {}
_resilience_lock = threading.RLock()


def get_resilience_controller() -> ResilienceController:
    """获取全局韧性控制器实例。必须在 init_app 调用后才能工作。"""
    if resilience.controller is None:
        # 这个错误比 "Working outside of application context" 更明确
        raise RuntimeError(
            "The resilience system was not initialized. "
            "You must call resilience.init_app(app) first."
        )
    return resilience.controller


def get_or_create_circuit_breaker(name: str) -> CircuitBreaker:
    """获取或创建熔断器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = CircuitBreaker(name, controller)
            logger.debug(f"创建新的熔断器实例: {name}")
        return _resilience_instances[name]


def get_or_create_rate_limiter(name: str) -> RateLimiter:
    """获取或创建限流器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = RateLimiter(name, controller)
            logger.debug(f"创建新的限流器实例: {name}")
        return _resilience_instances[name]


def get_or_create_bulkhead(name: str) -> "Bulkhead":
    """获取或创建舱壁隔离器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = Bulkhead(name, controller)
            logger.debug(f"创建新的舱壁隔离器实例: {name}")
        return _resilience_instances[name]


def clear_resilience_instances():
    """清空韧性组件注册表 - 主要用于测试"""
    with _resilience_lock:
        _resilience_instances.clear()
        logger.info("已清空韧性组件注册表")


def get_resilience_instances_info() -> Dict[str, str]:
    """获取韧性组件注册表信息 - 用于调试"""
    with _resilience_lock:
        return {
            name: type(instance).__name__
            for name, instance in _resilience_instances.items()
        }


# ==================== 辅助函数 ====================


# 创建一个辅助函数来处理事件发布，保持装饰器代码的整洁
def _publish_breaker_event(breaker: CircuitBreaker, event_intent: str, state: str):
    """根据意图发布熔断器事件。"""
    # "event_opened" -> "resilience.circuit_breaker.opened"
    event_name = f"resilience.circuit_breaker.{event_intent.split('_')[1]}"

    if breaker.controller.event_publisher:
        breaker.controller.event_publisher.publish(
            channel=RESILIENCE_EVENTS_CHANNEL,  # 假设这个常量可以被访问
            event_name=event_name,
            payload={"name": breaker.name, "state": state},
            source_module="resilience.circuit_breaker",
        )


# ==================== 装饰器工厂 ====================


def circuit_breaker(name: str, fallback_function: Optional[Callable] = None):
    """
    熔断器装饰器

    Args:
        name: 熔断器名称
        fallback_function: 降级函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = get_or_create_circuit_breaker(name)

            # 步骤1: 原子性地检查是否可以执行
            can_execute, state, event_intent = breaker.execute_atomic_operation("check")

            # 步骤2: 在任何业务逻辑之前，处理状态转换事件
            # 这一步是安全的，因为它只发布消息，不影响核心流程
            if event_intent != "no_event":
                try:
                    _publish_breaker_event(breaker, event_intent, state)
                except Exception as e:
                    logger.error(f"发布熔断器事件失败: {e}")

            if not can_execute:
                # 如果熔断器不允许执行，直接进入降级路径
                logger.warning(f"熔断器 '{name}' 开启 (状态: {state})，请求被阻止。")
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                else:
                    raise Exception(
                        f"CircuitBreaker '{name}' is open."
                    )  # 使用自定义异常更佳

            # 步骤3: 精确地保护核心业务函数
            try:
                # 只有 func 的调用在这个 try 块中
                result = func(*args, **kwargs)

                # 步骤4: 原子性地记录成功
                # 这个操作本身也可能失败，但不应影响到已经成功的业务结果
                try:
                    _, state, event_intent = breaker.execute_atomic_operation("success")
                    if event_intent != "no_event":
                        try:
                            _publish_breaker_event(breaker, event_intent, state)
                        except Exception as event_e:
                            logger.error(f"发布熔断器成功事件失败: {event_e}")
                except Exception as redis_e:
                    logger.error(f"记录熔断器 '{name}' 成功状态失败: {redis_e}")

                # 无论记录是否成功，都必须返回原始的、正确的业务结果
                return result

            except Exception as e:
                # 步骤5: 原子性地记录失败
                try:
                    _, state, event_intent = breaker.execute_atomic_operation("failure")
                    if event_intent != "no_event":
                        try:
                            _publish_breaker_event(breaker, event_intent, state)
                        except Exception as event_e:
                            logger.error(f"发布熔断器失败事件失败: {event_e}")
                except Exception as redis_e:
                    logger.error(f"记录熔断器 '{name}' 失败状态失败: {redis_e}")

                # 记录失败后，进入降级路径
                logger.warning(f"函数调用失败，熔断器 '{name}' 记录失败。原始错误: {e}")
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                else:
                    # 重新抛出原始的业务异常
                    raise e

        # 修正结构性错误：装饰器工厂必须返回装饰器本身
        return wrapper

    # 返回装饰器
    return decorator


def rate_limit(
    name: str,
    key_func: Optional[Callable] = None,
    multi_key_func: Optional[Callable] = None,
):
    """
    限流器装饰器

    Args:
        name: 限流器名称
        key_func: 生成限流键的函数
        multi_key_func: 生成多维限流键的函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用全局注册表获取或创建限流器实例
            limiter = get_or_create_rate_limiter(name)

            # 生成限流键
            if key_func:
                limit_key = key_func(*args, **kwargs)
            else:
                limit_key = "default"

            # 生成多维限流键
            multi_key = None
            if multi_key_func:
                multi_key = multi_key_func(*args, **kwargs)

            if not limiter.is_allowed(limit_key, multi_key):
                # 发布事件时使用异常保护，避免影响主流程
                try:
                    if limiter.controller.event_publisher:
                        limiter.controller.event_publisher.publish(
                            channel=RESILIENCE_EVENTS_CHANNEL,
                            event_name="resilence.rate_limit.triggered",
                            payload={"limiter_name": name, "key": limit_key},
                            source_module="resilence.rate_limiter",
                        )
                except Exception as e:
                    logger.error(f"发布限流事件失败: {e}")

                raise Exception(f"限流器 '{name}' 触发，请求被拒绝")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def degradable(name: str, fallback_function: Callable):
    """
    降级装饰器

    Args:
        name: 降级配置名称
        fallback_function: 降级函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            controller = get_resilience_controller()
            config = controller.get_degradation_config(name)

            if config.enabled:
                # 发布事件时使用异常保护，避免影响主流程
                try:
                    if controller.event_publisher:
                        controller.event_publisher.publish(
                            channel=RESILIENCE_EVENTS_CHANNEL,
                            event_name="resilence.degradation.activated",
                            payload={"degradation_name": name},
                            source_module="resilence.degradation",
                        )
                except Exception as e:
                    logger.error(f"发布降级事件失败: {e}")

                logger.info(f"降级 '{name}' 已启用，使用降级函数")
                return fallback_function(*args, **kwargs)

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ==================== 便捷函数 ====================


def get_circuit_breaker_state(name: str) -> Dict[str, Any]:
    """获取熔断器状态 - 所有状态都从Redis获取"""
    controller = get_resilience_controller()
    breaker = get_or_create_circuit_breaker(name)  # 使用全局注册表
    config = breaker.get_config()

    return {
        "name": name,
        "state": breaker.get_state().value,
        "failure_count": breaker.get_failure_count(),
        "last_failure_time": breaker.get_last_failure_time(),
        "half_open_calls": breaker.get_half_open_calls(),
        "config": {
            "failure_threshold": config.failure_threshold,
            "recovery_timeout": config.recovery_timeout,
            "expected_exception": config.expected_exception,
            "monitor_interval": config.monitor_interval,
        },
    }


def get_rate_limit_status(name: str) -> Dict[str, Any]:
    """获取限流器状态 - 使用全局注册表"""
    controller = get_resilience_controller()
    limiter = get_or_create_rate_limiter(name)  # 使用全局注册表
    config = limiter.get_config()

    return {
        "name": name,
        "enabled": config.enabled,
        "limit_type": config.limit_type.value,
        "max_requests": config.max_requests,
        "time_window": config.time_window,
        "tokens_per_second": config.tokens_per_second,
        "multi_dimensional": config.multi_dimensional,
        "user_id_limit": config.user_id_limit,
        "server_id_limit": config.server_id_limit,
        "ip_limit": config.ip_limit,
        "combined_limit": config.combined_limit,
    }


def set_circuit_breaker_config(name: str, use_override: bool = True, **kwargs) -> bool:
    """
    设置熔断器配置

    Args:
        name: 配置名称
        use_override: 是否使用覆盖层（运维人员手动配置时使用）
        **kwargs: 配置参数
    """
    controller = get_resilience_controller()
    config = controller.get_circuit_breaker_config(name)

    if config is None:
        # 如果配置不存在，创建默认配置
        config = CircuitBreakerConfig(name=name)

    # 更新配置
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return controller.set_circuit_breaker_config(name, config, use_override)


def set_rate_limit_config(name: str, use_override: bool = True, **kwargs) -> bool:
    """
    设置限流器配置

    Args:
        name: 配置名称
        use_override: 是否使用覆盖层（运维人员手动配置时使用）
        **kwargs: 配置参数
    """
    controller = get_resilience_controller()
    config = controller.get_rate_limit_config(name)

    if config is None:
        # 如果配置不存在，创建默认配置
        config = RateLimitConfig(name=name)

    # 更新配置
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return controller.set_rate_limit_config(name, config, use_override)


def set_degradation_config(name: str, use_override: bool = True, **kwargs) -> bool:
    """
    设置降级配置

    Args:
        name: 配置名称
        use_override: 是否使用覆盖层（运维人员手动配置时使用）
        **kwargs: 配置参数
    """
    controller = get_resilience_controller()
    config = controller.get_degradation_config(name)

    if config is None:
        # 如果配置不存在，创建默认配置
        config = DegradationConfig(name=name)

    # 更新配置
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return controller.set_degradation_config(name, config, use_override)


def get_all_resilience_configs() -> Dict[str, Any]:
    """获取所有韧性配置"""
    controller = get_resilience_controller()
    return controller.get_all_configs()


# ==================== 舱壁隔离机制 ====================


class IsolationStrategy(Enum):
    """隔离策略"""

    USER = "user"  # 按用户隔离
    ROLE = "role"  # 按角色隔离
    REQUEST_TYPE = "request_type"  # 按请求类型隔离
    PRIORITY = "priority"  # 按优先级隔离


class ResourceType(Enum):
    """资源类型"""

    THREAD_POOL = "thread_pool"  # 线程池
    CONNECTION_POOL = "connection_pool"  # 连接池
    MEMORY = "memory"  # 内存资源
    CPU = "cpu"  # CPU资源


@dataclass
class BulkheadConfig:
    """舱壁隔离配置 - 专注于并发请求数限制"""

    name: str
    strategy: IsolationStrategy = IsolationStrategy.USER
    max_concurrent_calls: int = 10  # 最大并发调用数
    max_wait_time: float = 5.0  # 最大等待时间（秒）
    timeout: float = 30.0  # 超时时间（秒）
    enabled: bool = True

    # 监控配置
    monitor_interval: float = 10.0  # 监控间隔（秒）
    alert_threshold: float = 0.8  # 告警阈值（资源使用率）


class Bulkhead:
    """舱壁隔离器 - 使用Redis状态管理解决多进程问题"""

    # Lua脚本：舱壁隔离原子操作
    BULKHEAD_ATOMIC_SCRIPT = """
    local name = KEYS[1]
    local operation = ARGV[1]  -- "check", "acquire", "release", "success", "failure"
    local max_concurrent_calls = tonumber(ARGV[2])
    local current_time = tonumber(ARGV[3])
    
    local active_calls_key = "bulkhead:{" .. name .. "}:active_calls"
    local total_calls_key = "bulkhead:{" .. name .. "}:total_calls"
    local failed_calls_key = "bulkhead:{" .. name .. "}:failed_calls"
    local last_call_time_key = "bulkhead:{" .. name .. "}:last_call_time"
    
    if operation == "check" then
        -- 检查是否可以执行
        local active_calls = redis.call("GET", active_calls_key)
        if not active_calls then
            active_calls = 0
        else
            active_calls = tonumber(active_calls)
        end
        
        if active_calls < max_concurrent_calls then
            return {1}  -- 可以执行
        else
            return {0}  -- 不能执行
        end
        
    elseif operation == "acquire" then
        -- 获取资源
        local active_calls = redis.call("GET", active_calls_key)
        if not active_calls then
            active_calls = 0
        else
            active_calls = tonumber(active_calls)
        end
        
        if active_calls < max_concurrent_calls then
            active_calls = active_calls + 1
            redis.call("SET", active_calls_key, active_calls)
            redis.call("SET", last_call_time_key, current_time)
            return {1, active_calls}  -- 成功获取
        else
            return {0, active_calls}  -- 无法获取
        end
        
    elseif operation == "release" then
        -- 释放资源
        local active_calls = redis.call("GET", active_calls_key)
        if not active_calls then
            active_calls = 0
        else
            active_calls = tonumber(active_calls)
        end
        
        if active_calls > 0 then
            active_calls = active_calls - 1
            redis.call("SET", active_calls_key, active_calls)
        end
        
        return {1, active_calls}
        
    elseif operation == "success" then
        -- 记录成功调用
        local total_calls = redis.call("GET", total_calls_key)
        if not total_calls then
            total_calls = 0
        else
            total_calls = tonumber(total_calls)
        end
        
        total_calls = total_calls + 1
        redis.call("SET", total_calls_key, total_calls)
        
        return {1, total_calls}
        
    elseif operation == "failure" then
        -- 记录失败调用
        local total_calls = redis.call("GET", total_calls_key)
        local failed_calls = redis.call("GET", failed_calls_key)
        
        if not total_calls then
            total_calls = 0
        else
            total_calls = tonumber(total_calls)
        end
        
        if not failed_calls then
            failed_calls = 0
        else
            failed_calls = tonumber(failed_calls)
        end
        
        total_calls = total_calls + 1
        failed_calls = failed_calls + 1
        
        redis.call("SET", total_calls_key, total_calls)
        redis.call("SET", failed_calls_key, failed_calls)
        
        return {1, total_calls, failed_calls}
    end
    
    return {0}
    """

    def __init__(self, name: str, controller: ResilienceController):
        self.name = name
        self.controller = controller
        logger.info(f"舱壁隔离器 '{name}' 已初始化")

    def get_config(self) -> BulkheadConfig:
        """获取当前配置"""
        # 避免递归调用，直接返回默认配置
        return BulkheadConfig(name=self.name)

    def set_config(self, config: BulkheadConfig) -> bool:
        """设置配置"""
        return self.controller.set_bulkhead_config(self.name, config)

    def acquire_resource(self) -> bool:
        """获取资源 - 原子操作，专注于并发请求数限制"""
        config = self.get_config()
        current_time = time.time()

        result = self.controller.bulkhead_execute_atomic_operation(
            self.name, "acquire", config.max_concurrent_calls, current_time
        )

        success, active_calls = result

        if success == 1:
            logger.debug(
                f"舱壁隔离器 '{self.name}' 获取资源成功，当前活跃调用: {active_calls}"
            )
            return True
        else:
            logger.warning(
                f"舱壁隔离器 '{self.name}' 获取资源失败，当前活跃调用: {active_calls}/{config.max_concurrent_calls}"
            )
            return False

    def release_resource(self):
        """释放资源 - 原子操作"""
        result = self.controller.bulkhead_execute_atomic_operation(
            self.name, "release", 0, time.time()
        )

        success, active_calls = result
        logger.debug(f"舱壁隔离器 '{self.name}' 释放资源，当前活跃调用: {active_calls}")

    def record_success(self):
        """记录成功调用 - 原子操作"""
        result = self.controller.bulkhead_execute_atomic_operation(
            self.name, "success", 0, time.time()
        )

        success, total_calls = result
        logger.debug(f"舱壁隔离器 '{self.name}' 记录成功调用，总调用数: {total_calls}")

    def record_failure(self):
        """记录失败调用 - 原子操作"""
        result = self.controller.bulkhead_execute_atomic_operation(
            self.name, "failure", 0, time.time()
        )

        success, total_calls, failed_calls = result
        logger.debug(
            f"舱壁隔离器 '{self.name}' 记录失败调用，总调用数: {total_calls}，失败调用数: {failed_calls}"
        )

    def get_active_calls(self) -> int:
        """从Redis获取活跃调用数"""
        return self.controller.get_bulkhead_active_calls(self.name)

    def get_total_calls(self) -> int:
        """从Redis获取总调用数"""
        return self.controller.get_bulkhead_total_calls(self.name)

    def get_failed_calls(self) -> int:
        """从Redis获取失败调用数"""
        return self.controller.get_bulkhead_failed_calls(self.name)

    def get_last_call_time(self) -> float:
        """从Redis获取最后调用时间"""
        return self.controller.get_bulkhead_last_call_time(self.name)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息 - 专注于并发请求数统计"""
        config = self.get_config()

        active_calls = self.get_active_calls()
        total_calls = self.get_total_calls()
        failed_calls = self.get_failed_calls()
        last_call_time = self.get_last_call_time()

        return {
            "name": self.name,
            "strategy": config.strategy.value,
            "enabled": config.enabled,
            "active_calls": active_calls,
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "max_concurrent_calls": config.max_concurrent_calls,
            "last_call_time": last_call_time,
            "failure_rate": failed_calls / max(total_calls, 1),
            "utilization_rate": active_calls / max(config.max_concurrent_calls, 1),
        }


# ==================== 舱壁隔离装饰器 ====================


def bulkhead(name: str, strategy: IsolationStrategy = IsolationStrategy.USER):
    """
    舱壁隔离装饰器 - 使用原子操作解决多进程问题

    Args:
        name: 舱壁隔离器名称
        strategy: 隔离策略
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用全局注册表获取或创建舱壁隔离器实例
            bulkhead_instance = get_or_create_bulkhead(name)
            config = bulkhead_instance.get_config()

            # 禁用状态下直接执行
            if not config.enabled:
                try:
                    bulkhead_instance.record_success()
                except Exception as e:
                    logger.error(f"记录舱壁隔离器 '{name}' 成功状态失败: {e}")
                return func(*args, **kwargs)

            start_time = time.time()

            # 原子性获取资源
            if not bulkhead_instance.acquire_resource():
                raise Exception(f"舱壁隔离器 '{name}' 无法获取资源，已达到最大并发限制")

            try:
                # 执行函数
                result = func(*args, **kwargs)
                # 记录成功调用 - 使用异常保护
                try:
                    bulkhead_instance.record_success()
                except Exception as e:
                    logger.error(f"记录舱壁隔离器 '{name}' 成功状态失败: {e}")
                return result
            except Exception as e:
                # 记录失败调用 - 使用异常保护
                try:
                    bulkhead_instance.record_failure()
                except Exception as record_e:
                    logger.error(f"记录舱壁隔离器 '{name}' 失败状态失败: {record_e}")
                # 重新抛出原始的业务异常
                raise e
            finally:
                # 释放资源 - 使用异常保护
                try:
                    bulkhead_instance.release_resource()
                except Exception as e:
                    logger.error(f"释放舱壁隔离器 '{name}' 资源失败: {e}")

        return wrapper

    return decorator


# ==================== 便捷函数 ====================


def get_bulkhead_stats(name: str) -> Dict[str, Any]:
    """获取舱壁隔离器状态 - 从Redis获取"""
    controller = get_resilience_controller()
    bulkhead_instance = get_or_create_bulkhead(name)
    return bulkhead_instance.get_stats()


def set_bulkhead_config(name: str, **kwargs) -> bool:
    """设置舱壁隔离器配置"""
    controller = get_resilience_controller()

    # 获取现有配置或创建新配置
    config = controller.get_bulkhead_config(name)
    if config is None:
        config = BulkheadConfig(name=name)

    # 更新配置
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # 使用控制器的set_bulkhead_config方法
    return controller.set_bulkhead_config(name, config)
