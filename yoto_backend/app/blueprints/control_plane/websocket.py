"""
控制平面WebSocket支持

提供实时事件流和系统状态推送
"""

import json
import logging
import threading
import time
from typing import Dict, Any, List
from flask_socketio import emit, disconnect
import redis

# 导入权限系统模块
from app.core.permission.permissions_refactored import (
    get_permission_system,
    get_resilience_controller,
)
from app.core.permission.hybrid_permission_cache import get_hybrid_cache
from app.core.permission.permission_monitor import get_permission_monitor

logger = logging.getLogger(__name__)

# 控制平面命名空间
CONTROL_NAMESPACE = "/control"


# Redis连接用于事件流 - 支持集群感知
def _init_redis_client():
    """初始化Redis客户端，支持集群和单节点模式"""
    try:
        # 尝试从Flask配置获取Redis配置
        try:
            from flask import current_app

            redis_config = current_app.config.get(
                "REDIS_SINGLE_NODE_CONFIG",
                {"host": "127.0.0.1", "port": 6379, "db": 0, "decode_responses": True},
            )
        except RuntimeError:
            # 如果不在应用上下文中，使用默认配置
            redis_config = {
                "host": "127.0.0.1",
                "port": 6379,
                "db": 0,
                "decode_responses": True,
            }

        # 尝试Redis集群连接
        try:
            # 获取集群节点配置
            cluster_nodes = current_app.config.get(
                "REDIS_CLUSTER_NODES", [{"host": "localhost", "port": 6379}]
            )

            # 确保节点配置格式正确
            valid_startup_nodes = []
            for node in cluster_nodes:
                if isinstance(node, dict) and "host" in node and "port" in node:
                    valid_startup_nodes.append(
                        {"host": node["host"], "port": node["port"]}
                    )

            if len(valid_startup_nodes) > 1:
                # 如果有多个节点，尝试集群模式
                try:
                    redis_client = redis.RedisCluster(
                        startup_nodes=valid_startup_nodes,
                        decode_responses=True,
                        skip_full_coverage_check=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                    )
                    redis_client.ping()
                    logger.info("控制平面使用Redis集群")
                    return redis_client, True
                except Exception as cluster_error:
                    logger.warning(
                        f"Redis集群连接失败，降级到单节点模式: {cluster_error}"
                    )

            # 降级到单节点Redis
            redis_client = redis.Redis(**redis_config)
            redis_client.ping()
            logger.info("控制平面使用Redis单节点")
            return redis_client, True

        except Exception as e:
            logger.warning(f"Redis连接失败: {e}")
            return None, False

    except Exception as e:
        logger.warning(f"Redis初始化失败: {e}")
        return None, False


# 初始化Redis客户端
redis_client, REDIS_AVAILABLE = _init_redis_client()

# 全局变量存储连接的客户端
connected_clients = set()

# ==================== WebSocket连接管理 ====================


