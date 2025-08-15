#!/usr/bin/env python3
"""
基础SearchHistory测试
"""

from app import create_app
from app.core.extensions import db
from app.blueprints.channels.models import SearchHistory


def test_search_history_basic():
    """基础SearchHistory测试"""
    app = create_app("testing")

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 创建测试数据
        search_history = SearchHistory(
            user_id=1,
            query="test query",
            search_type="channel",
            channel_id=1,
            filters={"user_id": 1},
            result_count=5,
        )

        # 保存到数据库
        db.session.add(search_history)
        db.session.commit()

        # 查询验证
        result = db.session.query(SearchHistory).filter_by(user_id=1).first()
        assert result is not None
        assert result.query == "test query"
        assert result.search_type == "channel"
        assert result.channel_id == 1
        assert result.result_count == 5

        print("✅ SearchHistory基础测试通过！")

        # 清理
        db.session.remove()
        db.drop_all()


if __name__ == "__main__":
    test_search_history_basic()
