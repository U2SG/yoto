"""
通用模块

提供系统级别的通用功能，如分布式锁、缓存等。
这些模块不依赖任何其他自定义模块，只依赖标准库和第三方库。
"""

from .distributed_lock import (
    OptimizedDistributedLock,
    create_optimized_distributed_lock,
)

__all__ = ["OptimizedDistributedLock", "create_optimized_distributed_lock"]
