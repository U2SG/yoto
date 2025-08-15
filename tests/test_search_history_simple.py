import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message, SearchHistory
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


class TestSearchHistorySimple:
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

    def test_search_history_model_creation(self, app):
        """测试SearchHistory模型的基本创建"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)
            db.session.commit()

            # 创建搜索历史记录
            search_history = SearchHistory(
                user_id=user.id,
                query="test query",
                search_type="channel",
                channel_id=1,
                filters={"user_id": 1},
                result_count=5,
            )
            db.session.add(search_history)
            db.session.commit()

            # 验证创建成功
            assert search_history.id is not None
            assert search_history.query == "test query"
            assert search_history.search_type == "channel"
            assert search_history.user_id == user.id

    def test_search_history_query(self, app):
        """测试SearchHistory模型的查询功能"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)
            db.session.commit()

            # 创建多个搜索历史记录
            history1 = SearchHistory(
                user_id=user.id,
                query="test1",
                search_type="channel",
                channel_id=1,
                result_count=3,
            )
            history2 = SearchHistory(
                user_id=user.id,
                query="test2",
                search_type="global",
                channel_id=None,
                result_count=7,
            )
            db.session.add(history1)
            db.session.add(history2)
            db.session.commit()

            # 查询用户的搜索历史
            histories = db.session.query(SearchHistory).filter_by(user_id=user.id).all()
            assert len(histories) == 2

            # 验证查询结果
            channel_histories = (
                db.session.query(SearchHistory)
                .filter_by(user_id=user.id, search_type="channel")
                .all()
            )
            assert len(channel_histories) == 1
            assert channel_histories[0].query == "test1"

            global_histories = (
                db.session.query(SearchHistory)
                .filter_by(user_id=user.id, search_type="global")
                .all()
            )
            assert len(global_histories) == 1
            assert global_histories[0].query == "test2"

    def test_search_history_api_basic(self, client, app):
        """测试搜索历史API的基本功能"""
        with app.app_context():
            # 创建用户
            user = User(
                username="testuser", password_hash=generate_password_hash("password123")
            )
            db.session.add(user)
            db.session.commit()

            # 获取认证token
            token = create_access_token(identity=str(user.id))
            auth_headers = {"Authorization": f"Bearer {token}"}

            # 测试获取搜索历史（应该为空）
            resp = client.get("/api/search/history", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["total"] == 0
            assert len(data["search_history"]) == 0

    def test_search_history_authentication(self, client, app):
        """测试搜索历史API的认证要求"""
        # 未认证的请求应该返回401
        resp = client.get("/api/search/history")
        assert resp.status_code == 401

        resp = client.delete("/api/search/history/1")
        assert resp.status_code == 401

        resp = client.delete("/api/search/history")
        assert resp.status_code == 401
