"""
OPA策略管理器

负责管理Open Policy Agent策略的加载、更新和缓存
支持动态策略加载、性能监控和错误处理
增强版：支持自适应策略调整、性能优化和详细监控
"""

import json
import logging
import requests
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import hashlib
import threading
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class PolicyMetrics:
    """策略性能指标"""

    total_evaluations: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
    average_response_time: float = 0.0
    last_evaluation_time: Optional[datetime] = None
    cache_hits: int = 0
    cache_misses: int = 0

    # 新增：详细性能指标
    response_time_history: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rate: float = 0.0
    throughput_per_minute: float = 0.0
    policy_complexity_score: float = 0.0


@dataclass
class AdaptivePolicyConfig:
    """自适应策略配置"""

    auto_adjust_enabled: bool = True
    confidence_threshold: float = 0.95
    performance_threshold: float = 100.0  # 毫秒
    error_rate_threshold: float = 0.05
    adjustment_cooldown: int = 300  # 秒
    last_adjustment_time: Optional[datetime] = None


class OPAPolicyManager:
    """
    OPA策略管理器

    负责与OPA服务交互，管理策略的加载、更新和缓存
    支持动态策略加载、性能监控和错误处理
    增强版：支持自适应策略调整、性能优化和详细监控
    """

    def __init__(self, opa_url: str = "http://localhost:8181", cache_ttl: int = 300):
        """
        初始化OPA策略管理器

        Args:
            opa_url: OPA服务URL
            cache_ttl: 缓存TTL（秒）
        """
        self.opa_url = opa_url.rstrip("/")
        self.cache_ttl = cache_ttl
        self._policy_cache = {}
        self._cache_timestamps = {}
        self._evaluation_cache = {}
        self._metrics = PolicyMetrics()
        self._lock = threading.RLock()

        # 新增：自适应策略配置
        self._adaptive_config = AdaptivePolicyConfig()

        # 新增：策略性能历史
        self._policy_performance_history = defaultdict(lambda: deque(maxlen=50))

        # 新增：智能缓存配置
        self._smart_cache_config = {
            "max_cache_size": 1000,
            "cache_eviction_policy": "lru",
            "preload_frequently_used": True,
        }

        # 验证OPA服务连接
        self._validate_opa_connection()

        # 启动策略监控线程
        self._start_policy_monitor()

        # 启动自适应调整线程
        self._start_adaptive_adjustment()

    def _validate_opa_connection(self) -> bool:
        """
        验证OPA服务连接

        Returns:
            bool: 连接是否成功
        """
        try:
            response = requests.get(f"{self.opa_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"OPA服务连接成功: {self.opa_url}")
                return True
            else:
                logger.error(f"OPA服务连接失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"OPA服务连接异常: {e}")
            return False

    def load_policy(self, policy_name: str, policy_content: str) -> bool:
        """
        加载策略到OPA服务

        Args:
            policy_name: 策略名称
            policy_content: 策略内容

        Returns:
            bool: 加载是否成功
        """
        try:
            url = f"{self.opa_url}/v1/policies/{policy_name}"
            headers = {"Content-Type": "text/plain"}

            response = requests.put(
                url, data=policy_content, headers=headers, timeout=10
            )

            if response.status_code == 200:
                logger.info(f"策略加载成功: {policy_name}")
                # 更新缓存
                with self._lock:
                    self._policy_cache[policy_name] = policy_content
                    self._cache_timestamps[policy_name] = datetime.now()

                    # 计算策略复杂度
                    complexity_score = self._calculate_policy_complexity(policy_content)
                    self._metrics.policy_complexity_score = complexity_score

                return True
            else:
                logger.error(
                    f"策略加载失败: {policy_name}, 状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"策略加载异常: {policy_name}, 错误: {e}")
            return False

    def _calculate_policy_complexity(self, policy_content: str) -> float:
        """计算策略复杂度分数"""
        try:
            # 基于策略内容的复杂度计算
            lines = len(policy_content.split("\n"))
            rules = policy_content.count("allow {")
            conditions = (
                policy_content.count("==")
                + policy_content.count("!=")
                + policy_content.count("in")
            )

            # 复杂度分数 = (行数 * 0.1) + (规则数 * 0.3) + (条件数 * 0.2)
            complexity = (lines * 0.1) + (rules * 0.3) + (conditions * 0.2)
            return min(complexity, 10.0)  # 最大复杂度为10
        except Exception:
            return 1.0

    def evaluate_policy(
        self, policy_name: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估策略

        Args:
            policy_name: 策略名称
            input_data: 输入数据

        Returns:
            Dict[str, Any]: 评估结果
        """
        try:
            start_time = time.time()

            # 检查缓存
            cache_key = self._generate_cache_key(policy_name, input_data)
            with self._lock:
                if cache_key in self._evaluation_cache:
                    cached_result = self._evaluation_cache[cache_key]
                    if datetime.now() - cached_result["timestamp"] < timedelta(
                        seconds=self.cache_ttl
                    ):
                        self._metrics.cache_hits += 1
                        return cached_result["result"]
                self._metrics.cache_misses += 1

            url = f"{self.opa_url}/v1/data/{policy_name}"
            headers = {"Content-Type": "application/json"}

            response = requests.post(url, json=input_data, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()

                # 更新缓存
                with self._lock:
                    self._evaluation_cache[cache_key] = {
                        "result": result,
                        "timestamp": datetime.now(),
                    }

                # 更新性能指标
                response_time = (time.time() - start_time) * 1000  # 毫秒
                self._update_metrics(True, response_time)

                # 记录策略性能历史
                self._record_policy_performance(policy_name, response_time, True)

                logger.debug(
                    f"策略评估成功: {policy_name}, 响应时间: {response_time:.2f}ms"
                )
                return result
            else:
                logger.error(
                    f"策略评估失败: {policy_name}, 状态码: {response.status_code}"
                )
                self._update_metrics(False, 0)
                self._record_policy_performance(policy_name, 0, False)
                return {"result": {"allow": False}}

        except Exception as e:
            logger.error(f"策略评估异常: {policy_name}, 错误: {e}")
            self._update_metrics(False, 0)
            self._record_policy_performance(policy_name, 0, False)
            return {"result": {"allow": False}}

    def _record_policy_performance(
        self, policy_name: str, response_time: float, success: bool
    ):
        """记录策略性能历史"""
        with self._lock:
            self._policy_performance_history[policy_name].append(
                {
                    "response_time": response_time,
                    "success": success,
                    "timestamp": datetime.now(),
                }
            )

    def _generate_cache_key(self, policy_name: str, input_data: Dict[str, Any]) -> str:
        """生成缓存键"""
        data_str = json.dumps(input_data, sort_keys=True)
        return hashlib.md5(f"{policy_name}:{data_str}".encode()).hexdigest()

    def _update_metrics(self, success: bool, response_time: float):
        """更新性能指标"""
        with self._lock:
            self._metrics.total_evaluations += 1
            if success:
                self._metrics.successful_evaluations += 1
            else:
                self._metrics.failed_evaluations += 1

            # 更新响应时间历史
            self._metrics.response_time_history.append(response_time)

            # 更新平均响应时间
            if self._metrics.total_evaluations > 0:
                self._metrics.average_response_time = (
                    self._metrics.average_response_time
                    * (self._metrics.total_evaluations - 1)
                    + response_time
                ) / self._metrics.total_evaluations

            # 更新错误率
            self._metrics.error_rate = self._metrics.failed_evaluations / max(
                self._metrics.total_evaluations, 1
            )

            # 更新吞吐量（每分钟）
            if len(self._metrics.response_time_history) >= 2:
                time_diff = (
                    (
                        datetime.now() - self._metrics.last_evaluation_time
                    ).total_seconds()
                    if self._metrics.last_evaluation_time
                    else 60
                )
                self._metrics.throughput_per_minute = (
                    (60 / max(time_diff, 1)) if time_diff > 0 else 0
                )

            self._metrics.last_evaluation_time = datetime.now()

    def check_permission(
        self,
        user: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        context: Dict[str, Any] = None,
    ) -> bool:
        """
        检查权限

        Args:
            user: 用户信息
            resource: 资源信息
            action: 操作
            context: 上下文信息

        Returns:
            bool: 是否允许访问
        """
        try:
            # 构建输入数据
            input_data = {
                "input": {
                    "user": user,
                    "resource": resource,
                    "action": action,
                    "context": context or {},
                    "time": {
                        "timestamp": int(time.time()),
                        "weekday": datetime.now().weekday(),
                        "hour": datetime.now().hour,
                        "minute": datetime.now().minute,
                    },
                }
            }

            # 评估策略
            result = self.evaluate_policy("permission.abac", input_data)

            # 检查结果
            if "result" in result and "allow" in result["result"]:
                return result["result"]["allow"]
            else:
                logger.warning(f"策略评估结果格式异常: {result}")
                return False

        except Exception as e:
            logger.error(f"权限检查异常: {e}")
            return False

    def get_policy_info(self, policy_name: str) -> Dict[str, Any]:
        """
        获取策略信息

        Args:
            policy_name: 策略名称

        Returns:
            Dict[str, Any]: 策略信息
        """
        try:
            url = f"{self.opa_url}/v1/policies/{policy_name}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                return {
                    "name": policy_name,
                    "content": response.text,
                    "last_updated": datetime.now().isoformat(),
                }
            else:
                return {"error": f"获取策略失败: {response.status_code}"}

        except Exception as e:
            return {"error": f"获取策略异常: {e}"}

    def list_policies(self) -> List[str]:
        """
        列出所有策略

        Returns:
            List[str]: 策略名称列表
        """
        try:
            url = f"{self.opa_url}/v1/policies"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                policies = response.json()
                return [policy["id"] for policy in policies.get("result", [])]
            else:
                logger.error(f"列出策略失败: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"列出策略异常: {e}")
            return []

    def delete_policy(self, policy_name: str) -> bool:
        """
        删除策略

        Args:
            policy_name: 策略名称

        Returns:
            bool: 删除是否成功
        """
        try:
            url = f"{self.opa_url}/v1/policies/{policy_name}"
            response = requests.delete(url, timeout=5)

            if response.status_code == 200:
                logger.info(f"策略删除成功: {policy_name}")
                # 清除缓存
                with self._lock:
                    if policy_name in self._policy_cache:
                        del self._policy_cache[policy_name]
                    if policy_name in self._cache_timestamps:
                        del self._cache_timestamps[policy_name]
                return True
            else:
                logger.error(
                    f"策略删除失败: {policy_name}, 状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"策略删除异常: {policy_name}, 错误: {e}")
            return False

    def reload_policies(self) -> bool:
        """
        重新加载所有策略

        Returns:
            bool: 重新加载是否成功
        """
        try:
            # 获取所有策略
            policies = self.list_policies()

            success_count = 0
            for policy_name in policies:
                if policy_name in self._policy_cache:
                    policy_content = self._policy_cache[policy_name]
                    if self.load_policy(policy_name, policy_content):
                        success_count += 1

            logger.info(f"策略重新加载完成: {success_count}/{len(policies)} 成功")
            return success_count == len(policies)

        except Exception as e:
            logger.error(f"策略重新加载异常: {e}")
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态

        Returns:
            Dict[str, Any]: 缓存状态信息
        """
        with self._lock:
            return {
                "policy_cache_size": len(self._policy_cache),
                "evaluation_cache_size": len(self._evaluation_cache),
                "cache_ttl": self.cache_ttl,
                "metrics": {
                    "total_evaluations": self._metrics.total_evaluations,
                    "successful_evaluations": self._metrics.successful_evaluations,
                    "failed_evaluations": self._metrics.failed_evaluations,
                    "average_response_time": self._metrics.average_response_time,
                    "cache_hits": self._metrics.cache_hits,
                    "cache_misses": self._metrics.cache_misses,
                    "cache_hit_rate": (
                        self._metrics.cache_hits
                        / max(self._metrics.cache_hits + self._metrics.cache_misses, 1)
                    ),
                    "error_rate": self._metrics.error_rate,
                    "throughput_per_minute": self._metrics.throughput_per_minute,
                    "policy_complexity_score": self._metrics.policy_complexity_score,
                    "last_evaluation_time": (
                        self._metrics.last_evaluation_time.isoformat()
                        if self._metrics.last_evaluation_time
                        else None
                    ),
                },
            }

    def clear_cache(self) -> None:
        """清除缓存"""
        with self._lock:
            self._policy_cache.clear()
            self._cache_timestamps.clear()
            self._evaluation_cache.clear()
            logger.info("策略缓存已清除")

    def get_policy_performance_analysis(self, policy_name: str) -> Dict[str, Any]:
        """
        获取策略性能分析

        Args:
            policy_name: 策略名称

        Returns:
            Dict[str, Any]: 性能分析结果
        """
        with self._lock:
            history = self._policy_performance_history[policy_name]
            if not history:
                return {"error": "无性能数据"}

            response_times = [entry["response_time"] for entry in history]
            success_count = sum(1 for entry in history if entry["success"])
            total_count = len(history)

            return {
                "policy_name": policy_name,
                "total_evaluations": total_count,
                "success_rate": success_count / total_count if total_count > 0 else 0,
                "average_response_time": (
                    statistics.mean(response_times) if response_times else 0
                ),
                "min_response_time": min(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "response_time_std": (
                    statistics.stdev(response_times) if len(response_times) > 1 else 0
                ),
                "last_evaluation": (
                    history[-1]["timestamp"].isoformat() if history else None
                ),
            }

    def adaptive_policy_adjustment(self) -> Dict[str, Any]:
        """
        自适应策略调整

        Returns:
            Dict[str, Any]: 调整结果
        """
        if not self._adaptive_config.auto_adjust_enabled:
            return {"status": "disabled"}

        current_time = datetime.now()
        if (
            self._adaptive_config.last_adjustment_time
            and (
                current_time - self._adaptive_config.last_adjustment_time
            ).total_seconds()
            < self._adaptive_config.adjustment_cooldown
        ):
            return {"status": "cooldown"}

        adjustments = []

        # 检查性能阈值
        if (
            self._metrics.average_response_time
            > self._adaptive_config.performance_threshold
        ):
            adjustments.append(
                {
                    "type": "performance",
                    "action": "optimize_cache",
                    "reason": f"平均响应时间 {self._metrics.average_response_time:.2f}ms 超过阈值 {self._adaptive_config.performance_threshold}ms",
                }
            )

        # 检查错误率阈值
        if self._metrics.error_rate > self._adaptive_config.error_rate_threshold:
            adjustments.append(
                {
                    "type": "reliability",
                    "action": "increase_timeout",
                    "reason": f"错误率 {self._metrics.error_rate:.2%} 超过阈值 {self._adaptive_config.error_rate_threshold:.2%}",
                }
            )

        # 应用调整
        if adjustments:
            self._apply_policy_adjustments(adjustments)
            self._adaptive_config.last_adjustment_time = current_time

            return {
                "status": "adjusted",
                "adjustments": adjustments,
                "timestamp": current_time.isoformat(),
            }

        return {"status": "no_adjustment_needed"}

    def _apply_policy_adjustments(self, adjustments: List[Dict[str, Any]]):
        """应用策略调整"""
        for adjustment in adjustments:
            if adjustment["action"] == "optimize_cache":
                # 优化缓存策略
                self._optimize_cache_strategy()
            elif adjustment["action"] == "increase_timeout":
                # 增加超时时间
                self._increase_timeout()

        logger.info(f"应用策略调整: {adjustments}")

    def _optimize_cache_strategy(self):
        """优化缓存策略"""
        # 增加缓存大小
        self._smart_cache_config["max_cache_size"] = min(
            self._smart_cache_config["max_cache_size"] * 1.5, 2000
        )

        # 预加载常用策略
        if self._smart_cache_config["preload_frequently_used"]:
            self._preload_frequent_policies()

    def _increase_timeout(self):
        """增加超时时间"""
        # 这里可以调整请求超时时间
        pass

    def _preload_frequent_policies(self):
        """预加载常用策略"""
        # 实现预加载逻辑
        pass

    def _start_policy_monitor(self):
        """启动策略监控线程"""

        def monitor_policies():
            while True:
                try:
                    # 检查策略缓存是否过期
                    current_time = datetime.now()
                    expired_policies = []

                    with self._lock:
                        for policy_name, timestamp in self._cache_timestamps.items():
                            if current_time - timestamp > timedelta(
                                seconds=self.cache_ttl
                            ):
                                expired_policies.append(policy_name)

                    # 重新加载过期的策略
                    for policy_name in expired_policies:
                        logger.debug(f"重新加载过期策略: {policy_name}")
                        self.reload_policies()

                    # 清理过期的评估缓存
                    with self._lock:
                        expired_evaluations = []
                        for cache_key, cache_data in self._evaluation_cache.items():
                            if current_time - cache_data["timestamp"] > timedelta(
                                seconds=self.cache_ttl
                            ):
                                expired_evaluations.append(cache_key)

                        for cache_key in expired_evaluations:
                            del self._evaluation_cache[cache_key]

                    time.sleep(60)  # 每分钟检查一次

                except Exception as e:
                    logger.error(f"策略监控异常: {e}")
                    time.sleep(60)

        monitor_thread = threading.Thread(target=monitor_policies, daemon=True)
        monitor_thread.start()
        logger.info("策略监控线程已启动")

    def _start_adaptive_adjustment(self):
        """启动自适应调整线程"""

        def adaptive_adjustment():
            while True:
                try:
                    # 执行自适应调整
                    result = self.adaptive_policy_adjustment()
                    if result["status"] == "adjusted":
                        logger.info(f"自适应策略调整: {result}")

                    time.sleep(300)  # 每5分钟检查一次

                except Exception as e:
                    logger.error(f"自适应调整异常: {e}")
                    time.sleep(300)

        adjustment_thread = threading.Thread(target=adaptive_adjustment, daemon=True)
        adjustment_thread.start()
        logger.info("自适应调整线程已启动")


# 全局OPA策略管理器实例
_opa_policy_manager = None


def get_opa_policy_manager() -> OPAPolicyManager:
    """获取OPA策略管理器实例"""
    global _opa_policy_manager
    if _opa_policy_manager is None:
        _opa_policy_manager = OPAPolicyManager()
    return _opa_policy_manager
