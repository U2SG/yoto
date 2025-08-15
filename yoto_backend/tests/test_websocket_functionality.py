"""
WebSocket功能测试
测试WebSocket的完整功能，包括连接、认证、消息发送、频道管理等
"""

# 在导入任何其他模块之前进行monkey patch
import eventlet

eventlet.monkey_patch()

import json
import time
import threading
import logging
from typing import Dict, Any, List
import pytest
from flask_socketio import SocketIO
from flask import Flask
import redis

import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入应用模块
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message, MessageReaction
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token

logger = logging.getLogger(__name__)


class WebSocketFunctionalityTest:
    """WebSocket功能测试类"""

    def __init__(self):
        self.test_results = {}
        self.received_events = []
        self.received_messages = []
        self.app = None
        self.socketio = None
        self.client = None
        self.test_user = None
        self.test_server = None
        self.test_channel = None
        self.auth_token = None

    def setup_test_environment(self):
        """设置测试环境"""
        try:
            # 创建测试应用
            self.app = create_app("testing")

            with self.app.app_context():
                # 创建数据库表
                db.create_all()

                # 创建测试用户 - 修复User模型参数
                self.test_user = User(
                    username="testuser",
                    password_hash=generate_password_hash("password123"),
                )
                db.session.add(self.test_user)
                db.session.commit()  # 先提交用户，确保有ID

                # 创建测试服务器 - 确保owner_id不为None
                self.test_server = Server(
                    name="Test Server", owner_id=self.test_user.id
                )
                db.session.add(self.test_server)
                db.session.commit()  # 提交服务器

                # 创建服务器成员
                server_member = ServerMember(
                    server_id=self.test_server.id, user_id=self.test_user.id
                )
                db.session.add(server_member)

                # 创建测试频道
                self.test_channel = Channel(
                    name="Test Channel", server_id=self.test_server.id, type="text"
                )
                db.session.add(self.test_channel)
                db.session.commit()

                # 获取认证token
                self.auth_token = self.get_auth_token()
                if not self.auth_token:
                    logger.error("获取认证token失败")
                    return False

                # 获取SocketIO实例
                from app.ws import get_socketio

                self.socketio = get_socketio()

                # 创建测试客户端，在连接时提供token
                self.client = self.socketio.test_client(
                    self.app, headers={"Authorization": f"Bearer {self.auth_token}"}
                )

            logger.info("测试环境设置完成")
            return True

        except Exception as e:
            logger.error(f"测试环境设置失败: {e}")
            return False

    def cleanup_test_environment(self):
        """清理测试环境"""
        try:
            with self.app.app_context():
                db.drop_all()
            logger.info("测试环境清理完成")
        except Exception as e:
            logger.error(f"测试环境清理失败: {e}")

    def get_auth_token(self):
        """获取认证token"""
        try:
            with self.app.app_context():
                # 重新查询用户，确保Session绑定正确
                user = User.query.filter_by(username="testuser").first()
                if not user:
                    logger.error("未找到测试用户")
                    return None

                token = create_access_token(
                    identity=str(user.id),  # 确保user_id是字符串
                    additional_claims={
                        "username": user.username,
                        "is_super_admin": False,
                    },
                )
                return token
        except Exception as e:
            logger.error(f"获取认证token失败: {e}")
            return None

    def test_websocket_connection(self):
        """测试WebSocket连接"""
        try:
            logger.info("开始测试WebSocket连接...")

            # 检查连接状态
            assert self.client.is_connected()
            logger.info("WebSocket连接成功")

            # 等待连接成功消息
            time.sleep(1)

            # 检查是否收到连接成功消息
            received = self.client.get_received(namespace="/")
            connection_success = any(msg["name"] == "connected" for msg in received)

            if connection_success:
                logger.info("WebSocket认证成功")
                self.test_results["connection"] = True
                return True
            else:
                logger.error("WebSocket认证失败")
                self.test_results["connection"] = False
                return False

        except Exception as e:
            logger.error(f"WebSocket连接测试失败: {e}")
            self.test_results["connection"] = False
            return False

    def test_ping_pong(self):
        """测试ping/pong功能"""
        try:
            logger.info("开始测试ping/pong功能...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 发送ping
            self.client.emit("ping", namespace="/")

            # 等待pong响应
            time.sleep(1)

            # 检查是否收到pong
            received = self.client.get_received(namespace="/")
            pong_received = any(msg["name"] == "pong" for msg in received)

            if pong_received:
                logger.info("ping/pong功能正常")
                self.test_results["ping_pong"] = True
                return True
            else:
                logger.error("ping/pong功能异常")
                self.test_results["ping_pong"] = False
                return False

        except Exception as e:
            logger.error(f"ping/pong测试失败: {e}")
            self.test_results["ping_pong"] = False
            return False

    def test_channel_join_leave(self):
        """测试频道加入/离开功能"""
        try:
            logger.info("开始测试频道加入/离开功能...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 获取频道ID，确保Session绑定正确
            with self.app.app_context():
                channel = Channel.query.filter_by(name="Test Channel").first()
                if not channel:
                    logger.error("未找到测试频道")
                    return False
                channel_id = channel.id

            # 加入频道
            self.client.emit("join_channel", {"channel_id": channel_id}, namespace="/")

            time.sleep(1)

            # 检查是否收到加入成功消息
            received = self.client.get_received(namespace="/")
            join_success = any(msg["name"] == "joined_channel" for msg in received)

            if not join_success:
                logger.error("频道加入失败")
                self.test_results["channel_join"] = False
                return False

            logger.info("频道加入成功")

            # 离开频道
            self.client.emit("leave_channel", {"channel_id": channel_id}, namespace="/")

            time.sleep(1)

            # 检查是否收到离开成功消息
            received = self.client.get_received(namespace="/")
            leave_success = any(msg["name"] == "left_channel" for msg in received)

            if leave_success:
                logger.info("频道离开成功")
                self.test_results["channel_join"] = True
                return True
            else:
                logger.error("频道离开失败")
                self.test_results["channel_join"] = False
                return False

        except Exception as e:
            logger.error(f"频道加入/离开测试失败: {e}")
            self.test_results["channel_join"] = False
            return False

    def test_message_sending(self):
        """测试消息发送功能"""
        try:
            logger.info("开始测试消息发送功能...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 获取频道ID，确保Session绑定正确
            with self.app.app_context():
                channel = Channel.query.filter_by(name="Test Channel").first()
                if not channel:
                    logger.error("未找到测试频道")
                    return False
                channel_id = channel.id

            # 先加入频道
            self.client.emit("join_channel", {"channel_id": channel_id}, namespace="/")

            time.sleep(1)

            # 发送消息
            test_message = "Hello, WebSocket!"
            self.client.emit(
                "send_message",
                {"channel_id": channel_id, "message": test_message, "type": "text"},
                namespace="/",
            )

            time.sleep(1)

            # 检查是否收到新消息事件
            received = self.client.get_received(namespace="/")
            message_sent = any(msg["name"] == "new_message" for msg in received)

            if message_sent:
                logger.info("消息发送成功")
                self.test_results["message_sending"] = True
                return True
            else:
                logger.error("消息发送失败")
                self.test_results["message_sending"] = False
                return False

        except Exception as e:
            logger.error(f"消息发送测试失败: {e}")
            self.test_results["message_sending"] = False
            return False

    def test_typing_indicator(self):
        """测试输入状态指示器"""
        try:
            logger.info("开始测试输入状态指示器...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 获取频道ID，确保Session绑定正确
            with self.app.app_context():
                channel = Channel.query.filter_by(name="Test Channel").first()
                if not channel:
                    logger.error("未找到测试频道")
                    return False
                channel_id = channel.id

            # 发送输入状态
            self.client.emit(
                "typing", {"channel_id": channel_id, "is_typing": True}, namespace="/"
            )

            time.sleep(1)

            # 检查是否收到输入状态事件
            received = self.client.get_received(namespace="/")
            typing_event = any(msg["name"] == "user_typing" for msg in received)

            if typing_event:
                logger.info("输入状态指示器正常")
                self.test_results["typing_indicator"] = True
                return True
            else:
                logger.error("输入状态指示器异常")
                self.test_results["typing_indicator"] = False
                return False

        except Exception as e:
            logger.error(f"输入状态指示器测试失败: {e}")
            self.test_results["typing_indicator"] = False
            return False

    def test_reaction_system(self):
        """测试表情反应系统"""
        try:
            logger.info("开始测试表情反应系统...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 获取频道ID，确保Session绑定正确
            with self.app.app_context():
                channel = Channel.query.filter_by(name="Test Channel").first()
                if not channel:
                    logger.error("未找到测试频道")
                    return False
                channel_id = channel.id

            # 先发送一条消息
            self.client.emit(
                "send_message",
                {
                    "channel_id": channel_id,
                    "message": "Test message for reaction",
                    "type": "text",
                },
                namespace="/",
            )

            time.sleep(1)

            # 获取消息ID（这里简化处理）
            with self.app.app_context():
                message = Message.query.filter_by(channel_id=channel_id).first()

                if not message:
                    logger.error("未找到测试消息")
                    self.test_results["reaction_system"] = False
                    return False

                # 添加表情反应
                self.client.emit(
                    "add_reaction",
                    {"message_id": message.id, "reaction_type": "👍"},
                    namespace="/",
                )

                time.sleep(1)

                # 检查是否收到新反应事件
                received = self.client.get_received(namespace="/")
                reaction_added = any(msg["name"] == "new_reaction" for msg in received)

                if reaction_added:
                    logger.info("表情反应添加成功")

                    # 移除表情反应
                    self.client.emit(
                        "remove_reaction",
                        {"message_id": message.id, "reaction_type": "👍"},
                        namespace="/",
                    )

                    time.sleep(1)

                    # 检查是否收到移除反应事件
                    received = self.client.get_received(namespace="/")
                    reaction_removed = any(
                        msg["name"] == "reaction_removed" for msg in received
                    )

                    if reaction_removed:
                        logger.info("表情反应移除成功")
                        self.test_results["reaction_system"] = True
                        return True
                    else:
                        logger.error("表情反应移除失败")
                        self.test_results["reaction_system"] = False
                        return False
                else:
                    logger.error("表情反应添加失败")
                    self.test_results["reaction_system"] = False
                    return False

        except Exception as e:
            logger.error(f"表情反应系统测试失败: {e}")
            self.test_results["reaction_system"] = False
            return False

    def test_disconnect(self):
        """测试断开连接"""
        try:
            logger.info("开始测试断开连接...")

            # 确保连接状态
            if not self.client.is_connected():
                self.client.connect(
                    namespace="/",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                )

            # 断开连接
            self.client.disconnect(namespace="/")

            # 检查连接状态
            assert not self.client.is_connected()

            logger.info("WebSocket断开连接成功")
            self.test_results["disconnect"] = True
            return True

        except Exception as e:
            logger.error(f"断开连接测试失败: {e}")
            self.test_results["disconnect"] = False
            return False

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始WebSocket功能测试...")

        # 设置测试环境
        if not self.setup_test_environment():
            logger.error("测试环境设置失败")
            return False

        try:
            # 运行各项测试
            tests = [
                ("connection", self.test_websocket_connection),
                ("ping_pong", self.test_ping_pong),
                ("channel_join", self.test_channel_join_leave),
                ("message_sending", self.test_message_sending),
                ("typing_indicator", self.test_typing_indicator),
                ("reaction_system", self.test_reaction_system),
                ("disconnect", self.test_disconnect),
            ]

            all_passed = True
            for test_name, test_func in tests:
                logger.info(f"运行测试: {test_name}")
                if not test_func():
                    all_passed = False
                    logger.error(f"测试失败: {test_name}")
                else:
                    logger.info(f"测试通过: {test_name}")

            # 输出测试结果
            logger.info("WebSocket功能测试结果:")
            for test_name, result in self.test_results.items():
                status = "✅ 通过" if result else "❌ 失败"
                logger.info(f"  {test_name}: {status}")

            return all_passed

        finally:
            # 清理测试环境
            self.cleanup_test_environment()


def test_websocket_functionality():
    """WebSocket功能测试主函数"""
    test = WebSocketFunctionalityTest()
    return test.run_all_tests()


if __name__ == "__main__":
    # 运行测试
    success = test_websocket_functionality()
    if success:
        print("🎉 所有WebSocket功能测试通过！")
    else:
        print("❌ 部分WebSocket功能测试失败")
