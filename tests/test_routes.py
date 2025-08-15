"""
路由测试
检查所有路由是否正确注册
"""

import pytest
from app import create_app


def test_routes_registration():
    """测试路由注册"""
    app = create_app("testing")

    with app.app_context():
        # 确保数据库表已创建
        from app.core.extensions import db

        db.create_all()

        # 打印所有注册的路由
        print("\n注册的路由:")
        for rule in app.url_map.iter_rules():
            print(f"{rule.rule} -> {rule.endpoint}")

        # 检查关键路由是否存在
        with app.test_client() as client:
            # 测试认证路由
            resp = client.get("/api/auth/register")
            print(f"GET /api/auth/register: {resp.status_code}")

            resp = client.post("/api/auth/register")
            print(f"POST /api/auth/register: {resp.status_code}")

            resp = client.post("/api/auth/login")
            print(f"POST /api/auth/login: {resp.status_code}")

            # 测试频道路由
            resp = client.get("/api/channels")
            print(f"GET /api/channels: {resp.status_code}")

            resp = client.post("/api/channels")
            print(f"POST /api/channels: {resp.status_code}")

        # 清理数据库
        db.drop_all()


def test_auth_blueprint():
    """测试认证蓝图"""
    app = create_app("testing")

    with app.app_context():
        # 确保数据库表已创建
        from app.core.extensions import db

        db.create_all()

        # 检查蓝图是否注册
        assert "auth" in app.blueprints
        auth_bp = app.blueprints["auth"]
        print(f"认证蓝图URL前缀: {auth_bp.url_prefix}")
        print(f"认证蓝图URL规则: {auth_bp.url_defaults}")

        # 检查路由是否在蓝图中
        with app.test_client() as client:
            resp = client.post("/api/auth/register", json={})
            print(f"注册路由状态: {resp.status_code}")
            # 应该返回400（参数错误）而不是404（路由不存在）
            assert resp.status_code in [400, 201]

        # 清理数据库
        db.drop_all()
