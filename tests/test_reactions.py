"""
表情反应功能测试
测试消息表情反应相关的功能
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server
from app.blueprints.channels.models import Channel, Message, MessageReaction
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


class TestMessageReactions:
    """表情反应功能测试类"""

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

    def test_add_message_reaction(self, client, app):
        """测试添加表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "表情反应添加成功"
        assert data["reaction"] == "👍"

    def test_add_duplicate_reaction(self, client, app):
        """测试添加重复的表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201

        # 再次添加相同的表情反应
        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 409
        data = resp.get_json()
        assert "表情反应已存在" in data["error"]

    def test_remove_message_reaction(self, client, app):
        """测试移除表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201

        # 移除表情反应
        resp = client.delete(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions?reaction=👍",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "表情反应移除成功"

    def test_remove_nonexistent_reaction(self, client, app):
        """测试移除不存在的表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 尝试移除不存在的表情反应
        resp = client.delete(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions?reaction=👍",
            headers=auth_headers,
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "表情反应不存在" in data["error"]

    def test_get_message_reactions(self, client, app):
        """测试获取消息的表情反应列表"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token1 = self.get_auth_token(client, app, user1_id)
        token2 = self.get_auth_token(client, app, user2_id)
        auth_headers1 = {"Authorization": f"Bearer {token1}"}
        auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers1,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 添加多个表情反应
        reactions = ["👍", "❤️", "😂"]
        for reaction in reactions:
            reaction_data = {"reaction": reaction}
            resp = client.post(
                f"/api/channels/{channel_id}/messages/{message_id}/reactions",
                json=reaction_data,
                headers=auth_headers1,
            )
            assert resp.status_code == 201

        # bob也添加一个表情反应
        reaction_data = {"reaction": "👍"}
        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers2,
        )
        assert resp.status_code == 201

        # 获取表情反应列表
        resp = client.get(f"/api/channels/{channel_id}/messages/{message_id}/reactions")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "reactions" in data
        assert len(data["reactions"]) == 3  # 👍, ❤️, 😂

        # 验证👍表情有两个用户
        thumbs_up_reaction = next(r for r in data["reactions"] if r["reaction"] == "👍")
        assert thumbs_up_reaction["count"] == 2
        assert len(thumbs_up_reaction["users"]) == 2

    def test_message_list_with_reactions(self, client, app):
        """测试消息列表包含表情反应信息"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 先发送一条消息
        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201

        # 获取消息列表
        resp = client.get(f"/api/channels/{channel_id}/messages")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "messages" in data

        # 找到消息并验证表情反应
        message_found = False
        for message in data["messages"]:
            if message["id"] == message_id:
                message_found = True
                assert "reactions" in message
                assert len(message["reactions"]) == 1
                assert message["reactions"][0]["reaction"] == "👍"
                assert message["reactions"][0]["count"] == 1
                break

        assert message_found, "消息未在列表中找到"

    def test_add_reaction_to_nonexistent_message(self, client, app):
        """测试为不存在的消息添加表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 尝试为不存在的消息添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/99999/reactions",
            json=reaction_data,
            headers=auth_headers,
        )

        assert resp.status_code == 404
        data = resp.get_json()
        assert "消息不存在" in data["error"]

    def test_add_reaction_without_authentication(self, client, app):
        """测试未认证用户添加表情反应"""
        user1_id, user2_id, server_id, channel_id = self.create_test_data(app)

        # 先发送一条消息（使用认证）
        token = self.get_auth_token(client, app, user1_id)
        auth_headers = {"Authorization": f"Bearer {token}"}

        message_data = {"content": "Hello everyone!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        message_data = resp.get_json()
        message_id = message_data["id"]

        # 尝试未认证添加表情反应
        reaction_data = {"reaction": "👍"}

        resp = client.post(
            f"/api/channels/{channel_id}/messages/{message_id}/reactions",
            json=reaction_data,
        )

        assert resp.status_code == 401
