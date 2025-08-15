"""
简单的认证测试
验证登录功能是否正常工作
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from werkzeug.security import generate_password_hash


def test_register_and_login():
    """测试注册和登录功能"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 测试注册
        client = app.test_client()
        register_data = {"username": "testuser", "password": "password123"}

        resp = client.post("/api/auth/register", json=register_data)
        print(f"注册响应: {resp.status_code} - {resp.get_json()}")
        assert resp.status_code == 201

        # 测试登录
        login_data = {"username": "testuser", "password": "password123"}

        resp = client.post("/api/auth/login", json=login_data)
        print(f"登录响应: {resp.status_code} - {resp.get_json()}")
        assert resp.status_code == 200

        data = resp.get_json()
        assert "access_token" in data
        assert "user_id" in data

        # 测试使用token访问受保护的接口
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/auth/me", headers=headers)
        print(f"获取用户信息响应: {resp.status_code} - {resp.get_json()}")
        assert resp.status_code == 200

        db.drop_all()


def test_login_with_invalid_credentials():
    """测试无效凭据登录"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 创建用户
        user = User(
            username="testuser", password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()

        # 测试错误密码
        client = app.test_client()
        login_data = {"username": "testuser", "password": "wrongpassword"}

        resp = client.post("/api/auth/login", json=login_data)
        assert resp.status_code == 401

        # 测试不存在的用户
        login_data = {"username": "nonexistent", "password": "password123"}

        resp = client.post("/api/auth/login", json=login_data)
        assert resp.status_code == 401

        db.drop_all()
