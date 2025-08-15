"""
WebSocket初始化和管理模块

提供稳定、可扩展的WebSocket信令通道
"""

import logging
from flask_socketio import SocketIO
from flask import Flask

logger = logging.getLogger(__name__)

# 全局SocketIO实例
socketio = None


def init_socketio(app: Flask):
    """初始化SocketIO"""
    global socketio

    try:
        # 创建SocketIO实例，配置为生产环境优化
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",  # 开发环境允许所有来源
            async_mode="eventlet",  # 使用eventlet作为异步模式
            logger=True,
            engineio_logger=True,
            ping_timeout=60,  # ping超时时间
            ping_interval=25,  # ping间隔
            max_http_buffer_size=1e8,  # 最大HTTP缓冲区大小
            max_message_size=1e8,  # 最大消息大小
            json=app.json,  # 使用Flask的JSON编码器
            manage_session=False,  # 不管理会话
            always_connect=True,  # 总是连接
            transports=["websocket", "polling"],  # 支持的传输方式
        )

        # 注册事件处理器
        from app.blueprints.control_plane.websocket import register_event_handlers

        register_event_handlers()

        # 注册SocketIO事件
        register_socketio_events()

        logger.info("SocketIO初始化成功")
        return socketio

    except Exception as e:
        logger.error(f"SocketIO初始化失败: {e}")
        raise


def register_socketio_events():
    """注册SocketIO事件处理器"""
    from app.blueprints.control_plane.websocket import (
        handle_connect,
        handle_disconnect,
        handle_subscribe_events,
        handle_request_status,
        handle_ping,
        handle_pong,
    )

    # 连接事件 - Flask-SocketIO使用不同的参数格式
    socketio.on_event(
        "connect", lambda sid: handle_connect(socketio, sid), namespace="/control"
    )
    socketio.on_event(
        "disconnect", lambda sid: handle_disconnect(socketio, sid), namespace="/control"
    )

    # 自定义事件 - 处理可选参数
    socketio.on_event(
        "subscribe_events",
        lambda sid, data=None: handle_subscribe_events(socketio, sid, data or {}),
        namespace="/control",
    )
    socketio.on_event(
        "request_status",
        lambda sid, data=None: handle_request_status(socketio, sid, data or {}),
        namespace="/control",
    )
    socketio.on_event(
        "ping",
        lambda sid, data=None: handle_ping(socketio, sid, data or {}),
        namespace="/control",
    )
    socketio.on_event(
        "pong",
        lambda sid, data=None: handle_pong(socketio, sid, data or {}),
        namespace="/control",
    )

    logger.info("SocketIO事件处理器注册完成")


def get_socketio() -> SocketIO:
    """获取SocketIO实例"""
    global socketio
    if socketio is None:
        raise RuntimeError("SocketIO未初始化，请先调用init_socketio()")
    return socketio


def broadcast_event(
    event: str, data: dict, namespace: str = "/control", room: str = None
):
    """广播事件到所有连接的客户端"""
    try:
        if socketio is None:
            logger.warning("SocketIO未初始化，无法广播事件")
            return

        if room:
            socketio.emit(event, data, room=room, namespace=namespace)
        else:
            socketio.emit(event, data, namespace=namespace)

        logger.debug(f"广播事件: {event}, 数据: {data}")

    except Exception as e:
        logger.error(f"广播事件失败: {e}")


def send_to_client(sid: str, event: str, data: dict, namespace: str = "/control"):
    """发送事件到指定客户端"""
    try:
        if socketio is None:
            logger.warning("SocketIO未初始化，无法发送事件")
            return

        socketio.emit(event, data, room=sid, namespace=namespace)
        logger.debug(f"发送事件到客户端 {sid}: {event}")

    except Exception as e:
        logger.error(f"发送事件到客户端失败: {e}")


