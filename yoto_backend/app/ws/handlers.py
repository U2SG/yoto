"""
WebSocket事件处理器
处理实时消息、用户状态、频道管理等
"""

import time
import logging
from flask import request
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from app.blueprints.auth.models import User
from app.blueprints.servers.models import ServerMember
from app.blueprints.channels.models import Channel, Message, MessageReaction as Reaction
from . import get_socketio

logger = logging.getLogger(__name__)

# 在线用户映射 {user_id: sid}
online_users = {}


def authenticate_socket(token):
    """验证WebSocket连接的token"""
    try:
        # 移除Bearer前缀
        if token.startswith("Bearer "):
            token = token[7:]

        decoded = decode_token(token)
        return decoded
    except Exception as e:
        logger.error(f"WebSocket认证失败: {e}")
        return None


def handle_ping():
    """处理ping请求 - 默认命名空间"""
    try:
        socketio = get_socketio()
        emit("pong", {"timestamp": time.time()}, namespace="/")
    except Exception as e:
        logger.error(f"Ping处理失败: {e}")


def handle_connect():
    """处理WebSocket连接 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        if not token:
            logger.warning("WebSocket连接缺少token")
            disconnect()
            return

        # 验证token
        token_data = authenticate_socket(token)
        if not token_data:
            logger.warning("WebSocket连接token无效")
            disconnect()
            return

        user_id = token_data["sub"]

        # 验证用户是否存在 - 将字符串user_id转换为整数
        try:
            user_id_int = int(user_id)
            user = User.query.get(user_id_int)
        except (ValueError, TypeError):
            logger.warning(f"WebSocket连接user_id格式错误: {user_id}")
            disconnect()
            return

        if not user:
            logger.warning(f"WebSocket连接用户不存在: {user_id}")
            disconnect()
            return

        # 记录在线用户
        online_users[user_id] = request.sid

        # 加入用户个人房间
        join_room(f"user_{user_id}")

        # 加入用户所在的服务器房间
        user_servers = ServerMember.query.filter_by(user_id=user_id_int).all()
        for member in user_servers:
            join_room(f"server_{member.server_id}")

        logger.info(f"用户 {user_id} WebSocket连接成功")
        emit("connected", {"user_id": user_id, "message": "连接成功"})

    except Exception as e:
        logger.error(f"WebSocket连接处理异常: {e}")
        disconnect()


def handle_disconnect():
    """处理WebSocket断开连接 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        if token:
            token_data = authenticate_socket(token)
            if token_data:
                user_id = token_data["sub"]
                if user_id in online_users:
                    del online_users[user_id]
                    logger.info(f"用户 {user_id} WebSocket断开连接")
    except Exception as e:
        logger.error(f"WebSocket断开连接处理异常: {e}")


