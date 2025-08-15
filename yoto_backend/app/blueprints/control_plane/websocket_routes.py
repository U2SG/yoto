"""
控制平面WebSocket路由

处理WebSocket连接和事件
"""

import logging
import time
from flask import Blueprint, request
from flask_socketio import emit, disconnect
from . import websocket

logger = logging.getLogger(__name__)

# 创建WebSocket蓝图
ws_bp = Blueprint("websocket", __name__)

# 控制平面命名空间
CONTROL_NAMESPACE = "/control"

# ==================== WebSocket事件处理 ====================


@ws_bp.route("/connect")
def handle_connect():
    """处理WebSocket连接"""
    try:
        # 这里可以添加连接验证逻辑
        return {"status": "connected"}
    except Exception as e:
        logger.error(f"WebSocket连接失败: {e}")
        return {"error": str(e)}, 500


# 注意：这些装饰器需要在SocketIO实例上注册，而不是在Blueprint上
# 这些函数将在主应用中通过socketio.on_event注册


def register_socketio_events(socketio):
    """注册SocketIO事件处理器 - 使用命名空间避免冲突"""

    @socketio.on("connect", namespace=CONTROL_NAMESPACE)
    def handle_socket_connect():
        """处理SocketIO连接 - 控制平面专用，不需要JWT认证"""
        try:
            logger.info(f"控制平面WebSocket连接: {request.sid}")

            # 直接调用控制平面的连接处理
            websocket.handle_connect(socketio, request.sid)

        except Exception as e:
            logger.error(f"控制平面WebSocket连接处理失败: {e}")
            disconnect()

    @socketio.on("disconnect", namespace=CONTROL_NAMESPACE)
    def handle_socket_disconnect():
        """处理SocketIO断开连接"""
        try:
            websocket.handle_disconnect(socketio, request.sid)
        except Exception as e:
            logger.error(f"控制平面WebSocket断开连接处理失败: {e}")

    @socketio.on("subscribe_events", namespace=CONTROL_NAMESPACE)
    def handle_subscribe_events(data):
        """处理事件订阅"""
        try:
            websocket.handle_subscribe_events(socketio, request.sid, data)
        except Exception as e:
            logger.error(f"事件订阅处理失败: {e}")
            emit("error", {"message": str(e)}, namespace=CONTROL_NAMESPACE)

    @socketio.on("request_status", namespace=CONTROL_NAMESPACE)
    def handle_request_status(data):
        """处理状态请求"""
        try:
            websocket.handle_request_status(socketio, request.sid, data)
        except Exception as e:
            logger.error(f"状态请求处理失败: {e}")
            emit("error", {"message": str(e)}, namespace=CONTROL_NAMESPACE)

    @socketio.on("ping", namespace=CONTROL_NAMESPACE)
    def handle_ping():
        """处理ping请求"""
        try:
            emit("pong", {"timestamp": time.time()}, namespace=CONTROL_NAMESPACE)
        except Exception as e:
            logger.error(f"Ping处理失败: {e}")

    # 启动后台任务
    try:
        websocket.start_background_tasks(socketio)
        logger.info("控制平面后台任务已启动")
    except Exception as e:
        logger.error(f"启动后台任务失败: {e}")

    logger.info(f"控制平面SocketIO事件处理器已注册 (命名空间: {CONTROL_NAMESPACE})")
