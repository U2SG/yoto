"""
基本功能测试
验证应用是否能正常启动和基本功能
"""

import pytest
from app import create_app
from app.core.extensions import db


def test_app_creation():
    """测试应用创建"""
    app = create_app("testing")
    assert app is not None
    assert app.config["TESTING"] == True


def test_database_creation():
    """测试数据库创建"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 检查表是否创建
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"创建的数据库表: {tables}")

        # 至少应该有users表
        assert "users" in tables

        db.drop_all()


def test_auth_endpoints():
    """测试认证端点"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        client = app.test_client()

        # 测试注册端点
        resp = client.post("/api/auth/register", json={})
        print(f"注册端点响应: {resp.status_code}")
        # 应该返回400（参数错误）而不是404（路由不存在）
        assert resp.status_code == 400

        # 测试登录端点
        resp = client.post("/api/auth/login", json={})
        print(f"登录端点响应: {resp.status_code}")
        # 应该返回400（参数错误）而不是404（路由不存在）
        assert resp.status_code == 400

        db.drop_all()


def test_channels_endpoints():
    """测试频道端点"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        client = app.test_client()

        # 测试频道列表端点
        resp = client.get("/api/channels")
        print(f"频道列表端点响应: {resp.status_code}")
        # 应该返回200或401，而不是404
        assert resp.status_code in [200, 401]

        db.drop_all()