class WebSocketConnectionManager:
    """WebSocket连接管理器 - 提供稳定、可扩展的连接管理"""

    def __init__(self):
        self.connected_clients = {}  # {sid: client_info}
        self.room_subscriptions = {}  # {room: set(sid)}
        self.event_handlers = {}  # {event_type: handler_func}
        self.connection_lock = threading.Lock()
        self.health_check_interval = 30  # 健康检查间隔（秒）
        self.max_connections = 1000  # 最大连接数
        self.connection_timeout = 300  # 连接超时时间（秒）

        # 启动健康检查线程
        self._start_health_check()

    def add_client(self, sid: str, client_info: dict = None):
        """添加客户端连接"""
        with self.connection_lock:
            if len(self.connected_clients) >= self.max_connections:
                logger.warning(f"达到最大连接数限制: {self.max_connections}")
                return False

            self.connected_clients[sid] = {
                "info": client_info or {},
                "connected_at": time.time(),
                "last_activity": time.time(),
                "subscriptions": set(),
                "status": "active",
            }
            logger.info(f"客户端连接: {sid}, 当前连接数: {len(self.connected_clients)}")
            return True

    def remove_client(self, sid: str):
        """移除客户端连接"""
        with self.connection_lock:
            if sid in self.connected_clients:
                # 清理房间订阅
                client_info = self.connected_clients[sid]
                for room in client_info["subscriptions"]:
                    if room in self.room_subscriptions:
                        self.room_subscriptions[room].discard(sid)
                        if not self.room_subscriptions[room]:
                            del self.room_subscriptions[room]

                del self.connected_clients[sid]
                logger.info(
                    f"客户端断开连接: {sid}, 当前连接数: {len(self.connected_clients)}"
                )

    def subscribe_to_room(self, sid: str, room: str):
        """订阅房间"""
        with self.connection_lock:
            if sid in self.connected_clients:
                self.connected_clients[sid]["subscriptions"].add(room)
                if room not in self.room_subscriptions:
                    self.room_subscriptions[room] = set()
                self.room_subscriptions[room].add(sid)
                self.connected_clients[sid]["last_activity"] = time.time()
                logger.debug(f"客户端 {sid} 订阅房间: {room}")

    def unsubscribe_from_room(self, sid: str, room: str):
        """取消订阅房间"""
        with self.connection_lock:
            if sid in self.connected_clients:
                self.connected_clients[sid]["subscriptions"].discard(room)
                if room in self.room_subscriptions:
                    self.room_subscriptions[room].discard(sid)
                    if not self.room_subscriptions[room]:
                        del self.room_subscriptions[room]
                self.connected_clients[sid]["last_activity"] = time.time()
                logger.debug(f"客户端 {sid} 取消订阅房间: {room}")

    def get_room_subscribers(self, room: str) -> set:
        """获取房间订阅者"""
        with self.connection_lock:
            return self.room_subscriptions.get(room, set()).copy()

    def broadcast_to_room(
        self, room: str, event: str, data: dict, namespace: str = None
    ):
        """向房间广播消息"""
        subscribers = self.get_room_subscribers(room)
        if subscribers:
            logger.debug(
                f"向房间 {room} 广播事件 {event}, 订阅者数: {len(subscribers)}"
            )
            return subscribers
        return set()

    def update_client_activity(self, sid: str):
        """更新客户端活动时间"""
        with self.connection_lock:
            if sid in self.connected_clients:
                self.connected_clients[sid]["last_activity"] = time.time()

    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        with self.connection_lock:
            now = time.time()
            active_connections = 0
            idle_connections = 0

            for client_info in self.connected_clients.values():
                if now - client_info["last_activity"] < self.connection_timeout:
                    active_connections += 1
                else:
                    idle_connections += 1

            return {
                "total_connections": len(self.connected_clients),
                "active_connections": active_connections,
                "idle_connections": idle_connections,
                "room_count": len(self.room_subscriptions),
                "max_connections": self.max_connections,
            }

    def _start_health_check(self):
        """启动健康检查线程"""

        def health_check_loop():
            while True:
                try:
                    self._cleanup_inactive_connections()
                    time.sleep(self.health_check_interval)
                except Exception as e:
                    logger.error(f"健康检查失败: {e}")
                    time.sleep(5)

        health_thread = threading.Thread(target=health_check_loop, daemon=True)
        health_thread.start()

    def _cleanup_inactive_connections(self):
        """清理非活跃连接"""
        with self.connection_lock:
            now = time.time()
            inactive_sids = []

            for sid, client_info in self.connected_clients.items():
                if now - client_info["last_activity"] > self.connection_timeout:
                    inactive_sids.append(sid)

            for sid in inactive_sids:
                self.remove_client(sid)
                logger.info(f"清理非活跃连接: {sid}")

    def register_event_handler(self, event_type: str, handler_func):
        """注册事件处理器"""
        self.event_handlers[event_type] = handler_func
        logger.debug(f"注册事件处理器: {event_type}")


# 创建全局连接管理器
connection_manager = WebSocketConnectionManager()

# ==================== 事件处理器注册 ====================


