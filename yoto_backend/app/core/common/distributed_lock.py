"""
通用分布式锁模块

提供基于Redis的分布式锁实现，支持超时、重试和自动续期。
不依赖任何其他自定义模块，只依赖redis和标准库。
"""

import os
import time
import logging
import threading
import redis
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class OptimizedDistributedLock:
    """
    优化的分布式锁，基于Redis实现，支持超时、重试和自动续期。

    特性：
    - 基于Redis的分布式锁实现
    - 支持自动续期，防止长时间操作时锁过期
    - 支持超时和重试机制
    - 线程安全的实现
    - 支持上下文管理器（with语句）
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_key: str,
        timeout: float = 2.0,
        retry_interval: float = 0.02,
        retry_count: int = 3,
    ):
        """
        初始化分布式锁

        Args:
            redis_client: Redis客户端实例
            lock_key: 锁的键名
            timeout: 锁超时时间（秒）
            retry_interval: 重试间隔（秒）
            retry_count: 重试次数
        """
        self.redis_client = redis_client
        self.lock_key = f"lock:opt:{lock_key}"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.retry_count = retry_count

        self.lock_value = None
        self.renew_task = None
        self._stop_renew_event = threading.Event()

    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire():
            raise Exception(f"无法获取优化分布式锁: {self.lock_key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()

    def acquire(self) -> bool:
        """
        尝试获取锁（非阻塞）

        Returns:
            bool: 是否成功获取锁
        """
        if not self.redis_client:
            logger.warning("无法获取分布式锁：Redis客户端不可用")
            return False

        # 生成唯一的锁值
        self.lock_value = f"{os.getpid()}:{threading.get_ident()}:{time.time_ns()}"

        # 尝试获取锁
        try:
            result = self.redis_client.set(
                self.lock_key, self.lock_value, nx=True, ex=int(self.timeout)
            )
            if result:
                self._start_renewal_task()
                logger.debug(f"成功获取分布式锁: {self.lock_key}")
                return True
        except Exception as e:
            logger.error(f"获取分布式锁失败: {self.lock_key}, 错误: {e}", exc_info=True)

        self.lock_value = None
        return False

    def release(self) -> bool:
        """
        释放锁（原子操作）

        Returns:
            bool: 是否成功释放锁
        """
        self._stop_renewal_task()

        if not self.redis_client or not self.lock_value:
            return True

        # Lua脚本确保只有锁的持有者才能删除它
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            result = self.redis_client.eval(
                lua_script, 1, self.lock_key, self.lock_value
            )
            if result:
                logger.debug(f"成功释放分布式锁: {self.lock_key}")
            else:
                logger.warning(f"释放分布式锁失败，可能锁已过期: {self.lock_key}")
        except Exception as e:
            logger.error(f"释放分布式锁失败: {self.lock_key}, 错误: {e}", exc_info=True)
        finally:
            self.lock_value = None

        return True

    def _start_renewal_task(self):
        """启动锁续期任务"""
        if self.renew_task and self.renew_task.is_alive():
            return

        self._stop_renew_event.clear()
        self.renew_task = threading.Thread(
            target=self._renew_lock_periodically, daemon=True
        )
        self.renew_task.start()
        logger.debug(f"锁 {self.lock_key} 的续期任务已启动")

    def _renew_lock_periodically(self):
        """定期续期锁"""
        while not self._stop_renew_event.is_set():
            try:
                # 检查锁是否仍然被持有
                if self.redis_client and self.lock_value:
                    current_value = self.redis_client.get(self.lock_key)
                    # 处理不同数据类型
                    if current_value:
                        if isinstance(current_value, bytes):
                            current_value_str = current_value.decode()
                        else:
                            current_value_str = str(current_value)

                        if current_value_str == self.lock_value:
                            # 锁仍然被持有，尝试续期
                            self.redis_client.expire(self.lock_key, int(self.timeout))
                            logger.debug(f"锁 {self.lock_key} 续期成功")
                        else:
                            # 锁已过期或被释放，退出续期任务
                            logger.debug(
                                f"锁 {self.lock_key} 已过期或被释放，退出续期任务"
                            )
                            break
                    else:
                        # 锁已过期或被释放，退出续期任务
                        logger.debug(f"锁 {self.lock_key} 已过期或被释放，退出续期任务")
                        break
                else:
                    logger.warning(
                        f"Redis客户端不可用或锁值无效，无法续期锁 {self.lock_key}"
                    )
                    break
            except Exception as e:
                logger.error(f"锁续期失败: {self.lock_key}, 错误: {e}", exc_info=True)
                break

            # 等待一段时间后再次尝试
            time.sleep(self.timeout / 2)

    def _stop_renewal_task(self):
        """停止锁续期任务"""
        self._stop_renew_event.set()
        if self.renew_task and self.renew_task.is_alive():
            self.renew_task.join(timeout=1.0)
            logger.debug(f"锁 {self.lock_key} 的续期任务已停止")


# 工厂函数
def create_optimized_distributed_lock(
    redis_client: redis.Redis,
    lock_key: str,
    timeout: float = 2.0,
    retry_interval: float = 0.02,
    retry_count: int = 3,
) -> OptimizedDistributedLock:
    """
    创建优化的分布式锁实例

    Args:
        redis_client: Redis客户端实例
        lock_key: 锁的键名
        timeout: 锁超时时间（秒）
        retry_interval: 重试间隔（秒）
        retry_count: 重试次数

    Returns:
        OptimizedDistributedLock: 优化的分布式锁实例
    """
    return OptimizedDistributedLock(
        redis_client=redis_client,
        lock_key=lock_key,
        timeout=timeout,
        retry_interval=retry_interval,
        retry_count=retry_count,
    )
