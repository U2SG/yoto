import unittest
import json
import time
import threading
import redis
import uuid  # <<-- 引入UUID来创建唯一、隔离的资源
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable
import sys
import os
from unittest.mock import MagicMock

# --- 动态添加项目根目录到Python路径 ---
# 这确保了无论从哪里运行测试，都能找到app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- 核心模块导入 ---
# 将所有被测模块的导入放在这里
from app.core.permission_events import (
    EventPublisher,
    EventSubscriber,
    create_event,
    RESILIENCE_EVENTS_CHANNEL,
)
from app.core.permission_resilience import (
    circuit_breaker,
    set_circuit_breaker_config,
    get_circuit_breaker_state,
    get_or_create_circuit_breaker,  # <<-- 导入工厂函数
    clear_resilience_instances,  # <<-- 导入清理函数
)

# --- 测试配置 ---
# 最好有一个集中的地方管理测试配置
TEST_REDIS_HOST = "localhost"
TEST_REDIS_PORT = 6379

# ======================================================================
#  单元测试 (Unit Tests) - 快速、无外部依赖
# ======================================================================


class TestEventPublisherUnit(unittest.TestCase):
    """单元测试: EventPublisher 的行为。"""

    def setUp(self):
        self.mock_redis_client = MagicMock(spec=redis.Redis)
        self.publisher = EventPublisher(self.mock_redis_client)

    def test_publish_success_formats_and_sends_message(self):
        """测试: publish 方法是否能正确格式化事件并调用 redis.publish。"""
        # ... (您原来的单元测试代码是完美的，无需修改) ...
        test_channel = "test:channel"
        test_event_name = "test.event"
        test_payload = {"user_id": 123, "success": True}
        test_source = "test_module"
        self.publisher.publish(test_channel, test_event_name, test_payload, test_source)
        self.mock_redis_client.publish.assert_called_once()
        # ... (其他断言) ...


class TestEventSubscriberUnit(unittest.TestCase):
    """单元测试: EventSubscriber 的行为。"""

    def setUp(self):
        self.mock_redis_client = MagicMock(spec=redis.Redis)
        self.mock_pubsub = MagicMock()
        self.mock_redis_client.pubsub.return_value = self.mock_pubsub
        self.mock_callback = MagicMock()
        self.subscriber = EventSubscriber(self.mock_redis_client)

    # ... (您所有的 EventSubscriber 单元测试都非常出色，无需修改) ...
    def test_listen_loop_processes_messages_and_calls_callback(self):
        # ...
        pass


# ======================================================================
#  集成测试 (Integration Tests) - 慢速、依赖真实Redis
# ======================================================================