def register_event_handlers():
    """注册所有事件处理器"""
    connection_manager.register_event_handler(
        "subscribe_events", handle_subscribe_events
    )
    connection_manager.register_event_handler("request_status", handle_request_status)
    connection_manager.register_event_handler("ping", handle_ping)
    connection_manager.register_event_handler("pong", handle_pong)


# ==================== WebSocket事件处理 ====================


def handle_connect(socketio, sid):
    """处理客户端连接"""
    try:
        # 添加到连接管理器
        if connection_manager.add_client(sid):
            logger.info(f"客户端连接: {sid}")

            # 发送欢迎消息
            emit(
                "welcome",
                {
                    "message": "欢迎连接到权限系统控制平面",
                    "timestamp": time.time(),
                    "client_id": sid,
                    "server_info": {
                        "version": "1.0.0",
                        "features": [
                            "real_time_events",
                            "system_monitoring",
                            "performance_stats",
                        ],
                    },
                },
                room=sid,
                namespace=CONTROL_NAMESPACE,
            )

            # 立即发送当前系统状态
            send_system_status(socketio, sid)

            # 订阅系统事件房间
            connection_manager.subscribe_to_room(sid, "system_events")

        else:
            logger.warning(f"拒绝客户端连接: {sid}, 已达到最大连接数")
            emit(
                "error",
                {
                    "message": "服务器已达到最大连接数限制",
                    "code": "MAX_CONNECTIONS_REACHED",
                },
                room=sid,
                namespace=CONTROL_NAMESPACE,
            )
            disconnect(sid, namespace=CONTROL_NAMESPACE)

    except Exception as e:
        logger.error(f"处理连接失败: {e}")
        emit("error", {"message": str(e)}, room=sid, namespace=CONTROL_NAMESPACE)


def handle_disconnect(socketio, sid):
    """处理客户端断开连接"""
    try:
        connection_manager.remove_client(sid)
        logger.info(f"客户端断开连接: {sid}")
    except Exception as e:
        logger.error(f"处理断开连接失败: {e}")


def handle_subscribe_events(socketio, sid, data):
    """处理事件订阅请求"""
    try:
        connection_manager.update_client_activity(sid)

        event_types = data.get("event_types", ["all"])
        rooms = data.get("rooms", [])

        logger.info(f"客户端 {sid} 订阅事件类型: {event_types}, 房间: {rooms}")

        # 订阅指定房间
        for room in rooms:
            if room:
                connection_manager.subscribe_to_room(sid, room)

        # 发送订阅确认
        emit(
            "subscription_confirmed",
            {
                "event_types": event_types,
                "rooms": rooms,
                "timestamp": time.time(),
                "subscription_id": f"{sid}_{int(time.time())}",
            },
            room=sid,
            namespace=CONTROL_NAMESPACE,
        )

    except Exception as e:
        logger.error(f"处理事件订阅失败: {e}")
        emit("error", {"message": str(e)}, room=sid, namespace=CONTROL_NAMESPACE)


def handle_request_status(socketio, sid, data):
    """处理状态请求"""
    try:
        connection_manager.update_client_activity(sid)

        status_type = data.get("type", "system")
        request_id = data.get("request_id", str(int(time.time())))

        logger.info(f"客户端 {sid} 请求状态: {status_type}")

        if status_type == "system":
            send_system_status(socketio, sid, request_id)
        elif status_type == "performance":
            send_performance_stats(socketio, sid, request_id)
        elif status_type == "cache":
            send_cache_stats(socketio, sid, request_id)
        elif status_type == "events":
            send_recent_events(socketio, sid, request_id)
        elif status_type == "connections":
            send_connection_stats(socketio, sid, request_id)
        else:
            emit(
                "error",
                {"message": f"未知的状态类型: {status_type}", "request_id": request_id},
                room=sid,
                namespace=CONTROL_NAMESPACE,
            )

    except Exception as e:
        logger.error(f"处理状态请求失败: {e}")
        emit("error", {"message": str(e)}, room=sid, namespace=CONTROL_NAMESPACE)


