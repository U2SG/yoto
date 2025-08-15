"""
权限系统核心模块

提供显式依赖注入和统一的初始化流程
"""

import logging
from typing import Optional

from .permission_resilience import (
    get_resilience_controller,
    get_or_create_rate_limiter,
    get_or_create_circuit_breaker,
    CircuitBreakerState,
)
from .monitor_backends import get_monitor_backend
from .permission_monitor import get_permission_monitor
from .permission_ml import get_ml_performance_monitor, register_ml_config_callback
from .permissions_refactored import get_permission_system
from .hybrid_permission_cache import get_hybrid_cache

logger = logging.getLogger(__name__)

# 全局初始化状态
_platform_initialized = False


def initialize_permission_platform() -> bool:
    """
    初始化权限平台

    按照正确的依赖顺序创建所有单例实例：
    1. 底层控制器最先
    2. 依赖底层的模块其次
    3. 顶层门面最后
    4. 执行跨模块"接线"工作

    Returns:
        bool: 初始化是否成功
    """
    global _platform_initialized

    if _platform_initialized:
        logger.info("权限平台已经初始化，跳过重复初始化")
        return True

    try:
        logger.info("开始初始化权限平台...")

        # 1. 底层控制器最先
        logger.debug("初始化底层控制器...")
        resilience_controller = get_resilience_controller()
        monitor_backend = get_monitor_backend()

        # 2. 依赖底层的模块其次
        logger.debug("初始化监控模块...")
        monitor = get_permission_monitor()
        ml_monitor = get_ml_performance_monitor()

        # 3. 顶层门面最后
        logger.debug("初始化权限系统...")
        permission_system = get_permission_system()

        # 4. 执行所有必要的跨模块"接线"工作
        logger.debug("执行跨模块接线...")
        register_ml_config_callback(permission_system._apply_ml_optimization)

        # 5. 异步触发冷启动预热流程
        logger.debug("启动冷启动预热流程...")
        import threading

        def async_warm_up():
            """异步执行预热流程"""
            try:
                warm_up_result = permission_system.warm_up()
                if warm_up_result.get("success"):
                    logger.info("冷启动预热流程完成")
                else:
                    logger.warning(
                        f"冷启动预热流程部分失败: {warm_up_result.get('errors', [])}"
                    )
            except Exception as e:
                logger.error(f"异步预热流程执行失败: {e}")

        # 启动异步预热线程
        warm_up_thread = threading.Thread(target=async_warm_up, daemon=True)
        warm_up_thread.start()

        # 标记初始化完成
        _platform_initialized = True

        logger.info("权限平台初始化成功！")
        logger.info(f"  - 韧性控制器: {type(resilience_controller).__name__}")
        logger.info(f"  - 监控后端: {type(monitor_backend).__name__}")
        logger.info(f"  - 权限监控器: {type(monitor).__name__}")
        logger.info(f"  - ML监控器: {type(ml_monitor).__name__}")
        logger.info(f"  - 权限系统: {type(permission_system).__name__}")

        return True

    except Exception as e:
        logger.error(f"权限平台初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def is_platform_initialized() -> bool:
    """
    检查权限平台是否已初始化

    Returns:
        bool: 是否已初始化
    """
    return _platform_initialized


def reset_platform_initialization():
    """
    重置平台初始化状态（主要用于测试）
    """
    global _platform_initialized
    _platform_initialized = False
    logger.info("权限平台初始化状态已重置")


def get_initialization_status() -> dict:
    """
    获取初始化状态详情

    Returns:
        dict: 初始化状态信息
    """
    return {
        "initialized": _platform_initialized,
        "components": {
            "resilience_controller": "get_resilience_controller()",
            "monitor_backend": "get_monitor_backend()",
            "permission_monitor": "get_permission_monitor()",
            "ml_performance_monitor": "get_ml_performance_monitor()",
            "permission_system": "get_permission_system()",
        },
    }
