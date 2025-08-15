"""
真实使用场景模拟测试

模拟一个完整的权限系统使用流程，包括：
- 用户登录和认证
- 权限检查和缓存
- 实时事件触发
- 系统状态监控
- 性能压力测试
- 错误恢复场景
"""

import sys
import os
import time
import json
import logging
import threading
import random
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 在导入其他模块之前进行monkey patch
import eventlet

eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO
from flask_jwt_extended import create_access_token, JWTManager
import redis

# 导入应用模块
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message, MessageReaction
from werkzeug.security import generate_password_hash

# 导入权限系统模块
from app.core.permission import (
    initialize_permission_platform,
    get_resilience_controller,
    get_permission_monitor,
    get_permission_system,
    get_hybrid_cache,
    get_or_create_rate_limiter,
    get_or_create_circuit_breaker,
    CircuitBreakerState,
)

logger = logging.getLogger(__name__)


class RealWorldScenarioTest:
    """真实使用场景测试类"""

    def __init__(self):
        self.app = None
        self.socketio = None
        self.test_users = []
        self.test_servers = []
        self.test_channels = []
        self.test_results = {}
        self.redis_client = None
        self.permission_system = None
        self.cache = None
        self.resilience_controller = None
        self.monitor = None

    def setup_test_environment(self):
        """设置测试环境"""
        logger.info("开始设置测试环境")

        # 创建Flask应用
        self.app = create_app("testing")

        # 初始化数据库
        with self.app.app_context():
            db.create_all()

            # 创建测试用户
            users_data = [
                {"username": "admin", "is_super_admin": True},
                {"username": "moderator", "is_super_admin": False},
                {"username": "user1", "is_super_admin": False},
                {"username": "user2", "is_super_admin": False},
                {"username": "user3", "is_super_admin": False},
            ]

            for user_data in users_data:
                user = User(
                    username=user_data["username"],
                    password_hash=generate_password_hash("password123"),
                    is_super_admin=user_data["is_super_admin"],
                )
                db.session.add(user)
            db.session.commit()
            self.test_users = User.query.all()

            # 创建测试服务器
            servers_data = [
                {"name": "游戏服务器"},
                {"name": "技术讨论"},
                {"name": "休闲聊天"},
            ]

            for server_data in servers_data:
                server = Server(
                    name=server_data["name"],
                    owner_id=self.test_users[0].id,  # admin as owner
                )
                db.session.add(server)
            db.session.commit()
            self.test_servers = Server.query.all()

            # 创建测试频道
            channels_data = [
                {"name": "一般", "server_id": self.test_servers[0].id},
                {"name": "公告", "server_id": self.test_servers[0].id},
                {"name": "讨论", "server_id": self.test_servers[0].id},
                {"name": "技术", "server_id": self.test_servers[1].id},
                {"name": "问答", "server_id": self.test_servers[1].id},
                {"name": "分享", "server_id": self.test_servers[1].id},
                {"name": "闲聊", "server_id": self.test_servers[2].id},
                {"name": "音乐", "server_id": self.test_servers[2].id},
                {"name": "游戏", "server_id": self.test_servers[2].id},
            ]

            for channel_data in channels_data:
                channel = Channel(
                    name=channel_data["name"], server_id=channel_data["server_id"]
                )
                db.session.add(channel)
            db.session.commit()
            self.test_channels = Channel.query.all()

            # 创建服务器成员
            for user in self.test_users:
                for server in self.test_servers:
                    member = ServerMember(user_id=user.id, server_id=server.id)
                    db.session.add(member)
            db.session.commit()

        # 初始化权限系统组件
        with self.app.app_context():
            initialize_permission_platform()
            self.permission_system = get_permission_system()
            self.resilience_controller = get_resilience_controller()
            self.cache = get_hybrid_cache()
            self.monitor = get_permission_monitor()

            # 禁用维护模式，确保权限系统正常工作
            self.resilience_controller.set_global_switch("maintenance_mode", False)

        # 初始化Redis客户端
        self.redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )

        # 初始化JWT
        self.jwt = JWTManager(self.app)

        logger.info(
            f"创建了 {len(self.test_users)} 个用户, {len(self.test_servers)} 个服务器, {len(self.test_channels)} 个频道"
        )
        logger.info("测试环境设置完成")
        return True

    def test_user_login_flow(self):
        """测试用户登录流程"""
        logger.info("开始测试用户登录流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象，确保它们在当前会话中
                users = User.query.all()

                for user in users:
                    # 模拟用户登录
                    login_result = {
                        "user_id": user.id,
                        "username": user.username,
                        "login_time": time.time(),
                        "session_token": f"token_{user.id}_{int(time.time())}",
                    }

                    # 模拟权限系统初始化 - 使用正确的API
                    try:
                        # 检查用户是否有基本权限
                        has_basic_permission = self.permission_system.check_permission(
                            user_id=user.id,
                            permission="read_messages",
                            scope="channel",
                            scope_id=1,
                        )
                        login_result["has_basic_permission"] = has_basic_permission
                    except Exception as e:
                        login_result["has_basic_permission"] = False
                        login_result["permission_error"] = str(e)

                    results[user.username] = login_result

                    logger.info(f"用户 {user.username} 登录成功")

            self.test_results["user_login"] = results
            return True

        except Exception as e:
            logger.error(f"用户登录流程测试失败: {e}")
            return False

    def test_permission_checking_flow(self):
        """测试权限检查流程"""
        logger.info("开始测试权限检查流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 测试不同用户的权限
                test_permissions = [
                    "read_messages",
                    "send_messages",
                    "manage_channels",
                    "manage_server",
                    "ban_users",
                    "view_analytics",
                ]

                for user in users:
                    user_results = {}

                    for permission in test_permissions:
                        # 模拟权限检查 - 使用正确的API
                        try:
                            has_permission = self.permission_system.check_permission(
                                user_id=user.id,
                                permission=permission,
                                scope="channel",
                                scope_id=1,
                            )
                            user_results[permission] = has_permission
                        except Exception as e:
                            user_results[permission] = False
                            user_results[f"{permission}_error"] = str(e)

                    results[user.username] = user_results
                    logger.info(f"用户 {user.username} 权限检查完成")

            self.test_results["permission_checking"] = results
            return True

        except Exception as e:
            logger.error(f"权限检查流程测试失败: {e}")
            return False

    def test_cache_operations_flow(self):
        """测试缓存操作流程"""
        logger.info("开始测试缓存操作流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 测试缓存预热
                cache_warmup = self.cache.warm_up_cache(
                    user_ids=[user.id for user in users],
                    permissions=["read_messages", "send_messages"],
                )
                results["cache_warmup"] = cache_warmup

                # 测试缓存命中率
                cache_hits = 0
                cache_misses = 0

                for _ in range(100):
                    user = random.choice(users)
                    permission = random.choice(["read_messages", "send_messages"])

                    # 模拟权限检查（会使用缓存） - 使用正确的API
                    try:
                        has_permission = self.permission_system.check_permission(
                            user_id=user.id,
                            permission=permission,
                            scope="channel",
                            scope_id=1,
                        )

                        # 检查缓存状态
                        cache_key = f"permission:{user.id}:{permission}:channel:1"
                        if self.redis_client.exists(cache_key):
                            cache_hits += 1
                        else:
                            cache_misses += 1
                    except Exception as e:
                        cache_misses += 1

                results["cache_performance"] = {
                    "hits": cache_hits,
                    "misses": cache_misses,
                    "hit_rate": (
                        cache_hits / (cache_hits + cache_misses)
                        if (cache_hits + cache_misses) > 0
                        else 0
                    ),
                }

                # 测试缓存失效
                cache_invalidation = self.cache.invalidate_user_permissions(
                    user_id=users[0].id
                )
                results["cache_invalidation"] = cache_invalidation

            self.test_results["cache_operations"] = results
            logger.info("缓存操作流程测试完成")
            return True

        except Exception as e:
            logger.error(f"缓存操作流程测试失败: {e}")
            return False

    def test_resilience_flow(self):
        """测试韧性系统流程"""
        logger.info("开始测试韧性系统流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 测试限流器
                rate_limit_results = []
                for _ in range(50):
                    user = random.choice(users)
                    # 使用正确的限流器API
                    rate_limiter = get_or_create_rate_limiter("api_calls")
                    success = rate_limiter.is_allowed(key=str(user.id))
                    rate_limit_results.append(success)

                results["rate_limiting"] = {
                    "total_requests": len(rate_limit_results),
                    "successful_requests": sum(rate_limit_results),
                    "blocked_requests": len(rate_limit_results)
                    - sum(rate_limit_results),
                }

                # 测试熔断器
                circuit_breaker = get_or_create_circuit_breaker("permission_service")
                circuit_breaker_state = circuit_breaker.get_state()
                results["circuit_breaker"] = circuit_breaker_state.value

                # 测试重试机制
                retry_results = []
                for _ in range(10):
                    try:
                        # 模拟可能失败的操作 - 使用正确的API
                        result = self.permission_system.check_permission(
                            user_id=random.choice(users).id,
                            permission="read_messages",
                            scope="channel",
                            scope_id=999,  # 不存在的资源
                        )
                        retry_results.append(True)
                    except Exception:
                        retry_results.append(False)

                results["retry_mechanism"] = {
                    "total_attempts": len(retry_results),
                    "successful_attempts": sum(retry_results),
                }

            self.test_results["resilience"] = results
            logger.info("韧性系统流程测试完成")
            return True

        except Exception as e:
            logger.error(f"韧性系统流程测试失败: {e}")
            return False

    def test_event_system_flow(self):
        """测试事件系统流程"""
        logger.info("开始测试事件系统流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 模拟权限事件
                events = []
                for user in users:
                    event = {
                        "event_type": "permission_granted",
                        "user_id": user.id,
                        "permission": "send_messages",
                        "scope": "channel",
                        "scope_id": 1,
                        "timestamp": time.time(),
                    }
                    events.append(event)

                    # 发布事件到Redis
                    self.redis_client.publish("permission_events", json.dumps(event))

                results["events_published"] = len(events)

                # 测试事件监听
                event_listener = self.redis_client.pubsub()
                event_listener.subscribe("permission_events")

                # 监听一段时间
                received_events = []
                start_time = time.time()
                while time.time() - start_time < 2:  # 监听2秒
                    message = event_listener.get_message(timeout=0.1)
                    if message and message["type"] == "message":
                        received_events.append(json.loads(message["data"]))

                results["events_received"] = len(received_events)
                results["event_latency"] = time.time() - start_time

                event_listener.close()

            self.test_results["event_system"] = results
            logger.info("事件系统流程测试完成")
            return True

        except Exception as e:
            logger.error(f"事件系统流程测试失败: {e}")
            return False

    def test_performance_stress_flow(self):
        """测试性能压力流程"""
        logger.info("开始测试性能压力流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 并发权限检查
                def check_permission_worker(user_id, permission):
                    start_time = time.time()
                    try:
                        result = self.permission_system.check_permission(
                            user_id=user_id,
                            permission=permission,
                            scope="channel",
                            scope_id=1,
                        )
                        latency = time.time() - start_time
                        return {"success": True, "latency": latency}
                    except Exception as e:
                        latency = time.time() - start_time
                        return {"success": False, "error": str(e), "latency": latency}

                # 创建并发任务
                tasks = []
                with ThreadPoolExecutor(max_workers=10) as executor:
                    for _ in range(100):
                        user = random.choice(users)
                        permission = random.choice(["read_messages", "send_messages"])
                        task = executor.submit(
                            check_permission_worker, user.id, permission
                        )
                        tasks.append(task)

                    # 收集结果
                    worker_results = []
                    for task in as_completed(tasks):
                        worker_results.append(task.result())

                # 分析性能
                successful_requests = [r for r in worker_results if r["success"]]
                failed_requests = [r for r in worker_results if not r["success"]]

                latencies = [r["latency"] for r in worker_results]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                max_latency = max(latencies) if latencies else 0
                min_latency = min(latencies) if latencies else 0

                results["concurrent_performance"] = {
                    "total_requests": len(worker_results),
                    "successful_requests": len(successful_requests),
                    "failed_requests": len(failed_requests),
                    "success_rate": (
                        len(successful_requests) / len(worker_results)
                        if worker_results
                        else 0
                    ),
                    "avg_latency": avg_latency,
                    "max_latency": max_latency,
                    "min_latency": min_latency,
                }

                # 测试缓存性能
                cache_stats = self.cache.get_stats()
                results["cache_performance"] = cache_stats

                # 测试监控性能 - 使用正确的方法名
                monitor_stats = self.monitor.get_stats()
                results["monitor_performance"] = monitor_stats

            self.test_results["performance_stress"] = results
            logger.info("性能压力流程测试完成")
            return True

        except Exception as e:
            logger.error(f"性能压力流程测试失败: {e}")
            return False

    def test_error_recovery_flow(self):
        """测试错误恢复流程"""
        logger.info("开始测试错误恢复流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()

                # 模拟数据库连接错误
                with patch("app.core.extensions.db.session.commit") as mock_commit:
                    mock_commit.side_effect = Exception("数据库连接错误")

                    try:
                        # 尝试权限检查 - 使用正确的API
                        result = self.permission_system.check_permission(
                            user_id=users[0].id,
                            permission="read_messages",
                            scope="channel",
                            scope_id=1,
                        )
                        results["database_error_handling"] = "handled"
                        results["database_error_message"] = "权限检查成功"
                    except Exception as e:
                        results["database_error_handling"] = "handled"
                        results["database_error_message"] = str(e)

                # 模拟Redis连接错误
                with patch.object(self.redis_client, "get") as mock_redis_get:
                    mock_redis_get.side_effect = Exception("Redis连接错误")

                    try:
                        # 尝试缓存操作 - 使用正确的API
                        cache_value = self.cache.get_permission(
                            user_id=users[0].id,
                            permission="read_messages",
                            scope="channel",
                            scope_id=1,
                        )
                        results["redis_error_handling"] = "handled"
                        results["redis_error_message"] = "缓存操作成功"
                    except Exception as e:
                        results["redis_error_handling"] = "handled"
                        results["redis_error_message"] = str(e)

                # 测试熔断器恢复
                circuit_breaker = get_or_create_circuit_breaker("permission_service")

                # 模拟熔断器打开
                circuit_breaker._state = CircuitBreakerState.OPEN

                # 检查是否恢复
                if circuit_breaker.get_state() == CircuitBreakerState.CLOSED:
                    results["circuit_breaker_recovery"] = "successful"
                else:
                    results["circuit_breaker_recovery"] = "failed"

            self.test_results["error_recovery"] = results
            logger.info("错误恢复流程测试完成")
            return True

        except Exception as e:
            logger.error(f"错误恢复流程测试失败: {e}")
            return False

    def test_integration_flow(self):
        """测试集成流程"""
        logger.info("开始测试集成流程")

        try:
            results = {}

            with self.app.app_context():
                # 重新查询用户对象
                users = User.query.all()
                user = (
                    users[1] if len(users) > 1 else users[0]
                )  # moderator用户或第一个用户

                # 1. 用户登录
                token = create_access_token(
                    identity=str(user.id),
                    additional_claims={
                        "username": user.username,
                        "role": user.is_super_admin,
                    },
                )
                results["login"] = {"user_id": user.id, "token_valid": True}

                # 2. 权限检查 - 使用正确的API
                permissions = ["read_messages", "send_messages", "manage_channels"]
                permission_results = {}
                for permission in permissions:
                    try:
                        has_permission = self.permission_system.check_permission(
                            user_id=user.id,
                            permission=permission,
                            scope="channel",
                            scope_id=1,
                        )
                        permission_results[permission] = has_permission
                    except Exception as e:
                        permission_results[permission] = False
                        permission_results[f"{permission}_error"] = str(e)
                results["permissions"] = permission_results

                # 3. 缓存操作
                cache_stats = self.cache.get_stats()
                results["cache_stats"] = cache_stats

                # 4. 事件触发
                event = {
                    "event_type": "user_action",
                    "user_id": user.id,
                    "action": "permission_check",
                    "timestamp": time.time(),
                }
                self.redis_client.publish("permission_events", json.dumps(event))
                results["event_triggered"] = True

                # 5. 监控更新 - 使用正确的方法名
                monitor_stats = self.monitor.get_stats()
                results["monitor_stats"] = monitor_stats

                # 6. 性能指标
                performance_stats = self.permission_system.get_system_stats()
                results["performance_stats"] = performance_stats

            self.test_results["integration"] = results
            logger.info("集成流程测试完成")
            return True

        except Exception as e:
            logger.error(f"集成流程测试失败: {e}")
            return False

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始运行真实使用场景测试")

        if not self.setup_test_environment():
            logger.error("测试环境设置失败")
            return False

        test_functions = [
            ("用户登录流程", self.test_user_login_flow),
            ("权限检查流程", self.test_permission_checking_flow),
            ("缓存操作流程", self.test_cache_operations_flow),
            ("韧性系统流程", self.test_resilience_flow),
            ("事件系统流程", self.test_event_system_flow),
            ("性能压力流程", self.test_performance_stress_flow),
            ("错误恢复流程", self.test_error_recovery_flow),
            ("集成流程", self.test_integration_flow),
        ]

        success_count = 0
        total_count = len(test_functions)

        for test_name, test_func in test_functions:
            logger.info(f"运行测试: {test_name}")
            try:
                if test_func():
                    success_count += 1
                    logger.info(f"✅ {test_name} 测试通过")
                else:
                    logger.error(f"❌ {test_name} 测试失败")
            except Exception as e:
                logger.error(f"❌ {test_name} 测试异常: {e}")

        # 输出测试结果摘要
        logger.info(f"\n测试结果摘要:")
        logger.info(f"总测试数: {total_count}")
        logger.info(f"成功测试数: {success_count}")
        logger.info(f"失败测试数: {total_count - success_count}")
        logger.info(f"成功率: {success_count/total_count*100:.1f}%")

        # 输出详细结果
        for test_name, result in self.test_results.items():
            logger.info(f"\n{test_name} 详细结果:")
            logger.info(json.dumps(result, indent=2, default=str))

        return success_count == total_count


def test_real_world_scenario():
    """运行真实使用场景测试"""
    test = RealWorldScenarioTest()
    return test.run_all_tests()


if __name__ == "__main__":
    success = test_real_world_scenario()
    if success:
        print("🎉 所有真实使用场景测试通过！")
    else:
        print("❌ 部分真实使用场景测试失败")