def handle_join_channel(data):
    """处理加入频道 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        token_data = authenticate_socket(token)
        if not token_data:
            emit("error", {"message": "认证失败"})
            return

        user_id = token_data["sub"]
        channel_id = data.get("channel_id")

        if not channel_id:
            emit("error", {"message": "频道ID必填"})
            return

        # 验证用户是否有权限访问该频道
        channel = Channel.query.get(channel_id)
        if not channel:
            emit("error", {"message": "频道不存在"})
            return

        # 检查用户是否是该频道所属服务器的成员 - 转换user_id为整数
        try:
            user_id_int = int(user_id)
            member = ServerMember.query.filter_by(
                server_id=channel.server_id, user_id=user_id_int
            ).first()
        except (ValueError, TypeError):
            emit("error", {"message": "用户ID格式错误"})
            return

        if not member:
            emit("error", {"message": "无权限访问该频道"})
            return

        # 加入频道房间
        join_room(f"channel_{channel_id}")
        emit(
            "joined_channel",
            {"channel_id": channel_id, "message": f"已加入频道 {channel.name}"},
        )

        logger.info(f"用户 {user_id} 加入频道 {channel_id}")

    except Exception as e:
        logger.error(f"加入频道处理异常: {e}")
        emit("error", {"message": "加入频道失败"})


def handle_leave_channel(data):
    """处理离开频道 - 主应用命名空间"""
    try:
        channel_id = data.get("channel_id")
        if channel_id:
            leave_room(f"channel_{channel_id}")
            emit("left_channel", {"channel_id": channel_id, "message": "已离开频道"})

            # 优先从headers获取token，兼容query参数
            token = request.headers.get("Authorization") or request.args.get("token")
            if token:
                token_data = authenticate_socket(token)
                if token_data:
                    user_id = token_data["sub"]
                    logger.info(f"用户 {user_id} 离开频道 {channel_id}")

    except Exception as e:
        logger.error(f"离开频道处理异常: {e}")


def handle_send_message(data):
    """处理发送消息事件 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        token_data = authenticate_socket(token)
        if not token_data:
            emit("error", {"message": "认证失败"})
            return

        user_id = token_data["sub"]
        channel_id = data.get("channel_id")
        message = data.get("message")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")

        if not channel_id or not message:
            emit("error", {"message": "频道ID和消息内容必填"})
            return

        # 验证频道是否存在
        channel = Channel.query.get(channel_id)
        if not channel:
            emit("error", {"message": "频道不存在"})
            return

        # 验证用户是否有权限发送消息到该频道
        try:
            user_id_int = int(user_id)
            member = ServerMember.query.filter_by(
                server_id=channel.server_id, user_id=user_id_int
            ).first()
        except (ValueError, TypeError):
            emit("error", {"message": "用户ID格式错误"})
            return

        if not member:
            emit("error", {"message": "无权限发送消息到该频道"})
            return

        # 创建消息记录
        new_message = Message(
            channel_id=channel_id,
            user_id=user_id_int,
            content=message,
            type=message_type,  # 修复：使用正确的字段名
            reply_to_id=reply_to_id,
        )

        # 保存到数据库
        from app.core.extensions import db

        db.session.add(new_message)
        db.session.commit()

        # 获取用户信息
        user = User.query.get(user_id_int)
        user_name = user.username if user else "Unknown"

        # 构建消息数据
        message_data = {
            "id": new_message.id,
            "channel_id": channel_id,
            "user_id": user_id_int,
            "content": message,
            "message_type": message_type,
            "reply_to_id": reply_to_id,
            "timestamp": new_message.created_at.isoformat(),
            "user_name": user_name,
        }

        # 广播消息到频道
        emit("new_message", message_data, room=f"channel_{channel_id}")

        logger.info(f"用户 {user_id} 在频道 {channel_id} 发送消息")

    except Exception as e:
        logger.error(f"发送消息处理异常: {e}")
        emit("error", {"message": "发送消息失败"})


