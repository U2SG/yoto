import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message, SearchHistory
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime, timedelta


class TestSearchHistory:
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

    def test_get_search_history(self, client, app):
        """测试获取搜索历史记录"""
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

        # 先进行一些搜索来创建历史记录
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test", headers=auth_headers
        )
        assert resp.status_code == 200

        resp = client.get("/api/messages/search?q=hello", headers=auth_headers)
        assert resp.status_code == 200

        # 获取搜索历史
        resp = client.get("/api/search/history", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.get_json()
        assert "search_history" in data
        assert "page" in data
        assert "per_page" in data
        assert "total" in data
        assert data["total"] >= 2  # 至少应该有2条搜索记录

    def test_get_search_history_with_filters(self, client, app):
        """测试带过滤条件的搜索历史获取"""
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

        # 进行不同类型的搜索
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test", headers=auth_headers
        )
        assert resp.status_code == 200

        resp = client.get("/api/messages/search?q=hello", headers=auth_headers)
        assert resp.status_code == 200

        # 按搜索类型过滤
        resp = client.get(
            "/api/search/history?search_type=channel", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        for record in data["search_history"]:
            assert record["search_type"] == "channel"

        resp = client.get(
            "/api/search/history?search_type=global", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        for record in data["search_history"]:
            assert record["search_type"] == "global"

    def test_get_search_history_pagination(self, client, app):
        """测试搜索历史分页"""
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

        # 进行多次搜索
        for i in range(5):
            resp = client.get(
                f"/api/channels/{channel1_id}/messages/search?q=test{i}",
                headers=auth_headers,
            )
            assert resp.status_code == 200

        # 测试分页
        resp = client.get("/api/search/history?page=1&per_page=3", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["search_history"]) <= 3
        assert data["page"] == 1
        assert data["per_page"] == 3

    def test_delete_search_history(self, client, app):
        """测试删除指定的搜索历史记录"""
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

        # 进行搜索
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test", headers=auth_headers
        )
        assert resp.status_code == 200

        # 获取搜索历史
        resp = client.get("/api/search/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        history_id = data["search_history"][0]["id"]

        # 删除指定的搜索历史记录
        resp = client.delete(f"/api/search/history/{history_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data

    def test_delete_nonexistent_search_history(self, client, app):
        """测试删除不存在的搜索历史记录"""
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

        # 删除不存在的记录
        resp = client.delete("/api/search/history/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "搜索历史记录不存在" in data["error"]

    def test_delete_others_search_history(self, client, app):
        """测试删除他人的搜索历史记录"""
        (
            user1_id,
            user2_id,
            server1_id,
            server2_id,
            channel1_id,
            channel2_id,
            channel3_id,
        ) = self.create_test_data(app)
        token1 = self.get_auth_token(client, app, user1_id)
        token2 = self.get_auth_token(client, app, user2_id)
        auth_headers1 = {"Authorization": f"Bearer {token1}"}
        auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # user1进行搜索
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test", headers=auth_headers1
        )
        assert resp.status_code == 200

        # 获取user1的搜索历史
        resp = client.get("/api/search/history", headers=auth_headers1)
        assert resp.status_code == 200
        data = resp.get_json()
        history_id = data["search_history"][0]["id"]

        # user2尝试删除user1的搜索历史
        resp = client.delete(f"/api/search/history/{history_id}", headers=auth_headers2)
        assert resp.status_code == 403
        data = resp.get_json()
        assert "没有权限删除此记录" in data["error"]

    def test_clear_search_history(self, client, app):
        """测试清空搜索历史记录"""
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

        # 进行多次搜索
        for i in range(3):
            resp = client.get(
                f"/api/channels/{channel1_id}/messages/search?q=test{i}",
                headers=auth_headers,
            )
            assert resp.status_code == 200

        # 清空搜索历史
        resp = client.delete("/api/search/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        assert "deleted_count" in data
        assert data["deleted_count"] >= 3

        # 验证搜索历史已被清空
        resp = client.get("/api/search/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0

    def test_search_history_without_authentication(self, client, app):
        """测试未认证的搜索历史操作"""
        # 未认证的获取搜索历史
        resp = client.get("/api/search/history")
        assert resp.status_code == 401

        # 未认证的删除搜索历史
        resp = client.delete("/api/search/history/1")
        assert resp.status_code == 401

        # 未认证的清空搜索历史
        resp = client.delete("/api/search/history")
        assert resp.status_code == 401

    def test_search_history_record_creation(self, client, app):
        """测试搜索历史记录的创建"""
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

        # 进行频道内搜索
        resp = client.get(
            f"/api/channels/{channel1_id}/messages/search?q=test&user_id=1&message_type=text",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # 检查搜索历史记录
        with app.app_context():
            history = (
                db.session.query(SearchHistory).filter_by(user_id=user1_id).first()
            )
            assert history is not None
            assert history.query == "test"
            assert history.search_type == "channel"
            assert history.channel_id == channel1_id
            assert history.filters is not None
            assert "user_id" in history.filters
            assert "message_type" in history.filters

        # 进行全局搜索
        resp = client.get(
            "/api/messages/search?q=hello&server_id=1", headers=auth_headers
        )
        assert resp.status_code == 200

        # 检查全局搜索历史记录
        with app.app_context():
            history = (
                db.session.query(SearchHistory)
                .filter_by(user_id=user1_id, search_type="global")
                .first()
            )
            assert history is not None
            assert history.query == "hello"
            assert history.search_type == "global"
            assert history.channel_id is None
            assert history.filters is not None
            assert "server_id" in history.filters
