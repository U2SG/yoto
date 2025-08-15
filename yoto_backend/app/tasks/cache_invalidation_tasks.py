"""
缓存失效后台任务

处理延迟失效队列的Celery任务
"""

import time
import logging
from celery import current_task, shared_task
from app.core.permission_invalidation import (
    _process_delayed_invalidations_internal,
    get_delayed_invalidation_stats,
    cleanup_expired_invalidations,
    get_smart_batch_invalidation_analysis,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="cache.process_delayed_invalidations")
def process_delayed_invalidations_task(
    self, batch_size: int = 100, max_execution_time: int = 300
):
    """
    处理延迟失效队列的后台任务

    参数:
        batch_size (int): 批处理大小
        max_execution_time (int): 最大执行时间（秒）

    返回:
        Dict[str, Any]: 处理结果
    """
    start_time = time.time()
    total_processed = 0
    total_batches = 0

    try:
        logger.info("开始处理延迟失效队列")

        # 持续处理直到达到最大执行时间或队列为空
        while (time.time() - start_time) < max_execution_time:
            # 处理一批任务
            results = _process_delayed_invalidations_internal(batch_size=batch_size)

            if results["processed_count"] == 0:
                # 队列为空，退出循环
                logger.info("延迟失效队列为空，停止处理")
                break

            total_processed += results["processed_count"]
            total_batches += 1

            # 更新任务进度
            self.update_state(
                state="PROGRESS",
                meta={
                    "processed_count": total_processed,
                    "batches_processed": total_batches,
                    "remaining_count": results["remaining_count"],
                    "execution_time": time.time() - start_time,
                },
            )

            logger.debug(
                f"处理批次 {total_batches}: {results['processed_count']} 个任务, 剩余: {results['remaining_count']} 个"
            )

            # 短暂休息，避免过度占用CPU
            time.sleep(0.1)

        execution_time = time.time() - start_time

        # 清理过期记录
        cleanup_expired_invalidations(max_age=3600)

        result = {
            "total_processed": total_processed,
            "total_batches": total_batches,
            "execution_time": execution_time,
            "status": "completed",
            "message": f"成功处理 {total_processed} 个延迟失效任务",
        }

        logger.info(
            f"延迟失效处理完成: {total_processed} 个任务, {total_batches} 个批次, 耗时 {execution_time:.2f} 秒"
        )

        return result

    except Exception as e:
        logger.error(f"处理延迟失效任务失败: {e}")
        return {
            "total_processed": total_processed,
            "total_batches": total_batches,
            "execution_time": time.time() - start_time,
            "status": "failed",
            "error": str(e),
        }


@shared_task(name="cache.get_invalidation_queue_stats")
def get_invalidation_queue_stats_task():
    """
    获取失效队列统计信息的后台任务

    返回:
        Dict[str, Any]: 队列统计信息
    """
    try:
        stats = get_delayed_invalidation_stats()
        analysis = get_smart_batch_invalidation_analysis()

        result = {
            "queue_stats": stats,
            "analysis": analysis,
            "timestamp": time.time(),
            "status": "completed",
        }

        logger.debug(
            f"获取失效队列统计: 待处理 {stats['pending_count']} 个, 已处理 {stats['processed_count']} 个"
        )

        return result

    except Exception as e:
        logger.error(f"获取失效队列统计失败: {e}")
        return {"status": "failed", "error": str(e), "timestamp": time.time()}


@shared_task(name="cache.cleanup_expired_invalidations")
def cleanup_expired_invalidations_task(max_age: int = 3600):
    """
    清理过期失效记录的后台任务

    参数:
        max_age (int): 最大保留时间（秒）

    返回:
        Dict[str, Any]: 清理结果
    """
    try:
        start_time = time.time()

        # 执行清理
        cleanup_expired_invalidations(max_age=max_age)

        execution_time = time.time() - start_time

        result = {
            "max_age": max_age,
            "execution_time": execution_time,
            "status": "completed",
            "message": f"清理过期失效记录完成，最大保留时间: {max_age} 秒",
        }

        logger.info(f"清理过期失效记录完成，耗时 {execution_time:.2f} 秒")

        return result

    except Exception as e:
        logger.error(f"清理过期失效记录失败: {e}")
        return {"status": "failed", "error": str(e), "timestamp": time.time()}


