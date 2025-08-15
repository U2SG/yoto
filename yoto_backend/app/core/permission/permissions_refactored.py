"""
重构后的权限系统主模块

整合所有子模块的功能，提供统一的权限管理接口
"""

import time
import logging
import json
from typing import Dict, List, Optional, Set, Any, Callable
from functools import wraps

# 导入子模块
from .permission_decorators import (
    require_permission,
    require_permission_v2,
    require_permissions_v2,
    require_permission_with_expression_v2,
    evaluate_permission_expression,
    invalidate_permission_check_cache,
)

from .opa_policy_manager import get_opa_policy_manager

from .hybrid_permission_cache import (
    get_hybrid_cache,
    get_permission,
    batch_get_permissions,
    invalidate_user_permissions,
    invalidate_role_permissions,
    get_cache_stats,
    get_performance_analysis,
    refresh_user_permissions,
    batch_refresh_user_permissions,
    refresh_role_permissions,
    warm_up_cache,
)

from .permission_queries import (
    optimized_single_user_query,
    batch_precompute_permissions,
    get_users_by_role,
)

from .permission_registry import (
    register_permission,
    register_role,
    batch_register_permissions,
    batch_register_roles,
    assign_permissions_to_role_v2,
    assign_roles_to_user_v2,
    get_permission_registry_stats,
    list_registered_permissions,
    list_registered_roles,
)

from .permission_invalidation import (
    add_delayed_invalidation,
    get_delayed_invalidation_stats,
    get_invalidation_statistics,
    get_smart_batch_invalidation_analysis,
    execute_smart_batch_invalidation,
    execute_global_smart_batch_invalidation,
    process_delayed_invalidations,
    get_cache_auto_tune_suggestions,
    get_cache_invalidation_strategy_analysis,
    cleanup_expired_invalidations,
    trigger_background_invalidation_processing,
    trigger_queue_monitoring,
    trigger_cleanup_task,
    get_redis_connection_status,
)

from .permission_monitor import (
    get_permission_monitor,
    record_cache_hit_rate,
    record_response_time,
    record_error_rate,
    get_health_status,
    get_performance_report,
    get_events_summary,
    get_values_summary,
    clear_alerts,
)


from .permission_ml import (
    get_ml_performance_monitor,
    register_ml_config_callback,
    unregister_ml_config_callback,
)

from .permission_resilience import (
    # 控制器和全局实例
    get_resilience_controller,
    get_or_create_circuit_breaker,
    get_or_create_rate_limiter,
    get_or_create_bulkhead,
    clear_resilience_instances,
    get_resilience_instances_info,
    # 装饰器
    circuit_breaker,
    rate_limit,
    degradable,
    bulkhead,
    # 便捷函数
    get_circuit_breaker_state,
    get_rate_limit_status,
    get_bulkhead_stats,
    set_circuit_breaker_config,
    set_rate_limit_config,
    set_degradation_config,
    set_bulkhead_config,
    get_all_resilience_configs,
    # 配置类
    CircuitBreakerConfig,
    RateLimitConfig,
    DegradationConfig,
    BulkheadConfig,
    # 枚举类
    CircuitBreakerState,
    RateLimitType,
    DegradationLevel,
    IsolationStrategy,
    ResourceType,
    # 数据结构
    MultiDimensionalKey,
)

logger = logging.getLogger(__name__)


