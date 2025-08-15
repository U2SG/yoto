"""
消息持久化系统测试
测试消息的发送、编辑、删除等功能
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash
import json


class TestMessagePersistence:
    """消息持久化测试类"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app("testing")
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return app.test_client()

    def create_test_data(self, app):
        """创建测试数据"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)
            db.session.commit()

            # 创建服务器
            server = Server(name="Test Server", owner_id=user.id)
            db.session.add(server)
            db.session.commit()

            # 创建频道
            channel = Channel(name="Test Channel", server_id=server.id, type="text")
            db.session.add(channel)
            db.session.commit()

            return user.id, server.id, channel.id

    def get_auth_token(self, client, app):
        """获取认证token"""
        with app.app_context():
            login_data = {"username": "testuser", "password": "password123"}
            resp = client.post("/api/auth/login", json=login_data)
            if resp.status_code != 200:
                print(f"登录失败: {resp.status_code} - {resp.get_json()}")
                return None
            data = resp.get_json()
            if not data or "access_token" not in data:
                print(f"登录响应格式错误: {data}")
                return None
            return data["access_token"]

    def test_send_message(self, client, app):
        """测试发送消息"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        assert token is not None, "获取认证token失败"

        auth_headers = {"Authorization": f"Bearer {token}"}

        message_data = {"content": "Hello, World!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello, World!"
        assert data["type"] == "text"
        assert data["channel_id"] == channel_id

    def test_list_messages(self, client, app):
        """测试获取消息列表"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送几条消息
        messages = [
            {"content": "Message 1", "type": "text"},
            {"content": "Message 2", "type": "text"},
            {"content": "Message 3", "type": "text"},
        ]

        for msg in messages:
            client.post(
                f"/api/channels/{channel_id}/messages", json=msg, headers=auth_headers
            )

        # 获取消息列表
        resp = client.get(f"/api/channels/{channel_id}/messages")
        assert resp.status_code == 200

        data = resp.json
        assert len(data["messages"]) == 3
        assert data["total"] == 3

    def test_edit_message(self, client, app):
        """测试编辑消息"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送消息
        message_data = {"content": "Original message", "type": "text"}
        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )
        message_id = resp.json["id"]

        # 编辑消息
        edit_data = {"content": "Edited message"}
        resp = client.patch(
            f"/api/channels/{channel_id}/messages/{message_id}",
            json=edit_data,
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json
        assert data["content"] == "Edited message"
        assert data["is_edited"] == True

    def test_delete_message(self, client, app):
        """测试删除消息"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送消息
        message_data = {"content": "Message to delete", "type": "text"}
        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )
        message_id = resp.json["id"]

        # 删除消息
        resp = client.delete(
            f"/api/channels/{channel_id}/messages/{message_id}", headers=auth_headers
        )

        assert resp.status_code == 200

        # 验证消息已被软删除（不在列表中显示）
        resp = client.get(f"/api/channels/{channel_id}/messages")
        assert resp.status_code == 200
        assert len(resp.json["messages"]) == 0

    def test_get_message_detail(self, client, app):
        """测试获取消息详情"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送消息
        message_data = {"content": "Test message", "type": "text"}
        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )
        message_id = resp.json["id"]

        # 获取消息详情
        resp = client.get(f"/api/channels/{channel_id}/messages/{message_id}")
        assert resp.status_code == 200

        data = resp.json
        assert data["id"] == message_id
        assert data["content"] == "Test message"
        assert data["is_edited"] == False

    def test_edit_others_message_fails(self, client, app):
        """测试编辑他人消息失败"""
        user_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app)
        auth_headers = {"Authorization": f"Bearer {token}"}

        with client.application.app_context():
            # 创建另一个用户
            other_user = User(
                username="otheruser",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(other_user)
            db.session.commit()

            # 用另一个用户发送消息
            message = Message(
                channel_id=channel_id,
                user_id=other_user.id,
                type="text",
                content="Other user message",
            )
            db.session.add(message)
            db.session.commit()
            message_id = message.id

            # 尝试编辑他人消息
            edit_data = {"content": "Trying to edit"}
            resp = client.patch(
                f"/api/channels/{channel_id}/messages/{message_id}",
                json=edit_data,
                headers=auth_headers,
            )

            assert resp.status_code == 403
