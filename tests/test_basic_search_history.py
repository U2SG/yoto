import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.channels.models import SearchHistory
from app.blueprints.auth.models import User
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token


def test_basic_search_history():
    """基本搜索历史测试"""
    app = create_app("testing")

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 创建测试用户
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

        # 验证记录创建成功
        result = db.session.query(SearchHistory).filter_by(user_id=user.id).first()
        assert result is not None
        assert result.query == "test query"
        assert result.search_type == "channel"
        assert result.channel_id == 1
        assert result.result_count == 5

        print("✅ 基本搜索历史测试通过！")

        # 测试API
        client = app.test_client()
        token = create_access_token(identity=str(user.id))
        headers = {"Authorization": f"Bearer {token}"}

        # 测试获取搜索历史API
        resp = client.get("/api/search/history", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "search_history" in data
        assert len(data["search_history"]) >= 1

        print("✅ 搜索历史API测试通过！")

        # 清理
        db.session.remove()
        db.drop_all()


if __name__ == "__main__":
    test_basic_search_history()
