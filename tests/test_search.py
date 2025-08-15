"""
消息搜索功能测试
测试消息搜索相关的功能
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


class TestMessageSearch:
    """消息搜索功能测试类"""

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

    def test_search_messages_in_channel(self, client, app):
        """测试在频道内搜索消息"""
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

        # 发送一些测试消息
        messages = [
            {"content": "Hello world!", "type": "text"},
            {"content": "This is a test message", "type": "text"},
            {"content": "Another message with hello", "type": "text"},
            {"content": "No match here", "type": "text"},
        ]

        for msg_data in messages:
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 搜索包含"hello"的消息
        resp = client.get(f"/api/channels/{channel1_id}/messages/search?q=hello")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data
        assert (
            len(data["messages"]) == 2
        )  # "Hello world!" 和 "Another message with hello"
        assert data["query"] == "hello"

        # 验证高亮显示
        for message in data["messages"]:
            assert "**hello**" in message["highlighted_content"].lower()

    def test_search_messages_with_filters(self, client, app):
        """测试带过滤条件的消息搜索"""
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

        # 发送一些测试消息
        messages = [
            {"content": "Message from alice", "type": "text"},
            {"content": "Message from bob", "type": "text"},
            {"content": "Another message from alice", "type": "text"},
        ]

        for msg_data in messages:
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 搜索alice发送的消息（只搜索包含"alice"的消息）
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=alice&user_id={user1_id}"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 2  # 只有alice发送的消息包含"alice"

        # 验证所有返回的消息都是alice发送的
        for message in data["messages"]:
            assert message["user_id"] == user1_id
            assert "alice" in message["content"].lower()

    def test_search_messages_with_date_filter(self, client, app):
        """测试带日期过滤的消息搜索"""
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

        # 发送一些测试消息
        messages = [
            {"content": "Message 1", "type": "text"},
            {"content": "Message 2", "type": "text"},
            {"content": "Message 3", "type": "text"},
        ]

        for msg_data in messages:
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 获取今天的日期
        today = datetime.now().strftime("%Y-%m-%d")

        # 搜索今天的消息
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=Message&start_date={today}&end_date={today}"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3  # 所有消息都是今天发送的

    def test_search_messages_with_pagination(self, client, app):
        """测试消息搜索的分页功能"""
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
        for i in range(5):
            msg_data = {"content": f"Test message {i+1}", "type": "text"}
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 搜索并分页
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=Test&page=1&per_page=3"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3  # 第一页3条
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert data["total"] == 5  # 总共5条

        # 获取第二页
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=Test&page=2&per_page=3"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 2  # 第二页2条
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert data["total"] == 5

    def test_search_messages_with_sorting(self, client, app):
        """测试消息搜索的排序功能"""
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

        # 发送一些测试消息
        messages = [
            {"content": "First message", "type": "text"},
            {"content": "Second message", "type": "text"},
            {"content": "Third message", "type": "text"},
        ]

        for msg_data in messages:
            resp = client.post(
                f"/api/channels/{channel1_id}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 按时间正序搜索
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=message&sort=date_asc"
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["messages"]) == 3

        # 验证排序（正序：First, Second, Third）
        assert "First message" in data["messages"][0]["content"]
        assert "Second message" in data["messages"][1]["content"]
        assert "Third message" in data["messages"][2]["content"]

    def test_global_search_messages(self, client, app):
        """测试全局消息搜索"""
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

        # 在多个频道发送消息
        messages = [
            {"content": "Message in channel 1", "type": "text"},
            {"content": "Message in channel 2", "type": "text"},
            {"content": "Another message in channel 1", "type": "text"},
        ]

        channels = [channel1_id, channel2_id, channel1_id]
        for i, msg_data in enumerate(messages):
            resp = client.post(
                f"/api/channels/{channels[i]}/messages",
                json=msg_data,
                headers=auth_headers,
            )
            assert resp.status_code == 201

        # 全局搜索（需要认证）
        resp = client.get("/api/messages/search?q=Message", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data
        assert len(data["messages"]) == 3

        # 验证返回的频道和服务器信息
        for message in data["messages"]:
            assert "channel_name" in message
            assert "server_name" in message
            assert message["channel_name"] in ["General", "Random"]
            assert message["server_name"] == "Test Server 1"

    def test_search_messages_with_invalid_params(self, client, app):
        """测试无效参数的消息搜索"""
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

        # 测试空关键词
        resp = client.get(f"/api/channels/{channel1_id}/messages/search?q=")

        assert resp.status_code == 400
        data = resp.get_json()
        assert "搜索关键词必填" in data["error"]

        # 测试无效的消息类型
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test&message_type=invalid"
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "无效的消息类型" in data["error"]

        # 测试无效的日期格式
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test&start_date=invalid-date"
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "开始日期格式错误" in data["error"]

    def test_search_messages_nonexistent_channel(self, client, app):
        """测试在不存在频道中搜索消息"""
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

        # 在不存在频道中搜索
        resp = client.get("/api/channels/99999/messages/search?q=test")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "频道不存在" in data["error"]

    def test_global_search_without_authentication(self, client, app):
        """测试未认证的全局搜索"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)

        # 未认证的全局搜索
        resp = client.get("/api/messages/search?q=test")

        assert resp.status_code == 401
