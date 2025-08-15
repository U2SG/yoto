# 主事件频道，所有韧性相关的事件都发布到这里
RESILIENCE_EVENTS_CHANNEL = "permissions:resilience:events"

# 可以预留未来的控制频道
CONTROL_COMMANDS_CHANNEL = "permissions:control:commands"

# in permission_events.py
import os
import socket
from typing import Dict, Any
import time
import json
import redis
import logging

logger = logging.getLogger(__name__)
from collections import defaultdict
from typing import Callable
import threading


def create_event(
    event_name: str, payload: Dict[str, Any], source_module: str
) -> Dict[str, Any]:
    """创建一个标准化的、结构化的事件。"""
    return {
        "event_name": event_name,
        "timestamp": time.time(),
        "source_module": source_module,
        "hostname": socket.gethostname(),  # 关键调试信息
        "pid": os.getpid(),  # 关键调试信息
        "payload": payload,
    }


# in permission_events.py


class EventPublisher:
    def __init__(self, redis_client: redis.Redis):
        if not redis_client:
            raise ValueError("EventPublisher requires a valid Redis client.")
        self.redis_client = redis_client

    def publish(
        self, channel: str, event_name: str, payload: Dict[str, Any], source_module: str
    ):
        try:
            event_data = create_event(event_name, payload, source_module)
            message = json.dumps(event_data)
            self.redis_client.publish(channel, message)
            logger.debug(f"Published event '{event_name}' to channel '{channel}'.")
        except Exception as e:
            logger.error(
                f"Failed to publish event '{event_name}' to channel '{channel}': {e}"
            )


class EventSubscriber:
    def __init__(self, redis_client: redis.Redis):
        if not redis_client:
            raise ValueError("EventSubscriber requires a valid Redis client.")
        self.redis_client = redis_client
        # 关键修改：不再忽略订阅消息！
        self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=False)
        self.callbacks = defaultdict(list)
        self.thread = None
        self.stop_event = threading.Event()

        # <<-- 新增: 用于同步的就绪信号
        self.ready_event = threading.Event()

    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]):
        """订阅一个频道，并为所有事件注册一个回调。"""
        self.pubsub.subscribe(channel)
        self.callbacks[channel].append(callback)
        # 安全地获取回调函数名称，处理Mock对象的情况
        logger.info(f"Callback {callback.__name__} subscribed to channel {channel}")

    def _listen(self):
        logger.info("Event subscriber thread started.")
        try:
            while not self.stop_event.is_set():
                message = self.pubsub.get_message(timeout=0.1)
                if message is None:
                    continue

                # <<-- 核心逻辑改变: 处理不同类型的消息
                message_type = message.get("type")

                if message_type == "subscribe":
                    # 收到了订阅成功的确认消息！
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    logger.info(f"Successfully subscribed to channel: {channel}")
                    # 发出“就绪”信号，通知主线程可以继续了
                    self.ready_event.set()

                elif message_type == "message":
                    # 这才是我们真正要处理的业务消息
                    try:
                        channel = message["channel"].decode("utf-8")
                        data = json.loads(message["data"].decode("utf-8"))

                        if channel in self.callbacks:
                            for callback in self.callbacks[channel]:
                                try:
                                    callback(data)
                                except Exception as e:
                                    logger.error(
                                        f"Error executing callback for event {data.get('event_name')}: {e}"
                                    )
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning(f"Failed to decode message from Pub/Sub: {e}")

        except Exception as e:
            if not self.stop_event.is_set():
                logger.error(
                    f"Critical error in subscriber listen loop: {e}", exc_info=True
                )

        finally:
            logger.info("Event subscriber thread gracefully stopped.")
            # 线程退出前，最后清理一下订阅
            try:
                self.pubsub.unsubscribe()
                self.pubsub.punsubscribe()
                self.pubsub.close()
            except Exception as e:
                logger.debug(f"Error during final pubsub cleanup: {e}")

    def start(self):
        """启动后台监听线程。"""
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()  # <<-- 新增: 确保启动时信号旗是清除的
            self.ready_event.clear()  # <<-- 新增: 确保每次启动时，就绪信号是清除的
            self.thread = threading.Thread(target=self._listen, daemon=True)
            self.thread.start()

    def stop(self):
        """
        优雅地停止后台监听线程的最终版。
        """
        if self.thread and self.thread.is_alive():
            # 1. 发出停止信号
            self.stop_event.set()

            # 2. 取消所有订阅。这将导致 listen()/get_message() 循环
            # 在下一次迭代中收到一个 'unsubscribe' 类型的消息（如果我们不忽略它），
            # 或者在超时后正常退出循环。这比 close() 更优雅。
            try:
                self.pubsub.unsubscribe()
                self.pubsub.punsubscribe()  # 确保模式订阅也被取消
            except redis.exceptions.ConnectionError:
                # 如果连接已经断开，忽略错误
                pass

            # 3. 等待线程自然结束
            self.thread.join(timeout=1.0)
            if self.thread.is_alive():
                logger.warning("Subscriber thread did not stop in time.")
            else:
                logger.info("Subscriber thread has been joined successfully.")

            # 4. 最后，在线程完全结束后，再关闭 pubsub 对象
            try:
                self.pubsub.close()
            except redis.exceptions.ConnectionError:
                pass