def handle_typing(data):
    """处理用户正在输入事件 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        token_data = authenticate_socket(token)
        if not token_data:
            return

        user_id = token_data["sub"]
        channel_id = data.get("channel_id")
        is_typing = data.get("is_typing", True)

        if not channel_id:
            return

        # 验证用户是否有权限访问该频道
        channel = Channel.query.get(channel_id)
        if not channel:
            return

        try:
            user_id_int = int(user_id)
            member = ServerMember.query.filter_by(
                server_id=channel.server_id, user_id=user_id_int
            ).first()
        except (ValueError, TypeError):
            return

        if not member:
            return

        # 获取用户信息
        user = User.query.get(user_id_int)
        user_name = user.username if user else "Unknown"

        # 广播输入状态到频道
        typing_data = {
            "user_id": user_id_int,
            "channel_id": channel_id,
            "is_typing": is_typing,
            "user_name": user_name,
        }

        emit("user_typing", typing_data, room=f"channel_{channel_id}")

    except Exception as e:
        logger.error(f"输入状态处理异常: {e}")


def broadcast_to_server(server_id, event, data):
    """广播消息到服务器所有成员"""
    try:
        socketio = get_socketio()
        socketio.emit(event, data, room=f"server_{server_id}")
    except Exception as e:
        logger.error(f"服务器广播失败: {e}")


def broadcast_to_channel(channel_id, event, data):
    """广播消息到频道所有成员"""
    try:
        socketio = get_socketio()
        socketio.emit(event, data, room=f"channel_{channel_id}")
    except Exception as e:
        logger.error(f"频道广播失败: {e}")


def send_to_user(user_id, event, data):
    """发送消息给指定用户"""
    try:
        socketio = get_socketio()
        socketio.emit(event, data, room=f"user_{user_id}")
    except Exception as e:
        logger.error(f"用户消息发送失败: {e}")


def handle_add_reaction(data):
    """处理添加表情反应 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        token_data = authenticate_socket(token)
        if not token_data:
            emit("error", {"message": "认证失败"})
            return

        user_id = token_data["sub"]
        message_id = data.get("message_id")
        reaction_type = data.get("reaction_type")  # emoji, like, etc.

        if not message_id or not reaction_type:
            emit("error", {"message": "消息ID和反应类型必填"})
            return

        # 验证消息是否存在
        message = Message.query.get(message_id)
        if not message:
            emit("error", {"message": "消息不存在"})
            return

        # 验证用户是否有权限访问该消息的频道
        try:
            user_id_int = int(user_id)
            member = ServerMember.query.filter_by(
                server_id=message.channel.server_id, user_id=user_id_int
            ).first()
        except (ValueError, TypeError):
            emit("error", {"message": "用户ID格式错误"})
            return

        if not member:
            emit("error", {"message": "无权限访问该消息"})
            return

        # 检查是否已经添加过相同的反应
        existing_reaction = Reaction.query.filter_by(
            message_id=message_id,
            user_id=user_id_int,
            reaction=reaction_type,  # 修复：使用正确的字段名
        ).first()

        if existing_reaction:
            emit("error", {"message": "已经添加过该反应"})
            return

        # 创建反应记录
        new_reaction = Reaction(
            message_id=message_id,
            user_id=user_id_int,
            reaction=reaction_type,  # 修复：使用正确的字段名
        )

        # 保存到数据库
        from app.core.extensions import db

        db.session.add(new_reaction)
        db.session.commit()

        # 获取用户信息
        user = User.query.get(user_id_int)
        user_name = user.username if user else "Unknown"

        # 构建反应数据
        reaction_data = {
            "id": new_reaction.id,
            "message_id": message_id,
            "user_id": user_id_int,
            "reaction_type": reaction_type,
            "timestamp": new_reaction.created_at.isoformat(),
            "user_name": user_name,
        }

        # 广播反应到频道
        emit("new_reaction", reaction_data, room=f"channel_{message.channel_id}")

        logger.info(f"用户 {user_id} 对消息 {message_id} 添加反应 {reaction_type}")

    except Exception as e:
        logger.error(f"添加反应处理异常: {e}")
        emit("error", {"message": "添加反应失败"})


def handle_remove_reaction(data):
    """处理移除表情反应 - 主应用命名空间"""
    try:
        # 优先从headers获取token，兼容query参数
        token = request.headers.get("Authorization") or request.args.get("token")
        token_data = authenticate_socket(token)
        if not token_data:
            emit("error", {"message": "认证失败"})
            return

        user_id = token_data["sub"]
        message_id = data.get("message_id")
        reaction_type = data.get("reaction_type")

        if not message_id or not reaction_type:
            emit("error", {"message": "消息ID和反应类型必填"})
            return

        # 验证消息是否存在
        message = Message.query.get(message_id)
        if not message:
            emit("error", {"message": "消息不存在"})
            return

        # 验证用户是否有权限访问该消息的频道
        try:
            user_id_int = int(user_id)
            member = ServerMember.query.filter_by(
                server_id=message.channel.server_id, user_id=user_id_int
            ).first()
        except (ValueError, TypeError):
            emit("error", {"message": "用户ID格式错误"})
            return

        if not member:
            emit("error", {"message": "无权限访问该消息"})
            return

        # 查找要删除的反应
        reaction = Reaction.query.filter_by(
            message_id=message_id,
            user_id=user_id_int,
            reaction=reaction_type,  # 修复：使用正确的字段名
        ).first()

        if not reaction:
            emit("error", {"message": "未找到该反应"})
            return

        # 删除反应记录
        from app.core.extensions import db

        db.session.delete(reaction)
        db.session.commit()

        # 获取用户信息
        user = User.query.get(user_id_int)
        user_name = user.username if user else "Unknown"

        # 构建反应数据
        reaction_data = {
            "message_id": message_id,
            "user_id": user_id_int,
            "reaction_type": reaction_type,
            "user_name": user_name,
        }

        # 广播反应移除到频道
        emit("reaction_removed", reaction_data, room=f"channel_{message.channel_id}")

        logger.info(f"用户 {user_id} 对消息 {message_id} 移除反应 {reaction_type}")

    except Exception as e:
        logger.error(f"移除反应处理异常: {e}")
        emit("error", {"message": "移除反应失败"})
