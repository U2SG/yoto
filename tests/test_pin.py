import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime, timedelta


class TestMessagePin:
    @pytest.fixture
    def app(self):
        app = create_app("testing")
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def create_test_data(self, app):
        """创建测试数据"""
        with app.app_context():
            # 创建用户
            user1 = User(
                username="user1", password_hash=generate_password_hash("password123")
            )
            user2 = User(
                username="user2", password_hash=generate_password_hash("password123")
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

            # 创建服务器
            server1 = Server(name="Test Server 1", owner_id=user1.id)
            server2 = Server(name="Test Server 2", owner_id=user2.id)
            db.session.add(server1)
            db.session.add(server2)
            db.session.commit()

            # 创建频道
            channel1 = Channel(name="General", server_id=server1.id, type="text")
            channel2 = Channel(name="Announcements", server_id=server1.id, type="text")
            channel3 = Channel(name="General", server_id=server2.id, type="text")
            db.session.add(channel1)
            db.session.add(channel2)
            db.session.add(channel3)
            db.session.commit()

            # 创建服务器成员
            member1 = ServerMember(user_id=user1.id, server_id=server1.id)
            member2 = ServerMember(user_id=user2.id, server_id=server1.id)
            db.session.add(member1)
            db.session.add(member2)
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
            token = create_access_token(identity=str(user.id))
            return token

    def test_pin_message_success(self, client, app):
        """测试成功置顶消息"""
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
        message_id = resp.get_json()["id"]

        # 置顶消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/pin",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        assert "pinned_message" in data
        assert data["pinned_message"]["is_pinned"] == True
        assert data["pinned_message"]["pinned_by"] == user1_id

    def test_unpin_message_success(self, client, app):
        """测试成功取消置顶消息"""
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
        message_id = resp.get_json()["id"]

        # 先置顶消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/pin",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # 取消置顶消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/unpin",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data

    def test_pin_already_pinned_message(self, client, app):
        """测试置顶已经置顶的消息"""
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
        message_id = resp.get_json()["id"]

        # 第一次置顶
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/pin",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # 再次置顶
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/pin",
            headers=auth_headers,
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "已经是置顶状态" in data["error"]

    def test_unpin_not_pinned_message(self, client, app):
        """测试取消置顶未置顶的消息"""
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
        message_id = resp.get_json()["id"]

        # 尝试取消置顶未置顶的消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{message_id}/unpin",
            headers=auth_headers,
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "不是置顶状态" in data["error"]

    def test_pin_nonexistent_message(self, client, app):
        """测试置顶不存在的消息"""
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

        # 尝试置顶不存在的消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/99999/pin", headers=auth_headers
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不存在或已删除" in data["error"]

    def test_pin_message_wrong_channel(self, client, app):
        """测试置顶消息时指定错误的频道"""
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
            json={"content": "This is a test message", "type": "text"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        message_id = resp.get_json()["id"]

        # 尝试从channel2置顶channel1的消息
        resp = client.post(
            f"/api/channels/{channel2_id}/messages/{message_id}/pin",
            headers=auth_headers,
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不在指定频道中" in data["error"]

    def test_pin_message_without_authentication(self, client, app):
        """测试未认证的置顶消息"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)

        # 未认证的置顶请求
        resp = client.post(f"/api/channels/{channel1_id}/messages/1/pin")

        assert resp.status_code == 401

    def test_get_pinned_messages(self, client, app):
        """测试获取置顶消息列表"""
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

        # 发送多条测试消息
        messages = []
        for i in range(3):
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json={"content": f"Test message {i+1}", "type": "text"},
                headers=auth_headers,
            )
            assert resp.status_code == 201
            messages.append(resp.get_json()["id"])

        # 置顶第一条和第三条消息
        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{messages[0]}/pin",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        resp = client.post(
            f"/api/channels/{channel1_id}/messages/{messages[2]}/pin",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # 获取置顶消息列表
        resp = client.get(f"/api/channels/{channel1_id}/messages/pinned")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "pinned_messages" in data
        assert "count" in data
        assert data["count"] == 2

        # 验证置顶消息按置顶时间倒序排列
        pinned_messages = data["pinned_messages"]
        assert len(pinned_messages) == 2
        assert pinned_messages[0]["pinned_at"] >= pinned_messages[1]["pinned_at"]

    def test_get_pinned_messages_empty(self, client, app):
        """测试获取空置顶消息列表"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)

        # 获取置顶消息列表（空）
        resp = client.get(f"/api/channels/{channel1_id}/messages/pinned")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 0
        assert len(data["pinned_messages"]) == 0

    def test_get_pinned_messages_nonexistent_channel(self, client, app):
        """测试获取不存在频道的置顶消息"""
        # 获取不存在频道的置顶消息
        resp = client.get("/api/channels/99999/messages/pinned")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "频道不存在" in data["error"]
