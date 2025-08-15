"""
消息回复功能测试
测试消息回复相关的功能
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


class TestMessageReplies:
    """消息回复功能测试类"""

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
            server = Server(name="Test Server", owner_id=user1.id)
            db.session.add(server)
            db.session.commit()

            # 创建频道
            channel = Channel(name="Test Channel", server_id=server.id, type="text")
            db.session.add(channel)
            db.session.commit()

            return user1.id, user2.id, server.id, channel.id

    def get_auth_token(self, client, app, user_id):
        """获取认证token"""
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                return None

            token = create_access_token(identity=str(user.id))
            return token

    def test_send_message_with_reply(self, client, app):
        """测试发送回复消息"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条原始消息
        original_message = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=original_message,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        original_data = resp.get_json()
        original_message_id = original_data["id"]

        # 发送回复消息
        reply_message = {
            "content": "This is a reply!",
            "type": "text",
            "reply_to": original_message_id,
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=reply_message,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        reply_data = resp.get_json()
        assert reply_data["content"] == "This is a reply!"
        assert reply_data["reply_to_id"] == original_message_id

    def test_send_message_with_invalid_reply(self, client, app):
        """测试发送无效回复消息"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送回复到不存在的消息
        reply_message = {
            "content": "This is a reply!",
            "type": "text",
            "reply_to": 99999,  # 不存在的消息ID
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=reply_message,
            headers=auth_headers,
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "回复的消息不存在" in data["error"]

    def test_send_message_without_reply(self, client, app):
        """测试发送不包含回复的消息"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送普通消息
        message = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages", json=message, headers=auth_headers
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello everyone!"
        assert data["reply_to_id"] is None

    def test_get_message_replies(self, client, app):
        """测试获取消息回复列表"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token1 = self.get_auth_token(client, app, user1_id)
        token2 = self.get_auth_token(client, app, user2_id)
        auth_headers1 = {"Authorization": f"Bearer {token1}"}
        auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # 先发送一条原始消息
        original_message = {"content": "Original message", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=original_message,
            headers=auth_headers1,
        )

        assert resp.status_code == 201
        original_data = resp.get_json()
        original_message_id = original_data["id"]

        # 发送多条回复消息
        for i in range(3):
            reply_message = {
                "content": f"Reply {i+1}",
                "type": "text",
                "reply_to": original_message_id,
            }

            resp = client.post(
                f"/api/channels/{channel_id}/messages",
                json=reply_message,
                headers=auth_headers2,
            )

            assert resp.status_code == 201

        # 获取回复列表
        resp = client.get(
            f"/api/channels/{channel_id}/messages/{original_message_id}/replies"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "replies" in data
        assert len(data["replies"]) == 3
        assert data["total"] == 3

        # 验证回复内容
        replies = data["replies"]
        assert any("Reply 1" in reply["content"] for reply in replies)
        assert any("Reply 2" in reply["content"] for reply in replies)
        assert any("Reply 3" in reply["content"] for reply in replies)

    def test_get_message_replies_with_pagination(self, client, app):
        """测试获取消息回复列表的分页功能"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token1 = self.get_auth_token(client, app, user1_id)
        token2 = self.get_auth_token(client, app, user2_id)
        auth_headers1 = {"Authorization": f"Bearer {token1}"}
        auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # 先发送一条原始消息
        original_message = {"content": "Original message", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=original_message,
            headers=auth_headers1,
        )

        assert resp.status_code == 201
        original_data = resp.get_json()
        original_message_id = original_data["id"]

        # 发送多条回复消息
        for i in range(5):
            reply_message = {
                "content": f"Reply {i+1}",
                "type": "text",
                "reply_to": original_message_id,
            }

            resp = client.post(
                f"/api/channels/{channel_id}/messages",
                json=reply_message,
                headers=auth_headers2,
            )

            assert resp.status_code == 201

        # 获取回复列表，使用分页
        resp = client.get(
            f"/api/channels/{channel_id}/messages/{original_message_id}/replies?page=1&per_page=3"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["replies"]) == 3  # 第一页3条
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert data["total"] == 5  # 总共5条

        # 获取第二页
        resp = client.get(
            f"/api/channels/{channel_id}/messages/{original_message_id}/replies?page=2&per_page=3"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["replies"]) == 2  # 第二页2条
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert data["total"] == 5

    def test_get_message_replies_nonexistent_message(self, client, app):
        """测试获取不存在消息的回复列表"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)

        # 尝试获取不存在消息的回复
        resp = client.get(f"/api/channels/{channel_id}/messages/99999/replies")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不存在" in data["error"]

    def test_message_list_with_reply_info(self, client, app):
        """测试消息列表包含回复信息"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token1 = self.get_auth_token(client, app, user1_id)
        token2 = self.get_auth_token(client, app, user2_id)
        auth_headers1 = {"Authorization": f"Bearer {token1}"}
        auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # 先发送一条原始消息
        original_message = {
            "content": "Original message with long content that should be truncated in reply preview",
            "type": "text",
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=original_message,
            headers=auth_headers1,
        )

        assert resp.status_code == 201
        original_data = resp.get_json()
        original_message_id = original_data["id"]

        # 发送回复消息
        reply_message = {
            "content": "This is a reply to the original message",
            "type": "text",
            "reply_to": original_message_id,
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=reply_message,
            headers=auth_headers2,
        )

        assert resp.status_code == 201

        # 获取消息列表
        resp = client.get(f"/api/channels/{channel_id}/messages")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data

        # 找到回复消息
        reply_found = False
        for message in data["messages"]:
            if message.get("reply_to_id") == original_message_id:
                reply_found = True
                assert "reply_to" in message
                reply_info = message["reply_to"]
                assert reply_info["id"] == original_message_id
                assert reply_info["user_id"] == user1_id
                assert reply_info["username"] == "alice"
                assert "Original message with long content" in reply_info["content"]
                break

        assert reply_found, "回复消息未在列表中找到"
