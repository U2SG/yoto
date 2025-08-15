"""
@提及系统测试
测试消息中的@提及功能
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


class TestMentionSystem:
    """@提及系统测试类"""

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
            user3 = User(
                username="charlie", password_hash=generate_password_hash("password123")
            )
            db.session.add_all([user1, user2, user3])
            db.session.commit()

            # 创建服务器
            server = Server(name="Test Server", owner_id=user1.id)
            db.session.add(server)
            db.session.commit()

            # 创建频道
            channel = Channel(name="Test Channel", server_id=server.id, type="text")
            db.session.add(channel)
            db.session.commit()

            return user1.id, user2.id, user3.id, server.id, channel.id

    def get_auth_token(self, client, app, user_id):
        """获取认证token"""
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                return None

            token = create_access_token(identity=str(user.id))
            return token

    def test_send_message_with_mentions(self, client, app):
        """测试发送包含@提及的消息"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送包含@提及的消息
        message_data = {
            "content": "Hello @bob and @charlie, how are you?",
            "type": "text",
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello @bob and @charlie, how are you?"
        assert "mentions" in data
        assert len(data["mentions"]) == 2  # bob和charlie
        assert user2_id in data["mentions"]
        assert user3_id in data["mentions"]

    def test_send_message_with_invalid_mentions(self, client, app):
        """测试发送包含无效@提及的消息"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送包含无效@提及的消息
        message_data = {
            "content": "Hello @nonexistent_user, how are you?",
            "type": "text",
        }

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello @nonexistent_user, how are you?"
        assert "mentions" in data
        assert len(data["mentions"]) == 0  # 无效用户不会被添加到mentions

    def test_send_message_without_mentions(self, client, app):
        """测试发送不包含@提及的消息"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送不包含@提及的消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello everyone!"
        assert "mentions" in data
        assert len(data["mentions"]) == 0  # 没有@提及

    def test_get_user_mentions(self, client, app):
        """测试获取用户被@的消息列表"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user2_id)  # 使用bob的token
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送几条包含@提及的消息
        user1_token = self.get_auth_token(client, app, user1_id)
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        # alice发送消息@bob
        message1 = {"content": "Hey @bob, check this out!", "type": "text"}
        client.post(
            f"/api/channels/{channel_id}/messages", json=message1, headers=user1_headers
        )

        # alice发送消息@bob和charlie
        message2 = {"content": "Hello @bob and @charlie!", "type": "text"}
        client.post(
            f"/api/channels/{channel_id}/messages", json=message2, headers=user1_headers
        )

        # 获取bob被@的消息列表
        resp = client.get("/api/users/mentions", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data
        assert len(data["messages"]) == 2  # bob被@了2次
        assert data["total"] == 2

        # 验证消息内容
        messages = data["messages"]
        assert any("Hey @bob, check this out!" in msg["content"] for msg in messages)
        assert any("Hello @bob and @charlie!" in msg["content"] for msg in messages)

    def test_get_user_mentions_with_pagination(self, client, app):
        """测试获取用户被@消息的分页功能"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送多条消息@bob
        for i in range(5):
            message_data = {"content": f"Message {i+1} @bob", "type": "text"}
            client.post(
                f"/api/channels/{channel_id}/messages",
                json=message_data,
                headers=auth_headers,
            )

        # 获取bob被@的消息，使用分页
        bob_token = self.get_auth_token(client, app, user2_id)
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        resp = client.get("/api/users/mentions?page=1&per_page=3", headers=bob_headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3  # 第一页3条
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert data["total"] == 5  # 总共5条

        # 获取第二页
        resp = client.get("/api/users/mentions?page=2&per_page=3", headers=bob_headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 2  # 第二页2条
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert data["total"] == 5

    def test_get_user_mentions_with_channel_filter(self, client, app):
        """测试获取用户被@消息的频道过滤功能"""
        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)

        # 创建第二个频道
        with app.app_context():
            channel2 = Channel(name="Test Channel 2", server_id=server_id, type="text")
            db.session.add(channel2)
            db.session.commit()
            channel2_id = channel2.id

        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 在第一个频道发送消息@bob
        message1 = {"content": "Hey @bob in channel 1!", "type": "text"}
        client.post(
            f"/api/channels/{channel_id}/messages", json=message1, headers=auth_headers
        )

        # 在第二个频道发送消息@bob
        message2 = {"content": "Hey @bob in channel 2!", "type": "text"}
        client.post(
            f"/api/channels/{channel2_id}/messages", json=message2, headers=auth_headers
        )

        # 获取bob被@的消息，过滤第一个频道
        bob_token = self.get_auth_token(client, app, user2_id)
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        resp = client.get(
            f"/api/users/mentions?channel_id={channel_id}", headers=bob_headers
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 1  # 只有第一个频道的消息
        assert "Hey @bob in channel 1!" in data["messages"][0]["content"]

    def test_mention_with_chinese_username(self, client, app):
        """测试中文用户名的@提及"""
        with app.app_context():
            # 创建中文用户名用户
            chinese_user = User(
                username="张三", password_hash=generate_password_hash("password123")
            )
            db.session.add(chinese_user)
            db.session.commit()
            chinese_user_id = chinese_user.id

        user1_id, user2_id, user3_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送包含中文用户名@提及的消息
        message_data = {"content": "Hello @张三, how are you?", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello @张三, how are you?"
        assert "mentions" in data
        assert len(data["mentions"]) == 1
        assert chinese_user_id in data["mentions"]