# 使用 unittest.skipUnless 来确保只有在Redis可用时才运行集成测试
@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS", "false").lower() == "true",
    "Skipping integration tests. Set RUN_INTEGRATION_TESTS=true to run.",
)
class TestIntegrationEventBus(unittest.TestCase):
    """
    终极版集成测试：使用动态、隔离的资源和确定性同步。
    """

    def setUp(self):
        """
        为每个测试用例建立真实的Redis连接，并创建唯一的资源名称。
        """
        # <<-- 核心改变 1: 为每个测试用例创建唯一的、隔离的资源名称
        self.run_id = str(uuid.uuid4())
        self.test_channel = f"test-channel:{self.run_id}"
        self.breaker_name = f"test-breaker:{self.run_id}"
        self.test_queue = Queue()

        print(f"\n--- Starting Test Case: {self._testMethodName} ---")
        print(
            f"Using isolated resources: Channel='{self.test_channel}', Breaker='{self.breaker_name}'"
        )

        try:
            self.publisher_client = redis.Redis(
                host=TEST_REDIS_HOST, port=TEST_REDIS_PORT, decode_responses=False
            )
            self.publisher_client.ping()
            self.subscriber_client = redis.Redis(
                host=TEST_REDIS_HOST, port=TEST_REDIS_PORT, decode_responses=False
            )

            self.publisher = EventPublisher(self.publisher_client)
            self.subscriber = EventSubscriber(self.subscriber_client)
            print(f"Redis connection successful: {TEST_REDIS_HOST}:{TEST_REDIS_PORT}")

        except redis.exceptions.ConnectionError as e:
            self.fail(
                f"Could not connect to Redis server at {TEST_REDIS_HOST}:{TEST_REDIS_PORT}. Error: {e}"
            )

    def tearDown(self):
        """
        清理：优雅地停止线程，并从Redis中删除所有与本次测试相关的键。
        """
        # 步骤 1: 优雅地停止订阅者线程
        if hasattr(self, "subscriber") and self.subscriber:
            self.subscriber.stop()

        # <<-- 核心改变 2: 清理测试在Redis中留下的所有状态
        try:
            # 找到所有与本次测试运行相关的键并删除，确保下一个测试是干净的
            keys_to_delete = self.publisher_client.keys(f"*:{self.run_id}*")
            if keys_to_delete:
                self.publisher_client.delete(*keys_to_delete)
                print(
                    f"✓ Cleaned up {len(keys_to_delete)} Redis keys for run_id: {self.run_id}"
                )
        except Exception as e:
            print(f"Warning during Redis cleanup (ignorable): {e}")

        # <<-- 核心改变 3: 清理Python进程内的韧性组件单例缓存
        # 这是为了确保下一个测试用例的 get_or_create_* 函数返回一个全新的对象
        clear_resilience_instances()
        print("✓ Cleared in-process resilience instances.")

        # 步骤 4: 关闭Redis连接
        if hasattr(self, "publisher_client"):
            self.publisher_client.close()
        if hasattr(self, "subscriber_client"):
            self.subscriber_client.close()

        print(f"--- Finished Test Case: {self._testMethodName} ---")

    def test_end_to_end_pubsub_communication(self):
        """测试：端到端通信（使用隔离频道和确定性同步）。"""

        def test_callback(event_data: Dict[str, Any]):
            self.test_queue.put(event_data)

        # 1. 订阅唯一的测试频道
        self.subscriber.subscribe(self.test_channel, test_callback)
        self.subscriber.start()

        # 2. 等待就绪信号，而不是猜测时间
        ready = self.subscriber.ready_event.wait(timeout=2.0)
        self.assertTrue(ready, "Subscriber did not become ready in time.")

        # 3. 在确认订阅者就绪后，发布到唯一的测试频道
        test_payload = {"data": "end-to-end"}
        self.publisher.publish(
            self.test_channel, "e2e.test", test_payload, "e2e_source"
        )

        # 4. 等待并验证结果
        try:
            received_event = self.test_queue.get(timeout=3.0)
        except Empty:
            self.fail("Timed out waiting for event message.")
        self.assertEqual(received_event["payload"], test_payload)
        print("✓ End-to-end communication test passed.")

    def test_circuit_breaker_opens_and_publishes_event_deterministically(self):
        """测试：熔断器在达到阈值时，能原子性地开启并发布一个事件。"""
        # 1. 配置一个唯一的、本次测试专用的熔断器
        set_circuit_breaker_config(
            self.breaker_name, failure_threshold=2, recovery_timeout=60
        )

        # 2. 定义一个简单的、会失败的函数
        @circuit_breaker(self.breaker_name)
        def failing_function():
            raise ValueError("Intentional failure")

        # 3. 订阅事件，并使用 Event 进行同步
        event_received_signal = threading.Event()

        def callback(event_data: Dict[str, Any]):
            # 只处理与我们本次测试相关的熔断器事件
            if event_data.get("payload", {}).get("name") == self.breaker_name:
                self.test_queue.put(event_data)
                event_received_signal.set()

        self.subscriber.subscribe(RESILIENCE_EVENTS_CHANNEL, callback)
        self.subscriber.start()
        ready = self.subscriber.ready_event.wait(timeout=2.0)
        self.assertTrue(ready, "Subscriber did not become ready in time.")

        # 4. 同步地、在主线程中触发失败
        # 第一次失败
        with self.assertRaises(ValueError):
            failing_function()

        state_after_1 = get_circuit_breaker_state(self.breaker_name)
        self.assertEqual(state_after_1["failure_count"], 1)
        self.assertEqual(state_after_1["state"], "closed")

        # 第二次失败 -> 应该触发熔断并发布事件
        with self.assertRaises(ValueError):
            failing_function()

        # 5. 等待事件到达的“信号”，而不是猜测时间
        event_arrived = event_received_signal.wait(timeout=2.0)
        self.assertTrue(
            event_arrived, "Timed out waiting for the circuit breaker 'opened' event."
        )

        # 6. 从队列中获取事件并验证
        received_event = self.test_queue.get_nowait()
        self.assertEqual(
            received_event["event_name"], "resilience.circuit_breaker.opened"
        )
        self.assertEqual(received_event["payload"]["name"], self.breaker_name)
        self.assertEqual(received_event["payload"]["state"], "open")

        # 7. 验证熔断器的最终状态
        final_state = get_circuit_breaker_state(self.breaker_name)
        self.assertEqual(final_state["state"], "open")
        self.assertEqual(final_state["failure_count"], 2)

        print("✓ Circuit breaker event test passed.")


if __name__ == "__main__":
    # 运行所有测试
    # 要运行集成测试，请在命令行设置环境变量：
    # (PowerShell) $env:RUN_INTEGRATION_TESTS="true"
    # (bash/zsh)   export RUN_INTEGRATION_TESTS=true
    unittest.main(verbosity=2)