@shared_task(name="cache.monitor_invalidation_queue")
def monitor_invalidation_queue_task():
    """
    监控失效队列的后台任务

    返回:
        Dict[str, Any]: 监控结果
    """
    try:
        # 获取队列统计
        stats = get_delayed_invalidation_stats()
        analysis = get_smart_batch_invalidation_analysis()

        # 分析队列健康状态
        health_status = "healthy"
        warnings = []

        if stats["pending_count"] > 1000:
            health_status = "warning"
            warnings.append(f"队列积压严重: {stats['pending_count']} 个待处理任务")

        if stats["pending_count"] > 100:
            health_status = "attention"
            warnings.append(f"队列积压: {stats['pending_count']} 个待处理任务")

        # 检查是否有频繁失效的模式
        if analysis["recommendations"]:
            health_status = "warning"
            warnings.append(f"发现 {len(analysis['recommendations'])} 个批量失效建议")

        result = {
            "health_status": health_status,
            "queue_stats": stats,
            "analysis": analysis,
            "warnings": warnings,
            "timestamp": time.time(),
            "status": "completed",
        }

        if warnings:
            logger.warning(f"失效队列监控警告: {', '.join(warnings)}")
        else:
            logger.debug("失效队列状态正常")

        return result

    except Exception as e:
        logger.error(f"监控失效队列失败: {e}")
        return {
            "health_status": "error",
            "status": "failed",
            "error": str(e),
            "timestamp": time.time(),
        }


@shared_task(name="cache.execute_global_smart_batch_invalidation")
def execute_global_smart_batch_invalidation_task():
    """
    执行全局智能批量失效的后台任务

    返回:
        Dict[str, Any]: 执行结果
    """
    try:
        from app.core.permission_invalidation import (
            execute_global_smart_batch_invalidation,
        )

        start_time = time.time()

        # 执行全局智能批量失效
        result = execute_global_smart_batch_invalidation()

        execution_time = time.time() - start_time

        # 添加执行时间到结果中
        result["execution_time"] = execution_time
        result["timestamp"] = time.time()

        if result["status"] == "completed":
            logger.info(
                f"全局智能批量失效完成: {result['executed_batches']} 个批次, {result['total_processed']} 个任务, 耗时 {execution_time:.2f} 秒"
            )
        else:
            logger.warning(
                f"全局智能批量失效状态: {result['status']}, 消息: {result.get('message', '')}"
            )

        return result

    except Exception as e:
        logger.error(f"执行全局智能批量失效任务失败: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": time.time() - start_time,
            "timestamp": time.time(),
        }


# 定时任务配置
CELERY_BEAT_SCHEDULE = {
    "process-delayed-invalidations": {
        "task": "cache.process_delayed_invalidations",
        "schedule": 60.0,  # 每60秒执行一次
        "args": (100, 300),  # batch_size=100, max_execution_time=300
    },
    "cleanup-expired-invalidations": {
        "task": "cache.cleanup_expired_invalidations",
        "schedule": 3600.0,  # 每小时执行一次
        "args": (3600,),  # max_age=3600
    },
    "monitor-invalidation-queue": {
        "task": "cache.monitor_invalidation_queue",
        "schedule": 300.0,  # 每5分钟执行一次
    },
    "execute-global-smart-batch-invalidation": {
        "task": "cache.execute_global_smart_batch_invalidation",
        "schedule": 1800.0,  # 每30分钟执行一次
    },
}

# 任务路由配置
CELERY_ROUTES = {
    "cache.process_delayed_invalidations": {"queue": "cache_invalidation"},
    "cache.get_invalidation_queue_stats": {"queue": "cache_invalidation"},
    "cache.cleanup_expired_invalidations": {"queue": "cache_invalidation"},
    "cache.monitor_invalidation_queue": {"queue": "cache_invalidation"},
    "cache.execute_global_smart_batch_invalidation": {"queue": "cache_invalidation"},
}
