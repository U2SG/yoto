"""
权限失效模块
管理权限失效缓存的生命周期
包含缓存失效逻辑
"""

import time
import logging
import json
import uuid
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict

# 导入缓存管理器
try:
    from .hybrid_permission_cache import get_hybrid_cache
except ImportError:
    get_hybrid_cache = None

logger = logging.getLogger(__name__)

# Redis键名常量
DELAYED_INVALIDATION_QUEUE = "delayed_invalidation_queue"  # 现在是ZSET
INVALIDATION_STATS_KEY = "invalidation_stats"
INVALIDATION_STATS_LOCK = "invalidation_stats_lock"
# 反向索引键名
REASON_INDEX_PREFIX = "reason_index:"
USER_INDEX_PREFIX = "user_index:"
SERVER_INDEX_PREFIX = "server_index:"
PATTERN_INDEX_PREFIX = "pattern_index:"
# 速率统计键名
RATE_STATS_PREFIX = "rate_stats:"
IN_RATE_PREFIX = "in_rate:"
OUT_RATE_PREFIX = "out_rate:"

# 任务触发器注册表（依赖注入）
_task_triggers = {
    "process_delayed_invalidations": None,
    "monitor_invalidation_queue": None,
    "cleanup_expired_invalidations": None,
}


def register_task_triggers(process_func=None, monitor_func=None, cleanup_func=None):
    """
    注册任务触发器（依赖注入）

    参数:
        process_func: 处理延迟失效的任务函数
        monitor_func: 监控队列的任务函数
        cleanup_func: 清理过期记录的任务函数
    """
    global _task_triggers

    if process_func is not None:
        _task_triggers["process_delayed_invalidations"] = process_func
    if monitor_func is not None:
        _task_triggers["monitor_invalidation_queue"] = monitor_func
    if cleanup_func is not None:
        _task_triggers["cleanup_expired_invalidations"] = cleanup_func

    logger.info("任务触发器已注册")


def get_registered_triggers() -> Dict[str, Any]:
    """
    获取已注册的任务触发器

    返回:
        Dict[str, Any]: 已注册的触发器信息
    """
    return {
        "process_delayed_invalidations": _task_triggers["process_delayed_invalidations"]
        is not None,
        "monitor_invalidation_queue": _task_triggers["monitor_invalidation_queue"]
        is not None,
        "cleanup_expired_invalidations": _task_triggers["cleanup_expired_invalidations"]
        is not None,
    }


def _get_cache_manager():
    """
    获取缓存管理器实例

    返回:
        HybridPermissionCache实例或None
    """
    if get_hybrid_cache is None:
        logger.warning("无法导入缓存管理器")
        return None

    try:
        return get_hybrid_cache()
    except Exception as e:
        logger.warning(f"获取缓存管理器失败: {e}")
        return None


def _get_redis_config():
    """
    获取Redis配置

    返回:
        Dict: Redis连接配置
    """
    # 尝试从应用配置获取
    try:
        from flask import current_app

        if current_app:
            config = current_app.config
            return {
                "host": config.get("REDIS_HOST", "localhost"),
                "port": config.get("REDIS_PORT", 6379),
                "db": config.get("REDIS_DB", 0),
                "password": config.get("REDIS_PASSWORD", None),
                "decode_responses": False,
                "socket_connect_timeout": config.get("REDIS_CONNECT_TIMEOUT", 5),
                "socket_timeout": config.get("REDIS_SOCKET_TIMEOUT", 5),
            }
    except Exception:
        pass

    # 尝试从config模块获取
    try:
        from config import Config

        return {
            "host": getattr(Config, "REDIS_HOST", "localhost"),
            "port": getattr(Config, "REDIS_PORT", 6379),
            "db": getattr(Config, "REDIS_DB", 0),
            "password": getattr(Config, "REDIS_PASSWORD", None),
            "decode_responses": False,
            "socket_connect_timeout": getattr(Config, "REDIS_CONNECT_TIMEOUT", 5),
            "socket_timeout": getattr(Config, "REDIS_SOCKET_TIMEOUT", 5),
        }
    except ImportError:
        pass

    # 默认配置
    return {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "decode_responses": False,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    }


def _check_redis_connection(redis_client) -> bool:
    """
    检查Redis连接健康状态

    参数:
        redis_client: Redis客户端实例

    返回:
        bool: 连接是否健康
    """
    try:
        # 测试连接
        redis_client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis连接健康检查失败: {e}")
        return False


def _get_redis_client():
    """
    获取Redis客户端（优先使用缓存模块，备选独立连接）

    返回:
        Redis客户端实例或None
    """
    # 方案1：优先使用缓存模块的Redis连接
    try:
        cache_manager = _get_cache_manager()
        if cache_manager:
            redis_client = cache_manager.get_redis_client()
            if redis_client and _check_redis_connection(redis_client):
                logger.debug("使用缓存模块的Redis连接")
                return redis_client
            else:
                logger.warning("缓存模块Redis连接不可用")
    except Exception as e:
        logger.warning(f"获取缓存模块Redis连接失败: {e}")

    # 方案2：备选独立Redis连接 - 支持集群感知
    try:
        import redis

        config = _get_redis_config()

        # 优先尝试Redis集群连接
        try:
            # 确保节点配置格式正确
            startup_nodes = [
                {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                }
            ]

            # 尝试从Flask配置获取额外的集群节点
            try:
                from flask import current_app

                redis_config = current_app.config.get("REDIS_CONFIG", {})
                additional_nodes = redis_config.get("additional_nodes", [])
                startup_nodes.extend(additional_nodes)
            except:
                pass

            # 过滤并确保节点配置格式正确
            valid_startup_nodes = []
            for node in startup_nodes:
                if isinstance(node, dict) and "host" in node and "port" in node:
                    valid_startup_nodes.append(
                        {"host": node["host"], "port": node["port"]}
                    )

            if len(valid_startup_nodes) > 1:
                # 如果有多个节点，尝试集群模式
                try:
                    redis_client = redis.RedisCluster(
                        startup_nodes=valid_startup_nodes,
                        decode_responses=config.get("decode_responses", True),
                        skip_full_coverage_check=True,
                    )
                    if _check_redis_connection(redis_client):
                        logger.debug("使用Redis集群连接")
                        return redis_client
                except Exception as cluster_error:
                    logger.warning(
                        f"Redis集群连接失败，尝试单节点模式: {cluster_error}"
                    )

            # 降级到单节点Redis
            redis_client = redis.Redis(**config)
            if _check_redis_connection(redis_client):
                logger.debug("使用Redis单节点连接")
                return redis_client
            else:
                logger.error("独立Redis连接健康检查失败")
        except Exception as e:
            logger.error(f"Redis连接创建失败: {e}")
    except Exception as e:
        logger.error(f"获取独立Redis连接失败: {e}")

    return None


def _get_stats_lock():
    """
    获取统计锁的Redis键

    返回:
        str: 锁的键名
    """
    return f"{INVALIDATION_STATS_LOCK}:{int(time.time() // 60)}"  # 每分钟一个锁


def add_delayed_invalidation(
    cache_key: str, cache_level: str = "l1", reason: str = None
):
    """
    添加延迟失效到Redis队列（使用Sorted Set）

    参数:
        cache_key (str): 缓存键
        cache_level (str): 缓存级别
        reason (str): 失效原因
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.error("Redis客户端不可用，无法添加延迟失效")
        return False

    try:
        # 创建失效任务
        current_time = time.time()
        invalidation_task = {
            "cache_key": cache_key,
            "cache_level": cache_level,
            "reason": reason,
            "timestamp": current_time,
            "processed": False,
        }

        # 将任务添加到Redis Sorted Set队列
        task_json = json.dumps(invalidation_task, ensure_ascii=False)
        redis_client.zadd(DELAYED_INVALIDATION_QUEUE, {task_json: current_time})

        # 更新反向索引
        _update_reverse_indexes(redis_client, cache_key, reason)

        # 更新统计信息
        _update_stats("delayed_invalidations", 1)

        # 记录入队速率
        _record_rate_stats(redis_client, "in", 1)

        logger.debug(f"添加延迟失效到Redis: {cache_key}, 原因: {reason}")
        return True

    except Exception as e:
        logger.error(f"添加延迟失效失败: {e}")
        return False


def _update_stats(stat_type: str, increment: int = 1):
    """
    更新Redis中的统计信息

    参数:
        stat_type (str): 统计类型
        increment (int): 增量
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return

    try:
        # 使用Redis HINCRBY原子操作更新统计
        redis_client.hincrby(INVALIDATION_STATS_KEY, stat_type, increment)
        # 设置过期时间，避免统计信息永久存在
        redis_client.expire(INVALIDATION_STATS_KEY, 86400)  # 24小时过期
    except Exception as e:
        logger.error(f"更新统计信息失败: {e}")