def handle_ping(socketio, sid, data):
    """处理ping请求"""
    try:
        connection_manager.update_client_activity(sid)

        emit(
            "pong",
            {
                "timestamp": time.time(),
                "server_time": time.time(),
                "latency": data.get("client_time", 0),
            },
            room=sid,
            namespace=CONTROL_NAMESPACE,
        )

    except Exception as e:
        logger.error(f"处理ping失败: {e}")


def handle_pong(socketio, sid, data):
    """处理pong响应"""
    try:
        connection_manager.update_client_activity(sid)
        # 可以在这里计算延迟统计
        logger.debug(f"收到客户端 {sid} 的pong响应")
    except Exception as e:
        logger.error(f"处理pong失败: {e}")


# ==================== 状态推送函数 ====================


def send_system_status(socketio, sid=None, request_id=None):
    """发送系统状态"""
    try:
        permission_system = get_permission_system()

        # 获取各组件状态
        resilience_stats = get_resilience_stats()
        cache_stats = get_cache_stats()
        monitor_stats = get_monitor_stats()
        connection_stats = connection_manager.get_connection_stats()

        status_data = {
            "type": "system_status",
            "timestamp": time.time(),
            "request_id": request_id,
            "system": {
                "status": "running",
                "uptime": time.time()
                - getattr(permission_system, "start_time", time.time()),
                "version": "1.0.0",
            },
            "components": {
                "resilience": resilience_stats,
                "cache": cache_stats,
                "monitor": monitor_stats,
                "connections": connection_stats,
            },
            "redis": {
                "available": REDIS_AVAILABLE,
                "status": "connected" if REDIS_AVAILABLE else "disconnected",
            },
        }

        if sid:
            emit("system_status", status_data, room=sid, namespace=CONTROL_NAMESPACE)
        else:
            # 广播到系统事件房间
            subscribers = connection_manager.get_room_subscribers("system_events")
            for subscriber_sid in subscribers:
                emit(
                    "system_status",
                    status_data,
                    room=subscriber_sid,
                    namespace=CONTROL_NAMESPACE,
                )

    except Exception as e:
        logger.error(f"发送系统状态失败: {e}")
        error_data = {"type": "error", "message": str(e), "request_id": request_id}
        if sid:
            emit("error", error_data, room=sid, namespace=CONTROL_NAMESPACE)


def send_connection_stats(socketio, sid, request_id=None):
    """发送连接统计信息"""
    try:
        stats = connection_manager.get_connection_stats()

        stats_data = {
            "type": "connection_stats",
            "timestamp": time.time(),
            "request_id": request_id,
            "stats": stats,
        }

        emit("connection_stats", stats_data, room=sid, namespace=CONTROL_NAMESPACE)

    except Exception as e:
        logger.error(f"发送连接统计失败: {e}")
        emit(
            "error",
            {"message": str(e), "request_id": request_id},
            room=sid,
            namespace=CONTROL_NAMESPACE,
        )


def send_performance_stats(socketio, sid=None, request_id=None):
    """发送性能统计"""
    try:
        permission_system = get_permission_system()
        system_stats = permission_system.get_system_stats()

        performance_data = {
            "type": "performance_stats",
            "stats": system_stats,
            "timestamp": time.time(),
            "request_id": request_id,
        }

        if sid:
            emit(
                "performance_stats",
                performance_data,
                room=sid,
                namespace=CONTROL_NAMESPACE,
            )
        else:
            socketio.emit(
                "performance_stats", performance_data, namespace=CONTROL_NAMESPACE
            )

    except Exception as e:
        logger.error(f"发送性能统计失败: {e}")


def send_cache_stats(socketio, sid=None, request_id=None):
    """发送缓存统计"""
    try:
        hybrid_cache = get_hybrid_cache()
        stats = hybrid_cache.get_stats()

        cache_data = {
            "type": "cache_stats",
            "stats": stats,
            "timestamp": time.time(),
            "request_id": request_id,
        }

        if sid:
            emit("cache_stats", cache_data, room=sid, namespace=CONTROL_NAMESPACE)
        else:
            socketio.emit("cache_stats", cache_data, namespace=CONTROL_NAMESPACE)

    except Exception as e:
        logger.error(f"发送缓存统计失败: {e}")