def get_connection_stats() -> dict:
    """获取连接统计信息"""
    try:
        from app.blueprints.control_plane.websocket import connection_manager

        return connection_manager.get_connection_stats()
    except Exception as e:
        logger.error(f"获取连接统计失败: {e}")
        return {}


def is_connected(sid: str) -> bool:
    """检查客户端是否连接"""
    try:
        from app.blueprints.control_plane.websocket import connection_manager

        return sid in connection_manager.connected_clients
    except Exception as e:
        logger.error(f"检查连接状态失败: {e}")
        return False


def disconnect_client(sid: str, namespace: str = "/control"):
    """断开指定客户端连接"""
    try:
        if socketio is None:
            logger.warning("SocketIO未初始化，无法断开连接")
            return

        socketio.disconnect(sid, namespace=namespace)
        logger.info(f"断开客户端连接: {sid}")

    except Exception as e:
        logger.error(f"断开客户端连接失败: {e}")


def get_active_connections() -> list:
    """获取活跃连接列表"""
    try:
        from app.blueprints.control_plane.websocket import connection_manager

        return list(connection_manager.connected_clients.keys())
    except Exception as e:
        logger.error(f"获取活跃连接失败: {e}")
        return []


# ==================== WebSocket健康检查 ====================


def check_websocket_health() -> dict:
    """检查WebSocket健康状态"""
    try:
        stats = get_connection_stats()

        health_status = {
            "status": "healthy",
            "socketio_initialized": socketio is not None,
            "active_connections": stats.get("active_connections", 0),
            "total_connections": stats.get("total_connections", 0),
            "max_connections": stats.get("max_connections", 1000),
            "connection_ratio": stats.get("total_connections", 0)
            / max(stats.get("max_connections", 1), 1),
        }

        # 检查连接比例
        if health_status["connection_ratio"] > 0.8:
            health_status["status"] = "warning"
        elif health_status["connection_ratio"] > 0.95:
            health_status["status"] = "critical"

        # 检查SocketIO初始化状态
        if not health_status["socketio_initialized"]:
            health_status["status"] = "error"

        return health_status

    except Exception as e:
        logger.error(f"WebSocket健康检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "socketio_initialized": socketio is not None,
        }


# ==================== WebSocket配置管理 ====================


class WebSocketConfig:
    """WebSocket配置管理"""

    def __init__(self):
        self.cors_allowed_origins = "*"
        self.async_mode = "eventlet"
        self.ping_timeout = 60
        self.ping_interval = 25
        self.max_http_buffer_size = 1e8
        self.max_message_size = 1e8
        self.transports = ["websocket", "polling"]
        self.max_connections = 1000
        self.connection_timeout = 300
        self.health_check_interval = 30

    def update_from_app_config(self, app):
        """从Flask应用配置更新WebSocket配置"""
        try:
            ws_config = app.config.get("WEBSOCKET_CONFIG", {})

            self.cors_allowed_origins = ws_config.get(
                "cors_allowed_origins", self.cors_allowed_origins
            )
            self.async_mode = ws_config.get("async_mode", self.async_mode)
            self.ping_timeout = ws_config.get("ping_timeout", self.ping_timeout)
            self.ping_interval = ws_config.get("ping_interval", self.ping_interval)
            self.max_http_buffer_size = ws_config.get(
                "max_http_buffer_size", self.max_http_buffer_size
            )
            self.max_message_size = ws_config.get(
                "max_message_size", self.max_message_size
            )
            self.transports = ws_config.get("transports", self.transports)
            self.max_connections = ws_config.get(
                "max_connections", self.max_connections
            )
            self.connection_timeout = ws_config.get(
                "connection_timeout", self.connection_timeout
            )
            self.health_check_interval = ws_config.get(
                "health_check_interval", self.health_check_interval
            )

            logger.info("WebSocket配置已更新")

        except Exception as e:
            logger.error(f"更新WebSocket配置失败: {e}")


# 全局配置实例
websocket_config = WebSocketConfig()
