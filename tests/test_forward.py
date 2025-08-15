"""
消息转发功能测试
测试消息转发相关的功能
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime, timedelta


class TestMessageForward:
    """消息转发功能测试类"""

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
            user1 = User(
                username="alice", password_hash=generate_password_hash("password123")
            )
            user2 = User(
                username="bob", password_hash=generate_password_hash("password123")
            )
            db.session.add_all([user1, user2])
            db.session.commit()

            # 创建服务器
            server1 = Server(name="Test Server 1", owner_id=user1.id)
            server2 = Server(name="Test Server 2", owner_id=user2.id)
            db.session.add_all([server1, server2])
            db.session.commit()

            # 创建频道
            channel1 = Channel(name="General", server_id=server1.id, type="text")
            channel2 = Channel(name="Random", server_id=server1.id, type="text")
            channel3 = Channel(name="Other Server", server_id=server2.id, type="text")
            db.session.add_all([channel1, channel2, channel3])
            db.session.commit()

            # 添加用户到服务器
            member1 = ServerMember(user_id=user1.id, server_id=server1.id)
            member2 = ServerMember(user_id=user1.id, server_id=server2.id)
            db.session.add_all([member1, member2])
            db.session.commit()

            return (
                user1.id,
                user2.id,
                server1.id,
                server2.id,
                channel1.id,
                channel2.id,
                channel3.id,
            )

    def get_auth_token(self, client, app, user_id):
        """获取认证token"""
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                return None

            token = create_access_token(identity=str(user.id))
            return token

    def test_forward_message_success(self, client, app):
        """测试成功转发消息"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "This is a test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 转发消息到另一个频道
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": [channel2_id], "comment": "Important message"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        assert "forwarded_messages" in data
        assert len(data["forwarded_messages"]) == 1

        # 验证转发消息的属性
        forwarded_msg = data["forwarded_messages"][0]
        assert forwarded_msg["channel_id"] == channel2_id
        assert forwarded_msg["content"] == "This is a test message"
        assert forwarded_msg["is_forwarded"] == True
        assert forwarded_msg["original_message_id"] == message_id
        assert forwarded_msg["original_channel_id"] == channel1_id
        assert forwarded_msg["original_user_id"] == user1_id
        assert forwarded_msg["forward_comment"] == "Important message"

    def test_forward_message_to_multiple_channels(self, client, app):
        """测试转发消息到多个频道"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Multi-channel message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 转发到多个频道
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": [channel2_id, channel3_id]},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["forwarded_messages"]) == 2

        # 验证两个频道都收到了转发消息
        channel_ids = [msg["channel_id"] for msg in data["forwarded_messages"]]
        assert channel2_id in channel_ids
        assert channel3_id in channel_ids

    def test_forward_message_without_comment(self, client, app):
        """测试转发消息时不添加评论"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Message without comment", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 转发消息，不添加评论
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": [channel2_id]},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        forwarded_msg = data["forwarded_messages"][0]
        assert forwarded_msg["forward_comment"] is None

    def test_forward_nonexistent_message(self, client, app):
        """测试转发不存在的消息"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 尝试转发不存在的消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/99999/forward",
            json={"target_channels": [channel2_id]},
            headers=auth_headers,
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不存在或已删除" in data["error"]

    def test_forward_message_to_nonexistent_channel(self, client, app):
        """测试转发到不存在的频道"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 转发到不存在的频道
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": [99999]},
            headers=auth_headers,
        )

        assert resp.status_code == 403
        data = resp.get_json()
        assert "没有有效的目标频道或权限不足" in data["error"]

    def test_forward_message_without_target_channels(self, client, app):
        """测试转发消息时没有指定目标频道"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 转发时没有指定目标频道
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": []},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "目标频道列表不能为空" in data["error"]

    def test_forward_message_without_authentication(self, client, app):
        """测试未认证的转发消息"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)

        # 未认证的转发请求
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/1/forward",
            json={"target_channels": [channel2_id]},
        )

        assert resp.status_code == 401

    def test_forward_message_wrong_channel(self, client, app):
        """测试转发消息时指定错误的频道"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 在channel1发送消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 尝试从channel2转发channel1的消息
        resp = client.post(
            f"/api/channels/{channel2_id}/messages/{message_id}/forward",
            json={"target_channels": [channel3_id]},
            headers=auth_headers,
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不在指定频道中" in data["error"]

    def test_forward_message_permission_check(self, client, app):
        """测试转发消息的权限检查"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送一条测试消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages",
            json={"content": "Test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 尝试转发到用户没有权限的频道（这里需要创建一个用户没有权限的频道）
        # 由于测试数据中user1已经加入了两个服务器，我们测试一个不存在的频道
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/forward",
            json={"target_channels": [99999]},
            headers=auth_headers,
        )

        assert resp.status_code == 403
        data = resp.get_json()
        assert "没有有效的目标频道或权限不足" in data["error"]