def send_recent_events(socketio, sid=None, request_id=None):
    """发送最近事件"""
    try:
        monitor = get_permission_monitor()
        if monitor:
            events = monitor.get_events_summary()
        else:
            events = {"events": [], "message": "监控器不可用"}

        events_data = {
            "type": "recent_events",
            "events": events,
            "timestamp": time.time(),
            "request_id": request_id,
        }

        if sid:
            emit("recent_events", events_data, room=sid, namespace=CONTROL_NAMESPACE)
        else:
            socketio.emit("recent_events", events_data, namespace=CONTROL_NAMESPACE)

    except Exception as e:
        logger.error(f"发送最近事件失败: {e}")


# ==================== 后台任务 ====================


def start_background_tasks(socketio):
    """启动后台任务"""

    def broadcast_loop():
        """定期广播系统状态"""
        while True:
            try:
                if connected_clients:
                    send_system_status(socketio)
                    send_performance_stats(socketio)
                    send_cache_stats(socketio)
                    logger.debug(f"广播状态到 {len(connected_clients)} 个客户端")
                time.sleep(10)  # 每10秒广播一次
            except Exception as e:
                logger.error(f"广播循环错误: {e}")
                time.sleep(30)  # 出错时等待30秒

    def event_listener():
        """监听Redis事件流"""
        if not REDIS_AVAILABLE or not redis_client:
            logger.warning("Redis不可用，跳过事件监听")
            return

        try:
            pubsub = redis_client.pubsub()
            pubsub.subscribe("permissions:events", "permissions:resilience:events")

            logger.info("开始监听权限系统事件流")

            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # 解析事件数据
                        event_data = json.loads(message["data"])

                        # 广播事件到所有连接的客户端
                        socketio.emit(
                            "permission_event",
                            {
                                "channel": message["channel"],
                                "data": event_data,
                                "timestamp": time.time(),
                            },
                            namespace=CONTROL_NAMESPACE,
                        )

                        logger.debug(f"广播事件: {message['channel']}")

                    except json.JSONDecodeError:
                        logger.warning(f"无法解析事件数据: {message['data']}")
                    except Exception as e:
                        logger.error(f"处理事件失败: {e}")

        except Exception as e:
            logger.error(f"事件监听器错误: {e}")

    # 启动后台线程
    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast_thread.start()

    event_thread = threading.Thread(target=event_listener, daemon=True)
    event_thread.start()

    logger.info("后台任务已启动")


# ==================== 辅助函数 ====================


def get_resilience_stats() -> Dict[str, Any]:
    """获取韧性系统统计"""
    try:
        controller = get_resilience_controller()
        if controller:
            return {
                "status": "healthy",
                "controller_available": True,
                "configs": controller.get_all_configs(),
            }
        else:
            return {
                "status": "error",
                "controller_available": False,
                "error": "韧性控制器不可用",
            }
    except Exception as e:
        return {"status": "error", "controller_available": False, "error": str(e)}


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    try:
        hybrid_cache = get_hybrid_cache()
        stats = hybrid_cache.get_stats()

        # 计算缓存健康状态
        if stats.get("lru", {}).get("hit_rate", 0) > 0.8:
            status = "healthy"
        elif stats.get("lru", {}).get("hit_rate", 0) > 0.5:
            status = "warning"
        else:
            status = "error"

        return {"status": status, "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_monitor_stats() -> Dict[str, Any]:
    """获取监控统计"""
    try:
        monitor = get_permission_monitor()
        if monitor:
            stats = monitor.get_stats()
            return {"status": "healthy", "monitor_available": True, "stats": stats}
        else:
            return {
                "status": "warning",
                "monitor_available": False,
                "error": "监控器不可用",
            }
    except Exception as e:
        return {"status": "error", "monitor_available": False, "error": str(e)}