def _get_stats():
    """
    从Redis获取统计信息

    返回:
        Dict[str, int]: 统计信息
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return {
            "total_invalidations": 0,
            "delayed_invalidations": 0,
            "immediate_invalidations": 0,
            "batch_invalidations": 0,
        }

    try:
        stats = redis_client.hgetall(INVALIDATION_STATS_KEY)
        return {
            "total_invalidations": int(stats.get(b"total_invalidations", 0)),
            "delayed_invalidations": int(stats.get(b"delayed_invalidations", 0)),
            "immediate_invalidations": int(stats.get(b"immediate_invalidations", 0)),
            "batch_invalidations": int(stats.get(b"batch_invalidations", 0)),
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return {
            "total_invalidations": 0,
            "delayed_invalidations": 0,
            "immediate_invalidations": 0,
            "batch_invalidations": 0,
        }


def get_delayed_invalidation_stats() -> Dict[str, Any]:
    """
    获取延迟失效统计（基于Sorted Set）

    返回:
        Dict[str, Any]: 延迟失效统计
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return {
            "pending_count": 0,
            "processed_count": 0,
            "total_count": 0,
            "stats": _get_stats(),
        }

    try:
        # 获取队列长度（Sorted Set的成员数量）
        queue_length = redis_client.zcard(DELAYED_INVALIDATION_QUEUE)

        # 获取统计信息
        stats = _get_stats()

        return {
            "pending_count": queue_length,
            "processed_count": stats["delayed_invalidations"] - queue_length,
            "total_count": stats["delayed_invalidations"],
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"获取延迟失效统计失败: {e}")
        return {
            "pending_count": 0,
            "processed_count": 0,
            "total_count": 0,
            "stats": _get_stats(),
        }


def get_invalidation_statistics() -> Dict[str, Any]:
    """
    获取失效统计

    返回:
        Dict[str, Any]: 失效统计
    """
    stats = _get_stats()
    return {
        "total_invalidations": stats["total_invalidations"],
        "delayed_invalidations": stats["delayed_invalidations"],
        "immediate_invalidations": stats["immediate_invalidations"],
        "batch_invalidations": stats["batch_invalidations"],
        "delayed_stats": get_delayed_invalidation_stats(),
    }


def _analyze_delayed_queue(
    max_tasks: int = 100, current_time: float = None
) -> Dict[str, Any]:
    """
    通用延迟队列分析函数（基于Sorted Set）

    参数:
        max_tasks (int): 最大分析任务数
        current_time (float): 当前时间戳，如果为None则使用当前时间

    返回:
        Dict[str, Any]: 分析结果
    """
    if current_time is None:
        current_time = time.time()

    redis_client = _get_redis_client()
    if not redis_client:
        return {
            "tasks": [],
            "key_patterns": {},
            "reasons": {},
            "cache_levels": {},
            "task_ages": [],
            "user_activity": {},
            "server_activity": {},
            "total_tasks": 0,
            "valid_tasks": 0,
        }

    try:
        # 获取队列长度
        queue_length = redis_client.zcard(DELAYED_INVALIDATION_QUEUE)
        if queue_length == 0:
            return {
                "tasks": [],
                "key_patterns": {},
                "reasons": {},
                "cache_levels": {},
                "task_ages": [],
                "user_activity": {},
                "server_activity": {},
                "total_tasks": 0,
                "valid_tasks": 0,
            }

        # 分析的任务数量
        analyze_count = min(max_tasks, queue_length)

        # 获取任务进行分析（按时间戳排序，从最老的开始）
        tasks = redis_client.zrange(
            DELAYED_INVALIDATION_QUEUE, 0, analyze_count - 1, withscores=True
        )

        # 分析结果
        key_patterns = defaultdict(int)
        reasons = defaultdict(int)
        cache_levels = defaultdict(int)
        task_ages = []
        user_activity = defaultdict(int)
        server_activity = defaultdict(int)
        valid_tasks = []

        for task_json, score in tasks:
            try:
                task = json.loads(task_json)
                if not task.get("processed", False):
                    valid_tasks.append(task)

                    # 分析键模式
                    key_parts = task["cache_key"].split(":")
                    if len(key_parts) >= 2:
                        pattern = f"{key_parts[0]}:{key_parts[1]}:*"
                        key_patterns[pattern] += 1

                    # 分析失效原因
                    if task.get("reason"):
                        reasons[task["reason"]] += 1

                    # 分析缓存级别分布
                    cache_levels[task.get("cache_level", "unknown")] += 1

                    # 分析任务年龄
                    task_age = current_time - task.get("timestamp", current_time)
                    task_ages.append(task_age)

                    # 分析用户活动模式
                    if len(key_parts) >= 3 and key_parts[0] == "perm":
                        try:
                            user_id = int(key_parts[1])
                            user_activity[user_id] += 1
                        except (ValueError, IndexError):
                            pass

                    # 分析服务器活动模式
                    if len(key_parts) >= 4 and key_parts[0] == "perm":
                        try:
                            server_id = int(key_parts[2])
                            server_activity[server_id] += 1
                        except (ValueError, IndexError):
                            pass

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析任务失败: {e}")
                continue

        return {
            "tasks": valid_tasks,
            "key_patterns": dict(key_patterns),
            "reasons": dict(reasons),
            "cache_levels": dict(cache_levels),
            "task_ages": task_ages,
            "user_activity": dict(user_activity),
            "server_activity": dict(server_activity),
            "total_tasks": queue_length,
            "valid_tasks": len(valid_tasks),
        }

    except Exception as e:
        logger.error(f"分析延迟队列失败: {e}")
        return {
            "tasks": [],
            "key_patterns": {},
            "reasons": {},
            "cache_levels": {},
            "task_ages": [],
            "user_activity": {},
            "server_activity": {},
            "total_tasks": 0,
            "valid_tasks": 0,
        }


