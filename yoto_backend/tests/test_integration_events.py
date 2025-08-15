import unittest
import json
import time
import threading
import redis
import uuid  # <<-- 引入UUID来创建唯一频道
from queue import Queue, Empty
from typing import Dict, Any
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置和权限事件模块
from config import TestingConfig
from app.core.permission.permission_events import (
    EventPublisher,
    EventSubscriber,
    create_event,
    RESILIENCE_EVENTS_CHANNEL,
)


class TestIntegrationEventBus(unittest.TestCase):
    """
    集成测试：测试 EventPublisher 和 EventSubscriber 在真实 Redis 环境下的交互。
    使用TestingConfig进行配置管理。
    """

    def setUp(self):
        """
        使用TestingConfig连接到Redis服务器，并初始化发布者和订阅者。
        """
        # ... (Redis连接部分保持不变) ...

        # <<-- 核心改变: 为每个测试用例创建唯一的频道名
        self.test_channel = f"test-channel:{uuid.uuid4()}"
        print(f"Using isolated test channel: {self.test_channel}")

        # 使用TestingConfig获取Redis配置
        self.config = TestingConfig()
        self.test_queue = Queue()  # 用于在订阅者线程和主线程之间传递数据

        try:
            # 从配置中解析Redis连接信息
            redis_url = self.config.CELERY_BROKER_URL
            if redis_url.startswith("redis://"):
                # 解析redis://localhost:6379/0格式
                redis_parts = redis_url.replace("redis://", "").split("/")
                host_port = redis_parts[0].split(":")
                self.redis_host = host_port[0]
                self.redis_port = int(host_port[1]) if len(host_port) > 1 else 6379
            else:
                # 默认配置
                self.redis_host = "localhost"
                self.redis_port = 6379

            # 使用一个独立的连接用于发布和订阅，避免线程安全问题
            self.publisher_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,  # 修复解码问题
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.publisher_client.ping()

            # 订阅者使用单独的连接
            self.subscriber_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,  # 修复解码问题
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            self.publisher = EventPublisher(self.publisher_client)
            self.subscriber = EventSubscriber(self.subscriber_client)

            # 确保 Redis 连接池已初始化，并且连接是活跃的
            print(
                f"\nRedis connection successful using config: {self.redis_host}:{self.redis_port}"
            )

        except redis.exceptions.ConnectionError as e:
            self.fail(
                f"Could not connect to Redis server at {self.redis_host}:{self.redis_port}. "
                f"Is Redis running? Error: {e}"
            )
        except Exception as e:
            self.fail(f"Unexpected error during Redis setup: {e}")

    def tearDown(self):
        """
        清理测试状态：停止订阅线程，关闭 Redis 连接，并清理测试数据。
        """
        try:
            # 步骤1： 优雅地停止订阅者线程
            if hasattr(self, "subscriber") and self.subscriber:
                self.subscriber.stop()

            # 步骤2： 关闭Redis连接
            if hasattr(self, "publisher_client"):
                self.publisher_client.close()
            if hasattr(self, "subscriber_client"):
                self.subscriber_client.close()

            print("✓ Teardown complete. All resources released.")

        except Exception as e:
            # 忽略清理过程中的错误，因为连接可能已经关闭
            print(f"清理过程中的警告（可忽略）: {e}")

    def test_end_to_end_pubsub_communication(self):
        """测试：端到端通信（使用隔离频道）。"""

        def test_callback(event_data: Dict[str, Any]):
            self.test_queue.put(event_data)

        # 1. 订阅唯一的测试频道
        self.subscriber.subscribe(self.test_channel, test_callback)
        self.subscriber.start()

        # 2. 等待就绪信号
        ready = self.subscriber.ready_event.wait(timeout=2.0)
        self.assertTrue(ready, "Subscriber did not become ready in time.")

        # 3. 发布到唯一的测试频道
        test_payload = {"data": "end-to-end"}
        self.publisher.publish(
            self.test_channel, "e2e.test", test_payload, "e2e_source"
        )

        # 4. 等待并验证结果 (逻辑不变)
        try:
            received_event = self.test_queue.get(timeout=3.0)
        except Empty:
            self.fail("Timed out waiting for event message.")
        self.assertEqual(received_event["payload"], test_payload)

    # 7. (高级测试) 测试错误处理
    def test_json_decode_error_in_callback_is_handled(self):
        """
        测试：如果 Pub/Sub 回调函数处理过程中发生错误，监听线程是否能处理异常并继续运行。
        """

        # 1. 定义一个会抛出异常的回调函数
        def broken_callback(event_data: Dict[str, Any]):
            raise ValueError("Intentional callback error")

        # 2. 订阅并启动监听线程
        self.subscriber.subscribe(RESILIENCE_EVENTS_CHANNEL, broken_callback)
        self.subscriber.start()
        time.sleep(0.1)

        # 3. 发布一个事件
        self.publisher.publish(
            RESILIENCE_EVENTS_CHANNEL, "error.test", {}, "test_source"
        )

        # 4. 等待一段时间，确保异常发生
        time.sleep(1.0)

        # 5. 验证订阅者线程仍然存活（说明异常被正确处理）
        # 如果异常没有被正确处理，线程会崩溃
        self.assertTrue(
            self.subscriber.thread.is_alive(),
            "订阅者线程应该仍然存活，说明异常被正确处理",
        )

        print("✓ 错误处理测试通过：异常被正确处理，线程继续运行")

    # 8. (高级测试) 测试回调异常不会使监听线程崩溃
    def test_callback_exception_does_not_crash_subscriber_thread(self):
        """测试：回调异常不会使监听线程崩溃（确定性版本）。"""
        # 使用 threading.Event 来同步，替代 time.sleep
        first_call_event = threading.Event()
        second_call_event = threading.Event()

        def multi_step_callback(event_data: Dict[str, Any]):
            # 第一次调用时，抛出异常并设置第一个信号
            if event_data["payload"]["step"] == 1:
                first_call_event.set()
                raise ValueError("Intentional callback error")
            # 第二次调用时，放入队列并设置第二个信号
            elif event_data["payload"]["step"] == 2:
                self.test_queue.put(event_data)
                second_call_event.set()

        # 订阅并启动
        self.subscriber.subscribe(self.test_channel, multi_step_callback)
        self.subscriber.start()
        ready = self.subscriber.ready_event.wait(timeout=2.0)
        self.assertTrue(ready, "Subscriber did not become ready.")

        # 发布第一个消息，预期会触发异常
        with self.assertLogs("app.core.permission.permission_events", level="ERROR"):
            self.publisher.publish(
                self.test_channel, "error.test", {"step": 1}, "test_source"
            )
            # 等待，直到我们确认第一个回调已经被调用
            self.assertTrue(
                first_call_event.wait(timeout=1.0), "First callback was never called."
            )

        # 验证线程仍然存活
        self.assertTrue(
            self.subscriber.thread.is_alive(),
            "Subscriber thread crashed after exception.",
        )

        # 发布第二个消息
        self.publisher.publish(
            self.test_channel, "success.test", {"step": 2}, "test_source"
        )

        # 等待第二个回调完成
        self.assertTrue(
            second_call_event.wait(timeout=1.0), "Second callback was never called."
        )

        # 验证第二个消息被成功接收
        received_event = self.test_queue.get_nowait()
        self.assertEqual(received_event["payload"]["step"], 2)
        print("✓ 错误处理测试通过：线程在异常后继续运行。")

    # 9. (高级测试) 测试熔断器跳闸时事件发布机制
    def test_circuit_breaker_event_trigger(self):
        """
        测试：熔断器跳闸时事件发布机制
        在一个线程中循环调用被装饰的函数，直到熔断器跳闸。
        在主线程中，等待一小段时间，然后断言mock的回调函数被调用了，
        并且收到的事件内容与预期一致。
        """
        from app.core.permission.permission_resilience import (
            circuit_breaker,
            set_circuit_breaker_config,
        )

        # 1. 清理之前的熔断器状态并设置新配置
        from app.core.permission.permission_resilience import (
            get_resilience_controller,
            CircuitBreakerConfig,
        )

        # 清理之前的熔断器状态
        controller = get_resilience_controller()
        controller.redis_client.delete("circuit_breaker:test_circuit_breaker:state")
        controller.redis_client.delete(
            "circuit_breaker:test_circuit_breaker:failure_count"
        )
        controller.redis_client.delete(
            "circuit_breaker:test_circuit_breaker:last_failure_time"
        )
        controller.redis_client.delete(
            "circuit_breaker:test_circuit_breaker:half_open_calls"
        )

        # 设置熔断器配置 - 低阈值以便快速触发
        config = CircuitBreakerConfig(
            name="test_circuit_breaker",
            failure_threshold=2,  # 2次失败就跳闸
            recovery_timeout=0.1,  # 快速恢复
        )
        success = controller.set_circuit_breaker_config("test_circuit_breaker", config)
        print(f"熔断器配置设置结果: {success}")

        # 验证配置是否正确设置
        from app.core.permission.permission_resilience import get_circuit_breaker_state

        initial_state = get_circuit_breaker_state("test_circuit_breaker")
        print(f"初始熔断器状态: {initial_state}")

        # 2. 定义会失败的函数
        call_count = [0]  # 使用列表来确保可变性

        @circuit_breaker("test_circuit_breaker")
        def failing_function():
            call_count[0] += 1
            print(f"函数被调用，当前次数: {call_count[0]}")
            raise Exception(f"模拟失败 #{call_count[0]}")

        # 3. 订阅熔断器事件
        def circuit_breaker_callback(event_data: Dict[str, Any]):
            self.test_queue.put(event_data)

        self.subscriber.subscribe(
            RESILIENCE_EVENTS_CHANNEL, circuit_breaker_callback
        )  # 订阅熔断器事件频道
        self.subscriber.start()

        # 4. 等待订阅者就绪
        ready = self.subscriber.ready_event.wait(timeout=2.0)
        self.assertTrue(ready, "订阅者未及时就绪")

        # 5. 在后台线程中循环调用失败函数，直到熔断器跳闸
        stop_event = threading.Event()

        def trigger_circuit_breaker():
            local_call_count = 0
            while not stop_event.is_set() and local_call_count < 10:  # 增加调用次数
                try:
                    failing_function()
                    local_call_count += 1
                    print(f"后台线程调用次数: {local_call_count}")
                except Exception as e:
                    print(f"后台线程异常: {e}")
                    pass  # 忽略异常，继续调用
                time.sleep(0.01)  # 短暂延迟

        trigger_thread = threading.Thread(target=trigger_circuit_breaker)
        trigger_thread.daemon = True  # 设置为守护线程，主线程结束时自动停止
        trigger_thread.start()

        # 6. 等待一小段时间，让熔断器跳闸并发布事件
        time.sleep(0.2)  # 增加等待时间

        # 检查熔断器状态
        current_state = get_circuit_breaker_state("test_circuit_breaker")
        print(f"熔断器当前状态: {current_state}")
        print(f"全局调用次数: {call_count[0]}")

        # 停止后台线程
        stop_event.set()
        trigger_thread.join(timeout=1.0)  # 等待线程结束，最多1秒

        # 7. 验证收到了熔断器开启事件
        try:
            received_event = self.test_queue.get(timeout=3.0)
        except Empty:
            self.fail("超时等待熔断器事件")

        # 8. 验证事件内容
        self.assertEqual(
            received_event["event_name"], "resilience.circuit_breaker.opened"
        )
        self.assertEqual(received_event["source_module"], "resilience.circuit_breaker")
        self.assertIn("payload", received_event)

        payload = received_event["payload"]
        self.assertEqual(payload["name"], "test_circuit_breaker")
        self.assertEqual(payload["state"], "open")

        # 9. 验证调用次数确实超过了阈值
        self.assertGreaterEqual(call_count[0], 2, "应该至少调用了2次才触发熔断器")

        print("✓ 熔断器事件测试通过：成功捕获到熔断器开启事件")


if __name__ == "__main__":
    # 确保在运行测试前 Redis 服务器已启动
    unittest.main()