class PermissionSystem:
    """权限系统主类 - 无状态设计"""

    def __init__(self):
        # 获取缓存和监控实例
        self.cache = get_hybrid_cache()
        self.monitor = get_permission_monitor()

        # 获取韧性控制器
        self.resilience_controller = get_resilience_controller()

        # 初始化ML优化回调
        self._setup_ml_optimization()

    def _setup_ml_optimization(self):
        """设置ML优化回调"""
        try:
            # 注册配置更新回调
            register_ml_config_callback(self._apply_ml_optimization)
            logger.info("ML优化回调已注册")
        except Exception as e:
            logger.error(f"设置ML优化回调失败: {e}")

    def _apply_ml_optimization(self, config: Dict[str, Any]):
        """
        应用ML优化配置到实际组件

        Args:
            config: 优化配置字典
        """
        try:
            logger.info(f"应用ML优化配置: {config}")

            # 应用缓存相关配置
            if "cache_max_size" in config:
                # 这里需要根据实际的缓存接口来应用配置
                # 暂时记录日志，实际应用中需要调用缓存组件的配置方法
                logger.info(f"更新缓存最大大小: {config['cache_max_size']}")
                # self.cache.set_max_size(config['cache_max_size'])  # 实际调用

            # 应用连接池相关配置
            if "connection_pool_size" in config:
                logger.info(f"更新连接池大小: {config['connection_pool_size']}")
                # self.cache.set_connection_pool_size(config['connection_pool_size'])  # 实际调用

            # 应用超时相关配置
            if "socket_timeout" in config:
                logger.info(f"更新Socket超时: {config['socket_timeout']}")
                # self.cache.set_socket_timeout(config['socket_timeout'])  # 实际调用

            if "lock_timeout" in config:
                logger.info(f"更新锁超时: {config['lock_timeout']}")
                # self.cache.set_lock_timeout(config['lock_timeout'])  # 实际调用

            # 应用批处理相关配置
            if "batch_size" in config:
                logger.info(f"更新批处理大小: {config['batch_size']}")
                # self.cache.set_batch_size(config['batch_size'])  # 实际调用

            logger.info("ML优化配置应用完成")

        except Exception as e:
            logger.error(f"应用ML优化配置失败: {e}")

    def check_permission(
        self,
        user_id: int,
        permission: str,
        scope: str = None,
        scope_id: int = None,
        context: Dict[str, Any] = None,
    ) -> bool:
        """
        检查用户权限（支持ABAC）

        参数:
            user_id (int): 用户ID
            permission (str): 权限名称
            scope (str): 权限作用域
            scope_id (int): 作用域ID
            context (Dict[str, Any]): 上下文信息（用于ABAC）

        返回:
            bool: 是否有权限
        """
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有权限检查请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        start_time = time.time()

        try:
            # 第一步：使用混合缓存检查RBAC权限
            rbac_result = self.cache.get_permission(
                user_id, permission, "hybrid", scope, scope_id
            )

            # 如果RBAC检查失败，直接返回False
            if isinstance(rbac_result, bool) and not rbac_result:
                return False
            elif isinstance(rbac_result, set) and permission not in rbac_result:
                return False

            # 第二步：如果RBAC检查通过，进行ABAC策略检查
            if context is not None:
                try:
                    # 获取OPA策略管理器
                    opa_manager = get_opa_policy_manager()

                    # 构建用户信息
                    user_info = self._build_user_info(user_id, context)

                    # 构建资源信息
                    resource_info = self._build_resource_info(
                        permission, scope, scope_id, context
                    )

                    # 进行ABAC策略检查
                    abac_result = opa_manager.check_permission(
                        user=user_info,
                        resource=resource_info,
                        action=permission,
                        context=context,
                    )

                    # 如果ABAC检查失败，返回False
                    if not abac_result:
                        logger.debug(
                            f"ABAC策略检查失败: user_id={user_id}, permission={permission}"
                        )
                        return False

                except Exception as e:
                    logger.warning(
                        f"ABAC策略检查异常，回退到RBAC: user_id={user_id}, permission={permission}, error={e}"
                    )
                    # ABAC检查异常时，回退到RBAC结果

            # 记录性能指标
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            self.monitor.record_response_time(response_time, "permission_check")

            # 根据返回类型处理结果
            if isinstance(rbac_result, bool):
                return rbac_result
            elif isinstance(rbac_result, set):
                return permission in rbac_result
            else:
                return False

        except Exception as e:
            logger.error(
                f"权限检查失败: user_id={user_id}, permission={permission}, error={e}"
            )
            self.monitor.record_error_rate(1.0, "permission_check_error")
            return False

    def _build_user_info(self, user_id: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建用户信息用于ABAC策略检查

        Args:
            user_id: 用户ID
            context: 上下文信息

        Returns:
            Dict[str, Any]: 用户信息
        """
        # 基础用户信息
        user_info = {
            "id": user_id,
            "session_valid": True,  # 默认值，实际应从会话管理获取
            "disabled": False,  # 默认值，实际应从用户管理获取
            "roles": [],  # 将从数据库获取
            "ip_address": context.get("ip_address", "127.0.0.1"),
            "device_type": context.get("device_type", "desktop"),
            "device_authenticated": context.get("device_authenticated", True),
            "risk_level": context.get("risk_level", 1),
            "behavior_score": context.get("behavior_score", 100),
            "security_level": context.get("security_level", 1),
            "location": context.get("location", {"country": "CN", "city": "Beijing"}),
            "resource_permissions": context.get("resource_permissions", {}),
        }

        # 获取用户角色（这里简化处理，实际应从数据库获取）
        try:
            # 这里应该从数据库获取用户角色，暂时使用空列表
            user_info["roles"] = []
        except Exception as e:
            logger.warning(f"获取用户角色失败: user_id={user_id}, error={e}")

        return user_info

    def _build_resource_info(
        self,
        permission: str,
        scope: str = None,
        scope_id: int = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        构建资源信息用于ABAC策略检查

        Args:
            permission: 权限名称
            scope: 权限作用域
            scope_id: 作用域ID
            context: 上下文信息

        Returns:
            Dict[str, Any]: 资源信息
        """
        # 基础资源信息
        resource_info = {
            "id": (
                f"{permission}_{scope}_{scope_id}" if scope and scope_id else permission
            ),
            "type": permission,
            "exists": True,  # 默认值，实际应检查资源是否存在
            "max_risk_level": context.get("resource_max_risk_level", 5),
            "min_behavior_score": context.get("resource_min_behavior_score", 0),
            "required_security_level": context.get(
                "resource_required_security_level", 1
            ),
            "owner_id": context.get("resource_owner_id", None),
            "shared": context.get("resource_shared", False),
            "shared_with": context.get("resource_shared_with", []),
        }

        return resource_info

    def batch_check_permissions(
        self,
        user_ids: List[int],
        permission: str,
        scope: str = None,
        scope_id: int = None,
    ) -> Dict[int, bool]:
        """
        批量检查用户权限

        参数:
            user_ids (List[int]): 用户ID列表
            permission (str): 权限名称
            scope (str): 权限作用域
            scope_id (int): 作用域ID

        返回:
            Dict[int, bool]: 用户权限映射
        """
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有批量权限检查请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        start_time = time.time()

        try:
            # 使用批量权限查询
            permissions_map = self.cache.batch_get_permissions(
                user_ids, permission, "hybrid", scope, scope_id
            )

            # 转换为布尔结果
            results = {}
            for user_id, permissions in permissions_map.items():
                if isinstance(permissions, bool):
                    results[user_id] = permissions
                elif isinstance(permissions, set):
                    results[user_id] = permission in permissions
                else:
                    results[user_id] = False

            # 记录性能指标
            response_time = (time.time() - start_time) * 1000
            self.monitor.record_response_time(response_time, "batch_permission_check")

            return results

        except Exception as e:
            logger.error(
                f"批量权限检查失败: user_ids={user_ids}, permission={permission}, error={e}"
            )
            self.monitor.record_error_rate(1.0, "batch_permission_check_error")
            return {user_id: False for user_id in user_ids}

    def register_permission(
        self, name: str, group: str = None, description: str = None
    ) -> Dict:
        """注册权限"""
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有权限注册请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        return register_permission(name, group, description)

    def register_role(self, name: str, server_id: int = None) -> Dict:
        """注册角色"""
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有角色注册请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        return register_role(name, server_id)

    def assign_permissions_to_role(
        self,
        role_id: int,
        permission_ids: List[int],
        scope_type: str = None,
        scope_id: int = None,
    ) -> List[Dict]:
        """为角色分配权限"""
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有权限分配请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        return assign_permissions_to_role_v2(
            role_id, permission_ids, scope_type, scope_id
        )

    def assign_roles_to_user(
        self, user_id: int, role_ids: List[int], server_id: int = None
    ) -> List[Dict]:
        """为用户分配角色"""
        # 检查维护模式
        if self.resilience_controller.is_global_switch_enabled("maintenance_mode"):
            logger.warning("权限系统处于维护模式，拒绝所有角色分配请求")
            raise PermissionError("系统正在维护中，请稍后再试")

        return assign_roles_to_user_v2(user_id, role_ids, server_id)

    def invalidate_user_cache(self, user_id: int):
        """失效用户缓存"""
        self.cache.invalidate_user_permissions(user_id)

        # 记录实际事件，而不是推断的指标
        self.monitor.record_event(
            "cache_invalidation",
            {"type": "user", "user_id": user_id, "timestamp": time.time()},
        )

    def invalidate_role_cache(self, role_id: int):
        """失效角色缓存"""
        self.cache.invalidate_role_permissions(role_id)

        # 记录实际事件，而不是推断的指标
        self.monitor.record_event(
            "cache_invalidation",
            {"type": "role", "role_id": role_id, "timestamp": time.time()},
        )

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计 - 实时从子模块聚合数据"""
        cache_stats = self.cache.get_stats()
        registry_stats = get_permission_registry_stats()
        invalidation_stats = get_invalidation_statistics()
        health_status = self.monitor.get_health_status()

        return {
            "cache": cache_stats,
            "registry": registry_stats,
            "invalidation": invalidation_stats,
            "performance": self.cache.get_performance_analysis(),
            "health": {
                "overall_status": health_status.overall_status,
                "cache_status": health_status.cache_status,
                "performance_status": health_status.performance_status,
                "error_status": health_status.error_status,
                "alerts_count": len(
                    [a for a in health_status.alerts if not a.resolved]
                ),
            },
        }

    def get_optimization_suggestions(self) -> Dict[str, Any]:
        """获取优化建议"""
        return {
            "cache_tune": get_cache_auto_tune_suggestions(),
            "invalidation_strategy": get_cache_invalidation_strategy_analysis(),
            "batch_analysis": get_smart_batch_invalidation_analysis(),
            "monitor_alerts": self.monitor.get_performance_report(),
        }

    def process_maintenance(self):
        """执行维护任务"""
        # 处理延迟失效，获取实际处理的数量
        processed_count = process_delayed_invalidations()

        # 清理过期记录，获取实际清理的数量
        cleaned_count = cleanup_expired_invalidations()

        # 根据实际处理结果记录指标
        if processed_count > 0:
            self.monitor.record_value("maintenance_items_processed", processed_count)

        if cleaned_count > 0:
            self.monitor.record_value("maintenance_items_cleaned", cleaned_count)

        # 记录维护事件
        self.monitor.record_event(
            "maintenance_completed",
            {
                "processed_count": processed_count,
                "cleaned_count": cleaned_count,
                "timestamp": time.time(),
            },
        )

    # ==================== 缓存刷新方法 ====================

    def refresh_user_permissions(self, user_id: int, force: bool = False) -> Dict:
        """刷新用户权限缓存"""
        return refresh_user_permissions(user_id, force)

    def batch_refresh_user_permissions(
        self, user_ids: List[int], force: bool = False
    ) -> Dict:
        """批量刷新用户权限缓存"""
        return batch_refresh_user_permissions(user_ids, force)

    def refresh_role_permissions(self, role_id: int, force: bool = False) -> Dict:
        """刷新角色权限缓存"""
        return refresh_role_permissions(role_id, force)

    def warm_up_cache(
        self, user_ids: List[int] = None, role_ids: List[int] = None
    ) -> Dict:
        """预热缓存"""
        # 直接调用缓存实例的预热方法，避免递归
        try:
            result = self.cache.warm_up_cache(user_ids, role_ids)
            return {
                "success": True,
                "warmed_count": result,
                "message": f"成功预热 {result} 个权限查询",
            }
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return {"success": False, "error": str(e), "warmed_count": 0}

    def warm_up(self) -> Dict[str, Any]:
        """
        冷启动预热流程

        协调所有需要预热的子系统，确保应用启动后能够快速进入正常工作状态。
        包括：
        - 缓存预热
        - ML模型历史数据预加载
        - 系统状态初始化

        Returns:
            Dict[str, Any]: 预热结果统计
        """
        logger.info("开始执行冷启动预热流程...")
        start_time = time.time()
        results = {
            "cache_warmup": {},
            "ml_warmup": {},
            "system_warmup": {},
            "total_time": 0.0,
            "success": True,
            "errors": [],
        }

        try:
            # 1. 缓存预热
            logger.info("执行缓存预热...")
            cache_start = time.time()
            try:
                cache_result = self.warm_up_cache()
                results["cache_warmup"] = {
                    "success": True,
                    "time": time.time() - cache_start,
                    "details": cache_result,
                }
                logger.info(f"缓存预热完成，耗时: {time.time() - cache_start:.2f}秒")
            except Exception as e:
                error_msg = f"缓存预热失败: {e}"
                logger.error(error_msg)
                results["cache_warmup"] = {
                    "success": False,
                    "time": time.time() - cache_start,
                    "error": str(e),
                }
                results["errors"].append(error_msg)

            # 2. ML模型预热
            logger.info("执行ML模型预热...")
            ml_start = time.time()
            try:
                ml_result = self._warm_up_ml_models()
                ml_time = time.time() - ml_start
                results["ml_warmup"] = {
                    "success": True,
                    "time": ml_time,
                    "details": ml_result,
                }
                logger.info(f"ML模型预热完成，耗时: {ml_time:.2f}秒")
            except Exception as e:
                error_msg = f"ML模型预热失败: {e}"
                logger.error(error_msg)
                ml_time = time.time() - ml_start
                results["ml_warmup"] = {
                    "success": False,
                    "time": ml_time,
                    "error": str(e),
                }
                results["errors"].append(error_msg)

            # 3. 系统状态预热
            logger.info("执行系统状态预热...")
            system_start = time.time()
            try:
                system_result = self._warm_up_system_state()
                system_time = time.time() - system_start
                results["system_warmup"] = {
                    "success": True,
                    "time": system_time,
                    "details": system_result,
                }
                logger.info(f"系统状态预热完成，耗时: {system_time:.2f}秒")
            except Exception as e:
                error_msg = f"系统状态预热失败: {e}"
                logger.error(error_msg)
                system_time = time.time() - system_start
                results["system_warmup"] = {
                    "success": False,
                    "time": system_time,
                    "error": str(e),
                }
                results["errors"].append(error_msg)

            # 计算总耗时
            results["total_time"] = time.time() - start_time

            # 检查是否有错误
            if results["errors"]:
                results["success"] = False
                logger.warning(f"预热过程中发现 {len(results['errors'])} 个错误")
            else:
                logger.info(
                    f"冷启动预热流程完成，总耗时: {results['total_time']:.2f}秒"
                )

            return results

        except Exception as e:
            error_msg = f"预热流程执行失败: {e}"
            logger.error(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            results["total_time"] = time.time() - start_time
            return results

    def _warm_up_ml_models(self) -> Dict[str, Any]:
        """
        预热ML模型

        从持久化存储中预加载最近24小时的性能数据摘要，
        使ML模型能够更快地进入有效预测状态。

        Returns:
            Dict[str, Any]: ML预热结果
        """
        try:
            # 获取ML性能监控器
            ml_monitor = get_ml_performance_monitor()

            # 尝试从Redis加载历史性能数据
            redis_client = self.cache.get_redis_client()
            if redis_client:
                # 加载最近24小时的性能数据摘要
                historical_data = self._load_historical_performance_data(redis_client)

                if historical_data:
                    # 将历史数据喂给ML模型
                    for data_point in historical_data:
                        ml_monitor.feed_metrics(data_point)

                    logger.info(f"成功加载 {len(historical_data)} 个历史数据点")
                    return {
                        "historical_data_points": len(historical_data),
                        "data_time_range": "24h",
                        "model_ready": True,
                    }
                else:
                    logger.info("未找到历史性能数据，ML模型将使用默认初始化")
                    return {
                        "historical_data_points": 0,
                        "data_time_range": "none",
                        "model_ready": False,
                    }
            else:
                logger.warning("Redis不可用，跳过ML模型预热")
                return {
                    "historical_data_points": 0,
                    "data_time_range": "none",
                    "model_ready": False,
                    "reason": "redis_unavailable",
                }

        except Exception as e:
            logger.error(f"ML模型预热失败: {e}")
            return {
                "historical_data_points": 0,
                "data_time_range": "none",
                "model_ready": False,
                "error": str(e),
            }

    def _load_historical_performance_data(self, redis_client) -> List[Any]:
        """
        从Redis加载历史性能数据

        Args:
            redis_client: Redis客户端实例

        Returns:
            List[Any]: 历史性能数据列表
        """
        try:
            # 从Redis中获取最近24小时的性能数据摘要
            # 使用Redis的ZRANGEBYSCORE获取时间范围内的数据
            current_time = time.time()
            start_time = current_time - (24 * 3600)  # 24小时前

            # 获取性能数据键
            performance_keys = redis_client.keys("performance:metrics:*")

            historical_data = []
            for key in performance_keys:
                try:
                    # 获取数据的时间戳
                    data = redis_client.get(key)
                    if data:
                        # 解析性能数据
                        metrics_data = json.loads(data)
                        timestamp = metrics_data.get("timestamp", 0)

                        # 只加载最近24小时的数据
                        if timestamp >= start_time:
                            # 创建PerformanceMetrics对象
                            from .permission_ml import PerformanceMetrics

                            metrics = PerformanceMetrics(
                                timestamp=timestamp,
                                cache_hit_rate=metrics_data.get("cache_hit_rate", 0.0),
                                response_time=metrics_data.get("response_time", 0.0),
                                memory_usage=metrics_data.get("memory_usage", 0.0),
                                cpu_usage=metrics_data.get("cpu_usage", 0.0),
                                error_rate=metrics_data.get("error_rate", 0.0),
                                qps=metrics_data.get("qps", 0.0),
                                lock_timeout_rate=metrics_data.get(
                                    "lock_timeout_rate", 0.0
                                ),
                                connection_pool_usage=metrics_data.get(
                                    "connection_pool_usage", 0.0
                                ),
                            )
                            historical_data.append(metrics)

                except Exception as e:
                    logger.warning(f"解析性能数据失败 {key}: {e}")
                    continue

            # 按时间戳排序
            historical_data.sort(key=lambda x: x.timestamp)

            return historical_data

        except Exception as e:
            logger.error(f"加载历史性能数据失败: {e}")
            return []

    def _warm_up_system_state(self) -> Dict[str, Any]:
        """
        预热系统状态

        初始化系统状态，确保所有组件都处于正常工作状态。

        Returns:
            Dict[str, Any]: 系统状态预热结果
        """
        try:
            results = {
                "resilience_controller": False,
                "monitor_backend": False,
                "permission_monitor": False,
                "ml_monitor": False,
                "cache_system": False,
            }

            # 检查韧性控制器状态
            try:
                resilience_controller = get_resilience_controller()
                if resilience_controller:
                    results["resilience_controller"] = True
                    logger.debug("韧性控制器状态正常")
            except Exception as e:
                logger.warning(f"韧性控制器状态检查失败: {e}")

            # 检查监控后端状态
            try:
                from .monitor_backends import get_monitor_backend

                monitor_backend = get_monitor_backend()
                if monitor_backend:
                    results["monitor_backend"] = True
                    logger.debug("监控后端状态正常")
            except Exception as e:
                logger.warning(f"监控后端状态检查失败: {e}")

            # 检查权限监控器状态
            try:
                permission_monitor = get_permission_monitor()
                if permission_monitor:
                    results["permission_monitor"] = True
                    logger.debug("权限监控器状态正常")
            except Exception as e:
                logger.warning(f"权限监控器状态检查失败: {e}")

            # 检查ML监控器状态
            try:
                ml_monitor = get_ml_performance_monitor()
                if ml_monitor:
                    results["ml_monitor"] = True
                    logger.debug("ML监控器状态正常")
            except Exception as e:
                logger.warning(f"ML监控器状态检查失败: {e}")

            # 检查缓存系统状态
            try:
                if self.cache:
                    # 执行简单的缓存健康检查
                    try:
                        cache_health = self.cache.get_cache_health_check()
                        if cache_health.get("overall_status") == "healthy":
                            results["cache_system"] = True
                            logger.debug("缓存系统状态正常")
                    except AttributeError:
                        # 如果缓存对象没有get_cache_health_check方法，使用基本检查
                        if hasattr(self.cache, "get_stats"):
                            stats = self.cache.get_stats()
                            if stats:
                                results["cache_system"] = True
                                logger.debug("缓存系统状态正常（基本检查）")
            except Exception as e:
                logger.warning(f"缓存系统状态检查失败: {e}")

            # 计算成功状态
            success_count = sum(1 for status in results.values() if status)
            total_count = len(results)

            return {
                "component_status": results,
                "success_rate": success_count / total_count if total_count > 0 else 0,
                "healthy_components": success_count,
                "total_components": total_count,
            }

        except Exception as e:
            logger.error(f"系统状态预热失败: {e}")
            return {
                "component_status": {},
                "success_rate": 0,
                "healthy_components": 0,
                "total_components": 0,
                "error": str(e),
            }

    # ==================== 失效管理方法 ====================

    def add_delayed_invalidation(
        self, invalidation_type: str, target_id: int, delay_seconds: int = 300
    ) -> Dict:
        """添加延迟失效"""
        return add_delayed_invalidation(invalidation_type, target_id, delay_seconds)

    def execute_smart_batch_invalidation(
        self, invalidation_type: str, target_ids: List[int]
    ) -> Dict:
        """执行智能批量失效"""
        return execute_smart_batch_invalidation(invalidation_type, target_ids)

    def execute_global_smart_batch_invalidation(self) -> Dict:
        """执行全局智能批量失效"""
        return execute_global_smart_batch_invalidation()

    def trigger_background_invalidation_processing(self) -> Dict:
        """触发后台失效处理"""
        return trigger_background_invalidation_processing()

    def trigger_queue_monitoring(self) -> Dict:
        """触发队列监控"""
        return trigger_queue_monitoring()

    def trigger_cleanup_task(self, max_age: int = 3600) -> Dict:
        """触发清理任务"""
        return trigger_cleanup_task(max_age)

    def get_redis_connection_status(self) -> Dict:
        """获取Redis连接状态"""
        return get_redis_connection_status()

    # ==================== 监控方法 ====================

    def get_events_summary(self) -> Dict[str, Any]:
        """获取事件摘要"""
        return get_events_summary()

    def get_values_summary(self) -> Dict[str, Any]:
        """获取数值摘要"""
        return get_values_summary()

    def clear_alerts(self, level: str = None):
        """清除告警"""
        clear_alerts(level)

    # ==================== 韧性功能 ====================

    def get_resilience_stats(self) -> Dict[str, Any]:
        """获取韧性系统统计信息"""
        try:
            return {
                "circuit_breakers": get_circuit_breaker_state("permission_system"),
                "rate_limiters": get_rate_limit_status("permission_api"),
                "bulkheads": get_bulkhead_stats("permission_operations"),
                "instances_info": get_resilience_instances_info(),
                "all_configs": get_all_resilience_configs(),
            }
        except Exception as e:
            logger.error(f"获取韧性统计信息失败: {e}")
            return {}

    def configure_circuit_breaker(self, name: str, **kwargs) -> bool:
        """配置熔断器"""
        try:
            return set_circuit_breaker_config(name, **kwargs)
        except Exception as e:
            logger.error(f"配置熔断器失败: {e}")
            return False

    def configure_rate_limiter(self, name: str, **kwargs) -> bool:
        """配置限流器"""
        try:
            return set_rate_limit_config(name, **kwargs)
        except Exception as e:
            logger.error(f"配置限流器失败: {e}")
            return False

    def configure_bulkhead(self, name: str, **kwargs) -> bool:
        """配置舱壁隔离器"""
        try:
            return set_bulkhead_config(name, **kwargs)
        except Exception as e:
            logger.error(f"配置舱壁隔离器失败: {e}")
            return False

    def clear_resilience_instances(self):
        """清空韧性组件注册表"""
        try:
            clear_resilience_instances()
            logger.info("已清空韧性组件注册表")
        except Exception as e:
            logger.error(f"清空韧性组件注册表失败: {e}")

    # 添加获取维护模式状态的方法
    def is_maintenance_mode_enabled(self) -> bool:
        """
        检查维护模式是否开启

        返回:
            bool: True表示维护模式已开启，False表示正常模式
        """
        try:
            return self.resilience_controller.is_global_switch_enabled(
                "maintenance_mode"
            )
        except Exception as e:
            logger.error(f"检查维护模式状态失败: {e}")
            return False

    # 添加设置维护模式状态的方法
    def set_maintenance_mode(self, enabled: bool) -> bool:
        """
        设置维护模式状态

        参数:
            enabled (bool): True表示开启维护模式，False表示关闭维护模式

        返回:
            bool: 操作是否成功
        """
        try:
            success = self.resilience_controller.set_global_switch(
                "maintenance_mode", enabled
            )

            if success:
                status = "开启" if enabled else "关闭"
                logger.warning(f"权限系统维护模式已{status}")

                # 记录事件
                self.monitor.record_event(
                    "maintenance_mode_change",
                    {
                        "enabled": enabled,
                        "timestamp": time.time(),
                        "changed_by": "system",  # 可扩展记录操作人
                    },
                )

            return success
        except Exception as e:
            logger.error(f"设置维护模式状态失败: {e}")
            return False


# 全局权限系统实例
_permission_system = None


def get_permission_system() -> PermissionSystem:
    """获取权限系统实例"""
    global _permission_system
    if _permission_system is None:
        _permission_system = PermissionSystem()
    return _permission_system


# 便捷函数 - 使用不同的函数名避免命名冲突
def check_permission(
    user_id: int,
    permission: str,
    scope: str = None,
    scope_id: int = None,
    context: Dict[str, Any] = None,
) -> bool:
    """检查权限 - 便捷函数（支持ABAC）"""
    return get_permission_system().check_permission(
        user_id, permission, scope, scope_id, context
    )


def batch_check_permissions(
    user_ids: List[int], permission: str, scope: str = None, scope_id: int = None
) -> Dict[int, bool]:
    """批量检查权限 - 便捷函数"""
    return get_permission_system().batch_check_permissions(
        user_ids, permission, scope, scope_id
    )


def register_permission(name: str, group: str = None, description: str = None) -> Dict:
    """注册权限 - 便捷函数"""
    return get_permission_system().register_permission(name, group, description)


def register_role(name: str, server_id: int = None) -> Dict:
    """注册角色 - 便捷函数"""
    return get_permission_system().register_role(name, server_id)


def assign_permissions_to_role(
    role_id: int,
    permission_ids: List[int],
    scope_type: str = None,
    scope_id: int = None,
) -> List[Dict]:
    """为角色分配权限 - 便捷函数"""
    return get_permission_system().assign_permissions_to_role(
        role_id, permission_ids, scope_type, scope_id
    )


def assign_roles_to_user(
    user_id: int, role_ids: List[int], server_id: int = None
) -> List[Dict]:
    """为用户分配角色 - 便捷函数"""
    return get_permission_system().assign_roles_to_user(user_id, role_ids, server_id)


def invalidate_user_cache(user_id: int):
    """失效用户缓存 - 便捷函数"""
    get_permission_system().invalidate_user_cache(user_id)


def invalidate_role_cache(role_id: int):
    """失效角色缓存 - 便捷函数"""
    get_permission_system().invalidate_role_cache(role_id)


def get_system_stats() -> Dict[str, Any]:
    """获取系统统计 - 便捷函数"""
    return get_permission_system().get_system_stats()


def get_optimization_suggestions() -> Dict[str, Any]:
    """获取优化建议 - 便捷函数"""
    return get_permission_system().get_optimization_suggestions()


def process_maintenance():
    """执行维护任务 - 便捷函数"""
    get_permission_system().process_maintenance()


# ==================== 缓存刷新便捷函数 ====================


def refresh_user_permissions(user_id: int, force: bool = False) -> Dict:
    """刷新用户权限缓存 - 便捷函数"""
    return get_permission_system().refresh_user_permissions(user_id, force)


def batch_refresh_user_permissions(user_ids: List[int], force: bool = False) -> Dict:
    """批量刷新用户权限缓存 - 便捷函数"""
    return get_permission_system().batch_refresh_user_permissions(user_ids, force)


def refresh_role_permissions(role_id: int, force: bool = False) -> Dict:
    """刷新角色权限缓存 - 便捷函数"""
    return get_permission_system().refresh_role_permissions(role_id, force)


def warm_up_cache(user_ids: List[int] = None, role_ids: List[int] = None) -> Dict:
    """预热缓存 - 便捷函数"""
    return get_permission_system().warm_up_cache(user_ids, role_ids)


# ==================== 失效管理便捷函数 ====================


def add_delayed_invalidation(
    invalidation_type: str, target_id: int, delay_seconds: int = 300
) -> Dict:
    """添加延迟失效 - 便捷函数"""
    return get_permission_system().add_delayed_invalidation(
        invalidation_type, target_id, delay_seconds
    )


def execute_smart_batch_invalidation(
    invalidation_type: str, target_ids: List[int]
) -> Dict:
    """执行智能批量失效 - 便捷函数"""
    return get_permission_system().execute_smart_batch_invalidation(
        invalidation_type, target_ids
    )


def execute_global_smart_batch_invalidation() -> Dict:
    """执行全局智能批量失效 - 便捷函数"""
    return get_permission_system().execute_global_smart_batch_invalidation()


def trigger_background_invalidation_processing() -> Dict:
    """触发后台失效处理 - 便捷函数"""
    return get_permission_system().trigger_background_invalidation_processing()


def trigger_queue_monitoring() -> Dict:
    """触发队列监控 - 便捷函数"""
    return get_permission_system().trigger_queue_monitoring()


def trigger_cleanup_task(max_age: int = 3600) -> Dict:
    """触发清理任务 - 便捷函数"""
    return get_permission_system().trigger_cleanup_task(max_age)


def get_redis_connection_status() -> Dict:
    """获取Redis连接状态 - 便捷函数"""
    return get_permission_system().get_redis_connection_status()


# ==================== 监控便捷函数 ====================


def get_events_summary() -> Dict[str, Any]:
    """获取事件摘要 - 便捷函数"""
    return get_permission_system().get_events_summary()


def get_values_summary() -> Dict[str, Any]:
    """获取数值摘要 - 便捷函数"""
    return get_permission_system().get_values_summary()


def clear_alerts(level: str = None):
    """清除告警 - 便捷函数"""
    get_permission_system().clear_alerts(level)


# ==================== 韧性功能便捷函数 ====================


def get_resilience_stats() -> Dict[str, Any]:
    """获取韧性系统统计信息 - 便捷函数"""
    return get_permission_system().get_resilience_stats()


def configure_circuit_breaker(name: str, **kwargs) -> bool:
    """配置熔断器 - 便捷函数"""
    return get_permission_system().configure_circuit_breaker(name, **kwargs)


def configure_rate_limiter(name: str, **kwargs) -> bool:
    """配置限流器 - 便捷函数"""
    return get_permission_system().configure_rate_limiter(name, **kwargs)


def configure_bulkhead(name: str, **kwargs) -> bool:
    """配置舱壁隔离器 - 便捷函数"""
    return get_permission_system().configure_bulkhead(name, **kwargs)


def clear_resilience_instances():
    """清空韧性组件注册表 - 便捷函数"""
    get_permission_system().clear_resilience_instances()


def is_maintenance_mode_enabled() -> bool:
    """检查维护模式是否开启的便捷函数"""
    return get_permission_system().is_maintenance_mode_enabled()


def set_maintenance_mode(enabled: bool) -> bool:
    """设置维护模式状态的便捷函数"""
    return get_permission_system().set_maintenance_mode(enabled)


# 导出所有装饰器
__all__ = [
    "require_permission",
    "require_permission_v2",
    "require_permissions_v2",
    "require_permission_with_expression_v2",
    "check_permission",
    "batch_check_permissions",
    "register_permission",
    "register_role",
    "assign_permissions_to_role",
    "assign_roles_to_user",
    "invalidate_user_cache",
    "invalidate_role_cache",
    "get_system_stats",
    "get_optimization_suggestions",
    "process_maintenance",
    # 缓存刷新函数
    "refresh_user_permissions",
    "batch_refresh_user_permissions",
    "refresh_role_permissions",
    "warm_up_cache",
    # 失效管理函数
    "add_delayed_invalidation",
    "execute_smart_batch_invalidation",
    "execute_global_smart_batch_invalidation",
    "trigger_background_invalidation_processing",
    "trigger_queue_monitoring",
    "trigger_cleanup_task",
    "get_redis_connection_status",
    # 监控函数
    "get_events_summary",
    "get_values_summary",
    "clear_alerts",
    # 韧性功能
    "circuit_breaker",
    "rate_limit",
    "degradable",
    "bulkhead",
    "get_resilience_stats",
    "configure_circuit_breaker",
    "configure_rate_limiter",
    "configure_bulkhead",
    "clear_resilience_instances",
    "get_circuit_breaker_state",
    "get_rate_limit_status",
    "get_bulkhead_stats",
    "set_circuit_breaker_config",
    "set_rate_limit_config",
    "set_degradation_config",
    "set_bulkhead_config",
    "get_all_resilience_configs",
    # 配置类和枚举
    "CircuitBreakerConfig",
    "RateLimitConfig",
    "DegradationConfig",
    "BulkheadConfig",
    "CircuitBreakerState",
    "RateLimitType",
    "DegradationLevel",
    "IsolationStrategy",
    "ResourceType",
    "MultiDimensionalKey",
    # 类和实例
    "PermissionSystem",
    "get_permission_system",
]