def get_smart_batch_invalidation_analysis() -> Dict[str, Any]:
    """
    获取智能批量失效分析（基于Redis全局数据）

    返回:
        Dict[str, Any]: 批量失效分析
    """
    # 使用通用分析函数
    analysis_result = _analyze_delayed_queue(max_tasks=100)

    if analysis_result["valid_tasks"] == 0:
        return {
            "pending_count": 0,
            "key_patterns": {},
            "reasons": {},
            "recommendations": [],
            "global_analysis": {
                "queue_health": "excellent",
                "total_tasks": 0,
                "avg_task_age": 0,
            },
            "performance_metrics": {"processing_rate": 0, "queue_growth_rate": 0},
        }

    # 计算全局分析指标
    task_ages = analysis_result["task_ages"]
    avg_task_age = sum(task_ages) / len(task_ages) if task_ages else 0
    max_task_age = max(task_ages) if task_ages else 0

    # 队列健康状态分析
    queue_length = analysis_result["total_tasks"]
    queue_health = "excellent"
    if queue_length > 1000:
        queue_health = "critical"
    elif queue_length > 500:
        queue_health = "warning"
    elif queue_length > 100:
        queue_health = "attention"

    # 性能指标分析
    performance_metrics = {
        "avg_task_age": avg_task_age,
        "max_task_age": max_task_age,
        "queue_length": queue_length,
        "processing_rate": _calculate_processing_rate(),
        "queue_growth_rate": _calculate_queue_growth_rate(),
    }

    # 推荐批量失效策略
    recommendations = []

    # 按模式分组
    for pattern, count in analysis_result["key_patterns"].items():
        if count >= 5:  # 如果同一模式有5个以上待失效项
            recommendations.append(
                {
                    "type": "pattern_batch",
                    "pattern": pattern,
                    "count": count,
                    "priority": "high" if count >= 20 else "medium",
                    "action": f"批量失效模式 {pattern} 的 {count} 个缓存项",
                    "estimated_impact": count * 0.1,  # 估算影响
                }
            )

    # 按原因分组
    for reason, count in analysis_result["reasons"].items():
        if count >= 3:  # 如果同一原因有3个以上待失效项
            recommendations.append(
                {
                    "type": "reason_batch",
                    "reason": reason,
                    "count": count,
                    "priority": "high" if count >= 15 else "medium",
                    "action": f"批量失效原因 {reason} 的 {count} 个缓存项",
                    "estimated_impact": count * 0.1,
                }
            )

    # 按用户活动分组
    for user_id, count in analysis_result["user_activity"].items():
        if count >= 10:  # 如果同一用户有10个以上待失效项
            recommendations.append(
                {
                    "type": "user_batch",
                    "user_id": user_id,
                    "count": count,
                    "priority": "high" if count >= 50 else "medium",
                    "action": f"批量失效用户 {user_id} 的 {count} 个缓存项",
                    "estimated_impact": count * 0.05,
                }
            )

    # 按服务器活动分组
    for server_id, count in analysis_result["server_activity"].items():
        if count >= 5:  # 如果同一服务器有5个以上待失效项
            recommendations.append(
                {
                    "type": "server_batch",
                    "server_id": server_id,
                    "count": count,
                    "priority": "high" if count >= 20 else "medium",
                    "action": f"批量失效服务器 {server_id} 的 {count} 个缓存项",
                    "estimated_impact": count * 0.08,
                }
            )

    # 全局分析结果
    global_analysis = {
        "queue_health": queue_health,
        "total_tasks": queue_length,
        "avg_task_age": avg_task_age,
        "max_task_age": max_task_age,
        "cache_level_distribution": analysis_result["cache_levels"],
        "top_users": dict(
            sorted(
                analysis_result["user_activity"].items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        ),
        "top_servers": dict(
            sorted(
                analysis_result["server_activity"].items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        ),
        "urgent_actions": _identify_urgent_actions(task_ages, queue_length),
    }

    return {
        "pending_count": queue_length,
        "key_patterns": analysis_result["key_patterns"],
        "reasons": analysis_result["reasons"],
        "recommendations": recommendations,
        "global_analysis": global_analysis,
        "performance_metrics": performance_metrics,
    }


def _calculate_processing_rate() -> float:
    """
    计算处理速率（基于真实数据）

    返回:
        float: 每秒处理的任务数
    """
    try:
        redis_client = _get_redis_client()
        if not redis_client:
            return 0.0

        # 获取最近5分钟的出队统计数据
        out_stats = _get_rate_stats(redis_client, "out", 5)

        if not out_stats:
            return 0.0

        # 计算总处理数和总时间
        total_processed = sum(stat["count"] for stat in out_stats)
        if len(out_stats) < 2:
            return 0.0

        # 计算时间跨度（秒）
        time_span = out_stats[0]["timestamp"] - out_stats[-1]["timestamp"]
        if time_span <= 0:
            return 0.0

        # 计算平均处理速率（每秒）
        processing_rate = total_processed / time_span

        return processing_rate

    except Exception as e:
        logger.error(f"计算处理速率失败: {e}")
        return 0.0


def _calculate_queue_growth_rate() -> float:
    """
    计算队列增长率（基于真实数据）

    返回:
        float: 每秒新增的任务数
    """
    try:
        redis_client = _get_redis_client()
        if not redis_client:
            return 0.0

        # 获取最近5分钟的入队统计数据
        in_stats = _get_rate_stats(redis_client, "in", 5)

        if not in_stats:
            return 0.0

        # 计算总入队数和总时间
        total_in = sum(stat["count"] for stat in in_stats)
        if len(in_stats) < 2:
            return 0.0

        # 计算时间跨度（秒）
        time_span = in_stats[0]["timestamp"] - in_stats[-1]["timestamp"]
        if time_span <= 0:
            return 0.0

        # 计算平均增长率（每秒）
        growth_rate = total_in / time_span

        return growth_rate

    except Exception as e:
        logger.error(f"计算队列增长率失败: {e}")
        return 0.0


def _identify_urgent_actions(
    task_ages: List[float], queue_length: int
) -> List[Dict[str, Any]]:
    """
    识别紧急操作

    参数:
        task_ages (List[float]): 任务年龄列表
        queue_length (int): 队列长度

    返回:
        List[Dict[str, Any]]: 紧急操作列表
    """
    urgent_actions = []

    # 检查是否有超时任务
    timeout_tasks = [age for age in task_ages if age > 3600]  # 超过1小时
    if timeout_tasks:
        urgent_actions.append(
            {
                "type": "timeout_cleanup",
                "count": len(timeout_tasks),
                "message": f"发现 {len(timeout_tasks)} 个超时任务需要立即清理",
                "priority": "critical",
            }
        )

    # 检查队列积压
    if queue_length > 1000:
        urgent_actions.append(
            {
                "type": "queue_overflow",
                "count": queue_length,
                "message": f"队列积压严重，建议增加处理worker",
                "priority": "critical",
            }
        )
    elif queue_length > 500:
        urgent_actions.append(
            {
                "type": "queue_warning",
                "count": queue_length,
                "message": f"队列积压，建议优化处理策略",
                "priority": "warning",
            }
        )

    # 检查处理速率
    processing_rate = _calculate_processing_rate()
    growth_rate = _calculate_queue_growth_rate()
    if growth_rate > processing_rate:
        urgent_actions.append(
            {
                "type": "rate_mismatch",
                "processing_rate": processing_rate,
                "growth_rate": growth_rate,
                "message": "队列增长率超过处理速率，需要扩容",
                "priority": "warning",
            }
        )

    return urgent_actions


def execute_smart_batch_invalidation(
    keys: List[str], strategy: str = "auto"
) -> Dict[str, Any]:
    """
    执行智能批量失效

    参数:
        keys (List[str]): 要失效的键列表
        strategy (str): 失效策略

    返回:
        Dict[str, Any]: 执行结果
    """
    start_time = time.time()
    results = {
        "strategy": strategy,
        "keys_count": len(keys),
        "success_count": 0,
        "failed_count": 0,
        "execution_time": 0,
    }

    try:
        cache_manager = _get_cache_manager()
        if not cache_manager:
            results["failed_count"] = len(keys)
            results["execution_time"] = time.time() - start_time
            return results

        # 使用缓存管理器的公共API执行批量失效
        invalidation_results = cache_manager.invalidate_keys(keys, cache_level="all")

        results["success_count"] = (
            invalidation_results["l1_invalidated"]
            + invalidation_results["l2_invalidated"]
        )
        results["failed_count"] = len(invalidation_results["failed_keys"])
        results["execution_time"] = invalidation_results["execution_time"]

        _update_stats("batch_invalidations", 1)
        _update_stats("total_invalidations", len(keys))

        logger.info(
            f"智能批量失效完成: {results['success_count']} 成功, {results['failed_count']} 失败"
        )

    except Exception as e:
        logger.error(f"智能批量失效失败: {e}")
        results["failed_count"] = len(keys)
        results["execution_time"] = time.time() - start_time

    return results


def trigger_background_invalidation_processing(
    batch_size: int = 100, max_execution_time: int = 300
):
    """
    触发后台失效处理任务（使用依赖注入）

    参数:
        batch_size (int): 批处理大小
        max_execution_time (int): 最大执行时间（秒）

    返回:
        Dict[str, Any]: 任务触发结果
    """
    try:
        # 检查是否已注册任务触发器
        if _task_triggers["process_delayed_invalidations"] is None:
            return {
                "status": "not_registered",
                "error": "处理延迟失效任务未注册，请先调用register_task_triggers",
            }

        # 使用注册的任务触发器
        task_func = _task_triggers["process_delayed_invalidations"]
        task = task_func.delay(batch_size, max_execution_time)

        result = {
            "task_id": task.id,
            "status": "triggered",
            "message": "后台失效处理任务已触发",
            "batch_size": batch_size,
            "max_execution_time": max_execution_time,
        }

        logger.info(f"触发后台失效处理任务: {task.id}")

        return result

    except Exception as e:
        logger.error(f"触发后台失效处理任务失败: {e}")
        return {"status": "failed", "error": str(e)}


def trigger_queue_monitoring():
    """
    触发队列监控任务（使用依赖注入）

    返回:
        Dict[str, Any]: 任务触发结果
    """
    try:
        # 检查是否已注册任务触发器
        if _task_triggers["monitor_invalidation_queue"] is None:
            return {
                "status": "not_registered",
                "error": "队列监控任务未注册，请先调用register_task_triggers",
            }

        # 使用注册的任务触发器
        task_func = _task_triggers["monitor_invalidation_queue"]
        task = task_func.delay()

        result = {
            "task_id": task.id,
            "status": "triggered",
            "message": "队列监控任务已触发",
        }

        logger.info(f"触发队列监控任务: {task.id}")

        return result

    except Exception as e:
        logger.error(f"触发队列监控任务失败: {e}")
        return {"status": "failed", "error": str(e)}


def trigger_cleanup_task(max_age: int = 3600):
    """
    触发清理过期记录任务（使用依赖注入）

    参数:
        max_age (int): 最大保留时间（秒）

    返回:
        Dict[str, Any]: 任务触发结果
    """
    try:
        # 检查是否已注册任务触发器
        if _task_triggers["cleanup_expired_invalidations"] is None:
            return {
                "status": "not_registered",
                "error": "清理过期记录任务未注册，请先调用register_task_triggers",
            }

        # 使用注册的任务触发器
        task_func = _task_triggers["cleanup_expired_invalidations"]
        task = task_func.delay(max_age)

        result = {
            "task_id": task.id,
            "status": "triggered",
            "message": "清理过期记录任务已触发",
            "max_age": max_age,
        }

        logger.info(f"触发清理过期记录任务: {task.id}")

        return result

    except Exception as e:
        logger.error(f"触发清理过期记录任务失败: {e}")
        return {"status": "failed", "error": str(e)}


# 为了向后兼容，保留原有的硬编码导入方式作为备选
def _trigger_with_fallback(task_type: str, *args, **kwargs):
    """
    使用备选方式触发任务（向后兼容）

    参数:
        task_type (str): 任务类型
        *args, **kwargs: 任务参数

    返回:
        Dict[str, Any]: 任务触发结果
    """
    try:
        if task_type == "process_delayed_invalidations":
            from app.tasks.cache_invalidation_tasks import (
                process_delayed_invalidations_task,
            )

            task = process_delayed_invalidations_task.delay(*args, **kwargs)
        elif task_type == "monitor_invalidation_queue":
            from app.tasks.cache_invalidation_tasks import (
                monitor_invalidation_queue_task,
            )

            task = monitor_invalidation_queue_task.delay(*args, **kwargs)
        elif task_type == "cleanup_expired_invalidations":
            from app.tasks.cache_invalidation_tasks import (
                cleanup_expired_invalidations_task,
            )

            task = cleanup_expired_invalidations_task.delay(*args, **kwargs)
        else:
            return {"status": "failed", "error": f"未知的任务类型: {task_type}"}

        return {
            "task_id": task.id,
            "status": "triggered_fallback",
            "message": f"使用备选方式触发{task_type}任务",
        }

    except Exception as e:
        logger.error(f"备选任务触发失败: {e}")
        return {"status": "failed", "error": str(e)}


# 保留原有的process_delayed_invalidations函数用于后台任务内部调用
# 但将其标记为内部函数，不推荐外部直接调用
def _process_delayed_invalidations_internal(batch_size: int = 100) -> Dict[str, Any]:
    """
    内部处理延迟失效队列（仅供后台任务使用）

    参数:
        batch_size (int): 批处理大小

    返回:
        Dict[str, Any]: 处理结果
    """
    start_time = time.time()
    results = {"processed_count": 0, "remaining_count": 0, "execution_time": 0}

    try:
        redis_client = _get_redis_client()
        if not redis_client:
            results["execution_time"] = time.time() - start_time
            return results

        # 获取待处理的失效项（按时间戳排序，从最老的开始）
        pending_tasks = redis_client.zrange(
            DELAYED_INVALIDATION_QUEUE, 0, batch_size - 1, withscores=True
        )

        if not pending_tasks:
            results["execution_time"] = time.time() - start_time
            return results

        # 按缓存级别分组
        l1_keys = []
        l2_keys = []
        task_jsons_to_remove = []

        for task_json, score in pending_tasks:
            try:
                task = json.loads(task_json)
                if not task.get("processed", False):
                    if task["cache_level"] == "l1":
                        l1_keys.append(task["cache_key"])
                    else:
                        l2_keys.append(task["cache_key"])
                    task_jsons_to_remove.append(task_json)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析任务失败: {e}")
                continue

        # 使用缓存管理器的公共API执行失效
        cache_manager = _get_cache_manager()
        if cache_manager:
            # 批量处理L1缓存
            if l1_keys:
                l1_results = cache_manager.invalidate_keys(l1_keys, cache_level="l1")
                logger.debug(f"L1缓存失效: {l1_results['l1_invalidated']} 个成功")

            # 批量处理L2缓存
            if l2_keys:
                l2_results = cache_manager.invalidate_keys(l2_keys, cache_level="l2")
                logger.debug(f"L2缓存失效: {l2_results['l2_invalidated']} 个成功")

        # 从队列中移除已处理的任务
        if task_jsons_to_remove:
            redis_client.zrem(DELAYED_INVALIDATION_QUEUE, *task_jsons_to_remove)
            # 记录出队速率
            _record_rate_stats(redis_client, "out", len(task_jsons_to_remove))

        results["processed_count"] = len(task_jsons_to_remove)
        results["remaining_count"] = redis_client.zcard(DELAYED_INVALIDATION_QUEUE)

        logger.info(
            f"处理延迟失效: {results['processed_count']} 个, 剩余: {results['remaining_count']} 个"
        )

    except Exception as e:
        logger.error(f"处理延迟失效失败: {e}")

    results["execution_time"] = time.time() - start_time
    return results


# 为了向后兼容，保留原函数名但标记为已弃用
import warnings


def process_delayed_invalidations(batch_size: int = 100) -> int:
    """
    处理延迟失效队列（已弃用，请使用trigger_background_invalidation_processing）

    参数:
        batch_size (int): 批处理大小

    返回:
        int: 实际处理的任务数量
    """
    warnings.warn(
        "process_delayed_invalidations已弃用，请使用trigger_background_invalidation_processing触发后台任务",
        DeprecationWarning,
        stacklevel=2,
    )
    result = _process_delayed_invalidations_internal(batch_size)
    return result.get("processed_count", 0)


def cleanup_expired_invalidations(max_age: int = 3600) -> int:
    """
    清理过期的失效记录（基于Sorted Set，高效实现，同时清理反向索引）

    参数:
        max_age (int): 最大保留时间（秒）

    返回:
        int: 实际清理的记录数量
    """
    current_time = time.time()
    cutoff_time = current_time - max_age

    # 移除过期的失效记录
    redis_client = _get_redis_client()
    if not redis_client:
        return 0

    try:
        # 获取要删除的过期任务（在删除前先获取内容）
        expired_tasks = redis_client.zrangebyscore(
            DELAYED_INVALIDATION_QUEUE,
            "-inf",  # 最小分数
            cutoff_time,  # 最大分数（过期时间）
        )

        if not expired_tasks:
            logger.debug("没有发现过期的失效记录")
            return 0

        # 解析过期任务，提取cache_key用于清理反向索引
        cache_keys_to_cleanup = []
        for task_json in expired_tasks:
            try:
                task = json.loads(task_json)
                cache_keys_to_cleanup.append(task["cache_key"])
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析过期任务失败: {e}")
                continue

        # 使用ZREMRANGEBYSCORE高效删除过期任务
        expired_count = redis_client.zremrangebyscore(
            DELAYED_INVALIDATION_QUEUE,
            "-inf",  # 最小分数
            cutoff_time,  # 最大分数（过期时间）
        )

        if expired_count > 0:
            # 清理反向索引中的过期记录
            if cache_keys_to_cleanup:
                _cleanup_reverse_indexes(redis_client, cache_keys_to_cleanup)
                logger.info(
                    f"清理过期失效记录: {expired_count} 个, 清理反向索引: {len(cache_keys_to_cleanup)} 个键"
                )
            else:
                logger.info(f"清理过期失效记录: {expired_count} 个")

            _update_stats("delayed_invalidations", -expired_count)  # 更新统计
        else:
            logger.debug("没有发现过期的失效记录")

        return expired_count

    except Exception as e:
        logger.error(f"清理过期失效记录失败: {e}")
        return 0


def _cleanup_reverse_indexes(redis_client, cache_keys: List[str]):
    """
    清理反向索引中的键（增强版，支持批量清理）

    参数:
        redis_client: Redis客户端
        cache_keys (List[str]): 要清理的缓存键列表
    """
    try:
        # 按索引类型分组，提高清理效率
        reason_keys_to_clean = set()
        user_keys_to_clean = set()
        server_keys_to_clean = set()
        pattern_keys_to_clean = set()

        for cache_key in cache_keys:
            # 解析缓存键
            key_parts = cache_key.split(":")

            # 收集所有可能的索引键
            if len(key_parts) >= 2:
                pattern_keys_to_clean.add(f"{key_parts[0]}:{key_parts[1]}:*")

            # 收集用户索引键
            if len(key_parts) >= 3 and key_parts[0] == "perm":
                try:
                    user_id = int(key_parts[1])
                    user_keys_to_clean.add(user_id)
                except (ValueError, IndexError):
                    pass

            # 收集服务器索引键
            if len(key_parts) >= 4 and key_parts[0] == "perm":
                try:
                    server_id = int(key_parts[2])
                    server_keys_to_clean.add(server_id)
                except (ValueError, IndexError):
                    pass

        # 批量清理模式索引
        for pattern in pattern_keys_to_clean:
            pattern_index_key = f"{PATTERN_INDEX_PREFIX}{pattern}"
            for cache_key in cache_keys:
                redis_client.srem(pattern_index_key, cache_key)

        # 批量清理用户索引
        for user_id in user_keys_to_clean:
            user_index_key = f"{USER_INDEX_PREFIX}{user_id}"
            for cache_key in cache_keys:
                redis_client.srem(user_index_key, cache_key)

        # 批量清理服务器索引
        for server_id in server_keys_to_clean:
            server_index_key = f"{SERVER_INDEX_PREFIX}{server_id}"
            for cache_key in cache_keys:
                redis_client.srem(server_index_key, cache_key)

        # 清理原因索引（需要从任务中获取原因信息）
        # 注意：这里我们无法直接清理原因索引，因为原因信息在任务JSON中
        # 在实际使用中，原因索引的清理主要依赖于任务处理时的清理

        logger.debug(
            f"清理反向索引完成: 模式索引 {len(pattern_keys_to_clean)} 个, 用户索引 {len(user_keys_to_clean)} 个, 服务器索引 {len(server_keys_to_clean)} 个"
        )

    except Exception as e:
        logger.error(f"清理反向索引失败: {e}")


def cleanup_orphaned_reverse_indexes():
    """
    清理孤立的反向索引（清理那些在主队列中不存在的键）

    返回:
        Dict[str, Any]: 清理结果
    """
    try:
        redis_client = _get_redis_client()
        if not redis_client:
            return {"status": "failed", "error": "Redis连接不可用"}

        # 获取主队列中的所有cache_key
        all_tasks = redis_client.zrange(
            DELAYED_INVALIDATION_QUEUE, 0, -1, withscores=True
        )
        valid_cache_keys = set()

        for task_json, score in all_tasks:
            try:
                task = json.loads(task_json)
                valid_cache_keys.add(task["cache_key"])
            except (json.JSONDecodeError, KeyError):
                continue

        # 清理各种反向索引中的孤立键
        cleaned_stats = {
            "reason_index": 0,
            "user_index": 0,
            "server_index": 0,
            "pattern_index": 0,
        }

        # 清理原因索引
        try:
            reason_keys = redis_client.keys(
                f"{RATE_STATS_PREFIX}{REASON_INDEX_PREFIX}*"
            )
            for reason_key in reason_keys:
                reason_name = reason_key.decode("utf-8").split(":")[-1]
                index_key = f"{REASON_INDEX_PREFIX}{reason_name}"
                orphaned_keys = redis_client.smembers(index_key)

                for orphaned_key in orphaned_keys:
                    cache_key = (
                        orphaned_key.decode("utf-8")
                        if isinstance(orphaned_key, bytes)
                        else orphaned_key
                    )
                    if cache_key not in valid_cache_keys:
                        redis_client.srem(index_key, cache_key)
                        cleaned_stats["reason_index"] += 1
        except Exception as e:
            logger.error(f"清理原因索引失败: {e}")

        # 清理用户索引
        try:
            user_keys = redis_client.keys(f"{USER_INDEX_PREFIX}*")
            for user_key in user_keys:
                user_id = user_key.decode("utf-8").split(":")[-1]
                orphaned_keys = redis_client.smembers(user_key)

                for orphaned_key in orphaned_keys:
                    cache_key = (
                        orphaned_key.decode("utf-8")
                        if isinstance(orphaned_key, bytes)
                        else orphaned_key
                    )
                    if cache_key not in valid_cache_keys:
                        redis_client.srem(user_key, cache_key)
                        cleaned_stats["user_index"] += 1
        except Exception as e:
            logger.error(f"清理用户索引失败: {e}")

        # 清理服务器索引
        try:
            server_keys = redis_client.keys(f"{SERVER_INDEX_PREFIX}*")
            for server_key in server_keys:
                server_id = server_key.decode("utf-8").split(":")[-1]
                orphaned_keys = redis_client.smembers(server_key)

                for orphaned_key in orphaned_keys:
                    cache_key = (
                        orphaned_key.decode("utf-8")
                        if isinstance(orphaned_key, bytes)
                        else orphaned_key
                    )
                    if cache_key not in valid_cache_keys:
                        redis_client.srem(server_key, cache_key)
                        cleaned_stats["server_index"] += 1
        except Exception as e:
            logger.error(f"清理服务器索引失败: {e}")

        # 清理模式索引
        try:
            pattern_keys = redis_client.keys(f"{PATTERN_INDEX_PREFIX}*")
            for pattern_key in pattern_keys:
                pattern_name = pattern_key.decode("utf-8").split(":")[-1]
                orphaned_keys = redis_client.smembers(pattern_key)

                for orphaned_key in orphaned_keys:
                    cache_key = (
                        orphaned_key.decode("utf-8")
                        if isinstance(orphaned_key, bytes)
                        else orphaned_key
                    )
                    if cache_key not in valid_cache_keys:
                        redis_client.srem(pattern_key, cache_key)
                        cleaned_stats["pattern_index"] += 1
        except Exception as e:
            logger.error(f"清理模式索引失败: {e}")

        total_cleaned = sum(cleaned_stats.values())
        logger.info(f"清理孤立反向索引完成: {total_cleaned} 个孤立键")

        return {
            "status": "success",
            "cleaned_stats": cleaned_stats,
            "total_cleaned": total_cleaned,
        }

    except Exception as e:
        logger.error(f"清理孤立反向索引失败: {e}")
        return {"status": "failed", "error": str(e)}


def get_cache_auto_tune_suggestions() -> Dict[str, Any]:
    """
    获取缓存自动调优建议

    返回:
        Dict[str, Any]: 调优建议
    """
    suggestions = []

    # 使用通用分析函数获取最近1小时的任务
    current_time = time.time()
    analysis_result = _analyze_delayed_queue(max_tasks=100, current_time=current_time)

    # 过滤最近1小时的任务
    recent_invalidations = []
    for task in analysis_result["tasks"]:
        if task.get("timestamp", 0) > current_time - 3600:  # 任务时间在1小时内
            recent_invalidations.append(task)

    if len(recent_invalidations) > 100:
        suggestions.append(
            {
                "type": "high_invalidation_rate",
                "message": "失效频率过高，建议检查缓存策略",
                "action": "review_cache_strategy",
            }
        )

    # 分析失效模式
    key_patterns = defaultdict(int)
    for task in recent_invalidations:
        key_parts = task["cache_key"].split(":")
        if len(key_parts) >= 2:
            pattern = f"{key_parts[0]}:{key_parts[1]}"
            key_patterns[pattern] += 1

    for pattern, count in key_patterns.items():
        if count > 20:
            suggestions.append(
                {
                    "type": "frequent_pattern_invalidation",
                    "pattern": pattern,
                    "count": count,
                    "message": f"模式 {pattern} 频繁失效，建议优化",
                    "action": "optimize_pattern_cache",
                }
            )

    return {
        "suggestions": suggestions,
        "recent_invalidations": len(recent_invalidations),
        "patterns": dict(key_patterns),
    }


def get_cache_invalidation_strategy_analysis() -> Dict[str, Any]:
    """
    获取缓存失效策略分析

    返回:
        Dict[str, Any]: 策略分析
    """
    # 使用通用分析函数
    analysis_result = _analyze_delayed_queue(max_tasks=100)

    # 分析失效原因分布
    reasons = analysis_result["reasons"]

    # 分析缓存级别分布
    levels = analysis_result["cache_levels"]

    # 计算平均失效延迟
    task_ages = analysis_result["task_ages"]
    avg_delay = sum(task_ages) / len(task_ages) if task_ages else 0
    pending_count = analysis_result["valid_tasks"]

    return {
        "reasons_distribution": reasons,
        "levels_distribution": levels,
        "avg_delay": avg_delay,
        "total_pending": pending_count,
        "total_processed": _get_stats()["delayed_invalidations"] - pending_count,
    }


def get_distributed_cache_stats() -> Dict[str, Any]:
    """
    获取分布式缓存集群统计信息（兼容性函数）

    返回:
        Dict: 包含集群节点信息、健康状态和操作统计
    """
    try:
        cache_manager = _get_cache_manager()
        if cache_manager:
            return cache_manager.get_distributed_cache_stats()
        return {"connected": False, "error": "缓存管理器未初始化"}
    except Exception as e:
        logger.error(f"获取分布式缓存统计失败: {e}")
        return {"connected": False, "error": str(e)}


def distributed_cache_get(key: str) -> Optional[bytes]:
    """
    从分布式缓存获取数据（兼容性函数）

    参数:
        key (str): 缓存键

    返回:
        Optional[bytes]: 缓存值，如果不存在返回None
    """
    try:
        cache_manager = _get_cache_manager()
        if cache_manager:
            return cache_manager.distributed_cache_get(key)
        return None
    except Exception as e:
        logger.error(f"从分布式缓存获取数据失败: {e}")
        return None


def distributed_cache_set(key: str, value: bytes, ttl: int = 300) -> bool:
    """
    向分布式缓存设置数据（兼容性函数）

    参数:
        key (str): 缓存键
        value (bytes): 缓存值
        ttl (int): 过期时间（秒）

    返回:
        bool: 操作是否成功
    """
    try:
        cache_manager = _get_cache_manager()
        if cache_manager:
            return cache_manager.distributed_cache_set(key, value, ttl)
        return False
    except Exception as e:
        logger.error(f"向分布式缓存设置数据失败: {e}")
        return False


def distributed_cache_delete(key: str) -> bool:
    """
    从分布式缓存删除数据（兼容性函数）

    参数:
        key (str): 缓存键

    返回:
        bool: 操作是否成功
    """
    try:
        cache_manager = _get_cache_manager()
        if cache_manager:
            return cache_manager.distributed_cache_delete(key)
        return False
    except Exception as e:
        logger.error(f"从分布式缓存删除数据失败: {e}")
        return False


def execute_global_smart_batch_invalidation() -> Dict[str, Any]:
    """
    基于全局分析执行智能批量失效

    返回:
        Dict[str, Any]: 执行结果
    """
    try:
        # 获取全局分析结果
        analysis = get_smart_batch_invalidation_analysis()

        if analysis["pending_count"] == 0:
            return {
                "status": "no_tasks",
                "message": "队列中没有待处理的任务",
                "executed_batches": 0,
                "total_processed": 0,
            }

        executed_batches = 0
        total_processed = 0
        results = []

        # 按优先级执行推荐操作
        recommendations = analysis.get("recommendations", [])

        # 首先处理紧急操作
        urgent_actions = analysis.get("global_analysis", {}).get("urgent_actions", [])
        for action in urgent_actions:
            if action["type"] == "timeout_cleanup":
                # 清理超时任务
                cleanup_result = cleanup_expired_invalidations(max_age=3600)
                results.append(
                    {
                        "type": "timeout_cleanup",
                        "result": cleanup_result,
                        "priority": "critical",
                    }
                )

        # 按优先级处理推荐操作
        high_priority = [r for r in recommendations if r.get("priority") == "high"]
        medium_priority = [r for r in recommendations if r.get("priority") == "medium"]

        # 先处理高优先级操作
        for recommendation in high_priority:
            batch_result = _execute_recommendation(recommendation)
            if batch_result["success"]:
                executed_batches += 1
                total_processed += batch_result["processed_count"]
            results.append(batch_result)

        # 再处理中等优先级操作
        for recommendation in medium_priority:
            batch_result = _execute_recommendation(recommendation)
            if batch_result["success"]:
                executed_batches += 1
                total_processed += batch_result["processed_count"]
            results.append(batch_result)

        return {
            "status": "completed",
            "executed_batches": executed_batches,
            "total_processed": total_processed,
            "queue_health": analysis.get("global_analysis", {}).get(
                "queue_health", "unknown"
            ),
            "performance_metrics": analysis.get("performance_metrics", {}),
            "results": results,
        }

    except Exception as e:
        logger.error(f"执行全局智能批量失效失败: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "executed_batches": 0,
            "total_processed": 0,
        }


def _execute_recommendation(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行单个推荐操作

    参数:
        recommendation (Dict[str, Any]): 推荐操作

    返回:
        Dict[str, Any]: 执行结果
    """
    try:
        rec_type = recommendation.get("type")
        redis_client = _get_redis_client()
        if not redis_client:
            return {
                "type": rec_type,
                "success": False,
                "processed_count": 0,
                "error": "Redis连接不可用",
            }

        if rec_type == "pattern_batch":
            # 按模式批量失效
            pattern = recommendation["pattern"]
            keys_to_invalidate, removed_tasks = _process_pattern_batch(
                redis_client, pattern
            )
            if keys_to_invalidate:
                result = execute_smart_batch_invalidation(keys_to_invalidate, "auto")
                return {
                    "type": "pattern_batch",
                    "pattern": pattern,
                    "success": result["success_count"] > 0,
                    "processed_count": result["success_count"],
                    "removed_tasks": removed_tasks,
                    "result": result,
                }

        elif rec_type == "reason_batch":
            # 按原因批量失效
            reason = recommendation["reason"]
            keys_to_invalidate, removed_tasks = _process_reason_batch(
                redis_client, reason
            )
            if keys_to_invalidate:
                result = execute_smart_batch_invalidation(keys_to_invalidate, "auto")
                return {
                    "type": "reason_batch",
                    "reason": reason,
                    "success": result["success_count"] > 0,
                    "processed_count": result["success_count"],
                    "removed_tasks": removed_tasks,
                    "result": result,
                }

        elif rec_type == "user_batch":
            # 按用户批量失效
            user_id = recommendation["user_id"]
            keys_to_invalidate, removed_tasks = _process_user_batch(
                redis_client, user_id
            )
            if keys_to_invalidate:
                result = execute_smart_batch_invalidation(keys_to_invalidate, "auto")
                return {
                    "type": "user_batch",
                    "user_id": user_id,
                    "success": result["success_count"] > 0,
                    "processed_count": result["success_count"],
                    "removed_tasks": removed_tasks,
                    "result": result,
                }

        elif rec_type == "server_batch":
            # 按服务器批量失效
            server_id = recommendation["server_id"]
            keys_to_invalidate, removed_tasks = _process_server_batch(
                redis_client, server_id
            )
            if keys_to_invalidate:
                result = execute_smart_batch_invalidation(keys_to_invalidate, "auto")
                return {
                    "type": "server_batch",
                    "server_id": server_id,
                    "success": result["success_count"] > 0,
                    "processed_count": result["success_count"],
                    "removed_tasks": removed_tasks,
                    "result": result,
                }

        return {
            "type": rec_type,
            "success": False,
            "processed_count": 0,
            "error": f"未知的推荐类型: {rec_type}",
        }

    except Exception as e:
        logger.error(f"执行推荐操作失败: {e}")
        return {
            "type": recommendation.get("type", "unknown"),
            "success": False,
            "processed_count": 0,
            "error": str(e),
        }


def _update_reverse_indexes(redis_client, cache_key: str, reason: str = None):
    """
    更新反向索引

    参数:
        redis_client: Redis客户端
        cache_key (str): 缓存键
        reason (str): 失效原因
    """
    try:
        # 解析缓存键
        key_parts = cache_key.split(":")

        # 更新原因索引
        if reason:
            reason_index_key = f"{REASON_INDEX_PREFIX}{reason}"
            redis_client.sadd(reason_index_key, cache_key)
            redis_client.expire(reason_index_key, 86400)  # 24小时过期

        # 更新用户索引
        if len(key_parts) >= 3 and key_parts[0] == "perm":
            try:
                user_id = int(key_parts[1])
                user_index_key = f"{USER_INDEX_PREFIX}{user_id}"
                redis_client.sadd(user_index_key, cache_key)
                redis_client.expire(user_index_key, 86400)  # 24小时过期
            except (ValueError, IndexError):
                pass

        # 更新服务器索引
        if len(key_parts) >= 4 and key_parts[0] == "perm":
            try:
                server_id = int(key_parts[2])
                server_index_key = f"{SERVER_INDEX_PREFIX}{server_id}"
                redis_client.sadd(server_index_key, cache_key)
                redis_client.expire(server_index_key, 86400)  # 24小时过期
            except (ValueError, IndexError):
                pass

        # 更新模式索引
        if len(key_parts) >= 2:
            pattern = f"{key_parts[0]}:{key_parts[1]}:*"
            pattern_index_key = f"{PATTERN_INDEX_PREFIX}{pattern}"
            redis_client.sadd(pattern_index_key, cache_key)
            redis_client.expire(pattern_index_key, 86400)  # 24小时过期

    except Exception as e:
        logger.error(f"更新反向索引失败: {e}")


def _cleanup_reverse_indexes(redis_client, cache_keys: List[str]):
    """
    清理反向索引中的键（增强版，支持批量清理）

    参数:
        redis_client: Redis客户端
        cache_keys (List[str]): 要清理的缓存键列表
    """
    try:
        # 按索引类型分组，提高清理效率
        reason_keys_to_clean = set()
        user_keys_to_clean = set()
        server_keys_to_clean = set()
        pattern_keys_to_clean = set()

        for cache_key in cache_keys:
            # 解析缓存键
            key_parts = cache_key.split(":")

            # 收集所有可能的索引键
            if len(key_parts) >= 2:
                pattern_keys_to_clean.add(f"{key_parts[0]}:{key_parts[1]}:*")

            # 收集用户索引键
            if len(key_parts) >= 3 and key_parts[0] == "perm":
                try:
                    user_id = int(key_parts[1])
                    user_keys_to_clean.add(user_id)
                except (ValueError, IndexError):
                    pass

            # 收集服务器索引键
            if len(key_parts) >= 4 and key_parts[0] == "perm":
                try:
                    server_id = int(key_parts[2])
                    server_keys_to_clean.add(server_id)
                except (ValueError, IndexError):
                    pass

        # 批量清理模式索引
        for pattern in pattern_keys_to_clean:
            pattern_index_key = f"{PATTERN_INDEX_PREFIX}{pattern}"
            for cache_key in cache_keys:
                redis_client.srem(pattern_index_key, cache_key)

        # 批量清理用户索引
        for user_id in user_keys_to_clean:
            user_index_key = f"{USER_INDEX_PREFIX}{user_id}"
            for cache_key in cache_keys:
                redis_client.srem(user_index_key, cache_key)

        # 批量清理服务器索引
        for server_id in server_keys_to_clean:
            server_index_key = f"{SERVER_INDEX_PREFIX}{server_id}"
            for cache_key in cache_keys:
                redis_client.srem(server_index_key, cache_key)

        # 清理原因索引（需要从任务中获取原因信息）
        # 注意：这里我们无法直接清理原因索引，因为原因信息在任务JSON中
        # 在实际使用中，原因索引的清理主要依赖于任务处理时的清理

        logger.debug(
            f"清理反向索引完成: 模式索引 {len(pattern_keys_to_clean)} 个, 用户索引 {len(user_keys_to_clean)} 个, 服务器索引 {len(server_keys_to_clean)} 个"
        )

    except Exception as e:
        logger.error(f"清理反向索引失败: {e}")


def _process_batch_by_index(
    redis_client, index_type: str, index_value: str, error_message: str
) -> tuple[List[str], int]:
    """
    通用的批量失效处理函数（基于反向索引）

    参数:
        redis_client: Redis客户端
        index_type (str): 索引类型 ('pattern', 'reason', 'user', 'server')
        index_value (str): 索引值
        error_message (str): 错误消息

    返回:
        tuple[List[str], int]: (要失效的键列表, 移除的任务数)
    """
    try:
        # 根据索引类型构建索引键
        if index_type == "pattern":
            index_key = f"{PATTERN_INDEX_PREFIX}{index_value}"
        elif index_type == "reason":
            index_key = f"{REASON_INDEX_PREFIX}{index_value}"
        elif index_type == "user":
            index_key = f"{USER_INDEX_PREFIX}{index_value}"
        elif index_type == "server":
            index_key = f"{SERVER_INDEX_PREFIX}{index_value}"
        else:
            logger.error(f"未知的索引类型: {index_type}")
            return [], 0

        # 使用反向索引获取匹配的键
        keys_to_invalidate = redis_client.smembers(index_key)

        if not keys_to_invalidate:
            return [], 0

        # 转换为字符串列表
        keys_to_invalidate = [
            key.decode("utf-8") if isinstance(key, bytes) else key
            for key in keys_to_invalidate
        ]

        # 从队列中移除相关任务
        removed_tasks = _remove_tasks_by_keys_lua(redis_client, keys_to_invalidate)

        # 清理反向索引
        _cleanup_reverse_indexes(redis_client, keys_to_invalidate)

        return keys_to_invalidate, removed_tasks

    except Exception as e:
        logger.error(f"{error_message}: {e}")
        return [], 0


def _process_pattern_batch(redis_client, pattern: str) -> tuple[List[str], int]:
    """
    处理模式批量失效（使用反向索引）

    参数:
        redis_client: Redis客户端
        pattern (str): 键模式

    返回:
        tuple[List[str], int]: (要失效的键列表, 移除的任务数)
    """
    return _process_batch_by_index(
        redis_client, "pattern", pattern, "处理模式批量失效失败"
    )


def _process_reason_batch(redis_client, reason: str) -> tuple[List[str], int]:
    """
    处理原因批量失效（使用反向索引）

    参数:
        redis_client: Redis客户端
        reason (str): 失效原因

    返回:
        tuple[List[str], int]: (要失效的键列表, 移除的任务数)
    """
    return _process_batch_by_index(
        redis_client, "reason", reason, "处理原因批量失效失败"
    )


def _process_user_batch(redis_client, user_id: int) -> tuple[List[str], int]:
    """
    处理用户批量失效（使用反向索引）

    参数:
        redis_client: Redis客户端
        user_id (int): 用户ID

    返回:
        tuple[List[str], int]: (要失效的键列表, 移除的任务数)
    """
    return _process_batch_by_index(
        redis_client, "user", str(user_id), "处理用户批量失效失败"
    )


def _process_server_batch(redis_client, server_id: int) -> tuple[List[str], int]:
    """
    处理服务器批量失效（使用反向索引）

    参数:
        redis_client: Redis客户端
        server_id (int): 服务器ID

    返回:
        tuple[List[str], int]: (要失效的键列表, 移除的任务数)
    """
    return _process_batch_by_index(
        redis_client, "server", str(server_id), "处理服务器批量失效失败"
    )


def _remove_tasks_by_keys_lua(redis_client, cache_keys: List[str]) -> int:
    if not cache_keys:
        return 0

    # 1. 将待删除的 keys 存入一个临时的 Redis Set
    temp_key_set = f"temp_remove_keys:{uuid.uuid4()}"
    redis_client.sadd(temp_key_set, *cache_keys)
    redis_client.expire(temp_key_set, 60)  # 设置短暂过期，以防万一

    # 2. 加载并执行 Lua 脚本
    lua_script = "remove_tasks_by_keys.lua"
    try:
        # redis-py 的 evalsha 会自动处理脚本加载和缓存
        remover_sha = redis_client.script_load(lua_script)
        removed_count = redis_client.evalsha(
            remover_sha, 1, temp_key_set, DELAYED_INVALIDATION_QUEUE
        )
        return removed_count
    finally:
        # 3. 清理临时 Set
        redis_client.delete(temp_key_set)


def _remove_tasks_by_keys(redis_client, cache_keys: List[str]) -> int:
    """
    根据缓存键从队列中移除任务（基于Sorted Set）

    参数:
        redis_client: Redis客户端
        cache_keys (List[str]): 缓存键列表

    返回:
        int: 移除的任务数
    """
    removed_tasks = 0

    try:
        # 获取队列中的所有任务
        all_tasks = redis_client.zrange(
            DELAYED_INVALIDATION_QUEUE, 0, -1, withscores=True
        )
        cache_keys_set = set(cache_keys)
        tasks_to_remove = []

        for task_json, score in all_tasks:
            try:
                task = json.loads(task_json)
                if (
                    not task.get("processed", False)
                    and task["cache_key"] in cache_keys_set
                ):
                    tasks_to_remove.append(task_json)
            except (json.JSONDecodeError, KeyError):
                continue

        # 批量移除匹配的任务
        if tasks_to_remove:
            removed_tasks = redis_client.zrem(
                DELAYED_INVALIDATION_QUEUE, *tasks_to_remove
            )

        return removed_tasks

    except Exception as e:
        logger.error(f"根据缓存键移除任务失败: {e}")
        return 0


def _match_pattern(cache_key: str, pattern: str) -> bool:
    """
    检查缓存键是否匹配模式

    参数:
        cache_key (str): 缓存键
        pattern (str): 模式

    返回:
        bool: 是否匹配
    """
    try:
        # 将模式转换为正则表达式
        import re

        pattern_regex = pattern.replace("*", ".*")
        return bool(re.match(pattern_regex, cache_key))
    except Exception:
        return False


def _match_user_pattern(cache_key: str, user_id: int) -> bool:
    """
    检查缓存键是否匹配用户模式

    参数:
        cache_key (str): 缓存键
        user_id (int): 用户ID

    返回:
        bool: 是否匹配
    """
    try:
        key_parts = cache_key.split(":")
        if len(key_parts) >= 3 and key_parts[0] == "perm":
            return int(key_parts[1]) == user_id
    except (ValueError, IndexError):
        pass
    return False


def _match_server_pattern(cache_key: str, server_id: int) -> bool:
    """
    检查缓存键是否匹配服务器模式

    参数:
        cache_key (str): 缓存键
        server_id (int): 服务器ID

    返回:
        bool: 是否匹配
    """
    try:
        key_parts = cache_key.split(":")
        if len(key_parts) >= 4 and key_parts[0] == "perm":
            return int(key_parts[2]) == server_id
    except (ValueError, IndexError):
        pass
    return False


def get_redis_connection_status() -> Dict[str, Any]:
    """
    获取Redis连接状态

    返回:
        Dict[str, Any]: 连接状态信息
    """
    status = {
        "cache_module_available": get_hybrid_cache is not None,
        "cache_manager_available": False,
        "cache_redis_available": False,
        "independent_redis_available": False,
        "current_connection_type": None,
        "error_details": [],
    }

    # 检查缓存模块连接
    try:
        cache_manager = _get_cache_manager()
        status["cache_manager_available"] = cache_manager is not None

        if cache_manager:
            redis_client = cache_manager.get_redis_client()
            if redis_client:
                status["cache_redis_available"] = _check_redis_connection(redis_client)
                if status["cache_redis_available"]:
                    status["current_connection_type"] = "cache_module"
    except Exception as e:
        status["error_details"].append(f"缓存模块连接检查失败: {e}")

    # 检查独立Redis连接
    try:
        import redis

        config = _get_redis_config()
        redis_client = redis.Redis(**config)
        status["independent_redis_available"] = _check_redis_connection(redis_client)
        if (
            status["independent_redis_available"]
            and status["current_connection_type"] is None
        ):
            status["current_connection_type"] = "independent"
    except Exception as e:
        status["error_details"].append(f"独立Redis连接检查失败: {e}")

    # 总体可用性
    status["overall_available"] = (
        status["cache_redis_available"] or status["independent_redis_available"]
    )

    return status


def get_rate_statistics() -> Dict[str, Any]:
    """
    获取速率统计信息

    返回:
        Dict[str, Any]: 速率统计
    """
    try:
        redis_client = _get_redis_client()
        if not redis_client:
            return {
                "processing_rate": 0.0,
                "growth_rate": 0.0,
                "queue_length": 0,
                "rate_health": "unknown",
            }

        # 获取当前队列长度
        queue_length = redis_client.zcard(DELAYED_INVALIDATION_QUEUE)

        # 计算处理速率和增长率
        processing_rate = _calculate_processing_rate()
        growth_rate = _calculate_queue_growth_rate()

        # 评估速率健康状态
        rate_health = "healthy"
        if growth_rate > processing_rate * 1.5:
            rate_health = "critical"
        elif growth_rate > processing_rate:
            rate_health = "warning"
        elif processing_rate == 0 and growth_rate > 0:
            rate_health = "stalled"

        return {
            "processing_rate": processing_rate,
            "growth_rate": growth_rate,
            "queue_length": queue_length,
            "rate_health": rate_health,
            "processing_efficiency": (
                processing_rate / max(growth_rate, 1) if growth_rate > 0 else 0
            ),
        }

    except Exception as e:
        logger.error(f"获取速率统计失败: {e}")
        return {
            "processing_rate": 0.0,
            "growth_rate": 0.0,
            "queue_length": 0,
            "rate_health": "error",
        }


def _record_rate_stats(redis_client, rate_type: str, count: int = 1):
    """
    记录速率统计

    参数:
        redis_client: Redis客户端
        rate_type (str): 速率类型 ('in' 或 'out')
        count (int): 计数
    """
    try:
        current_time = time.time()
        minute_key = time.strftime("%Y%m%d%H%M", time.localtime(current_time))

        if rate_type == "in":
            stats_key = f"{RATE_STATS_PREFIX}{IN_RATE_PREFIX}{minute_key}"
        else:
            stats_key = f"{RATE_STATS_PREFIX}{OUT_RATE_PREFIX}{minute_key}"

        # 使用HINCRBY记录每分钟的统计
        redis_client.hincrby(stats_key, "count", count)
        redis_client.hset(stats_key, "timestamp", current_time)
        redis_client.expire(stats_key, 3600)  # 1小时过期

    except Exception as e:
        logger.error(f"记录速率统计失败: {e}")


def _get_rate_stats(
    redis_client, rate_type: str, minutes: int = 5
) -> List[Dict[str, Any]]:
    """
    获取速率统计

    参数:
        redis_client: Redis客户端
        rate_type (str): 速率类型 ('in' 或 'out')
        minutes (int): 获取最近几分钟的数据

    返回:
        List[Dict[str, Any]]: 速率统计数据
    """
    try:
        stats = []
        current_time = time.time()

        for i in range(minutes):
            # 计算时间戳
            timestamp = current_time - (i * 60)
            minute_key = time.strftime("%Y%m%d%H%M", time.localtime(timestamp))

            if rate_type == "in":
                stats_key = f"{RATE_STATS_PREFIX}{IN_RATE_PREFIX}{minute_key}"
            else:
                stats_key = f"{RATE_STATS_PREFIX}{OUT_RATE_PREFIX}{minute_key}"

            # 获取该分钟的统计数据
            minute_stats = redis_client.hgetall(stats_key)
            if minute_stats:
                count = int(minute_stats.get(b"count", 0))
                timestamp_val = float(minute_stats.get(b"timestamp", timestamp))
                stats.append(
                    {
                        "minute_key": minute_key,
                        "count": count,
                        "timestamp": timestamp_val,
                    }
                )

        return stats

    except Exception as e:
        logger.error(f"获取速率统计失败: {e}")
        return []
