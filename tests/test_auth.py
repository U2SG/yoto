"""
auth 相关 API 测试文件。
后续在此文件中编写 auth 蓝图的单元测试。
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_register_success(client):
    resp = client.post(
        "/api/register", json={"username": "alice", "password": "123456"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "注册成功"
    assert "user" in data
    assert "id" in data["user"]
    assert data["user"]["username"] == "alice"


def test_register_duplicate_username(client):
    client.post("/api/register", json={"username": "bob", "password": "123456"})
    resp = client.post("/api/register", json={"username": "bob", "password": "abcdef"})
    assert resp.status_code == 409
    data = resp.get_json()
    assert "用户名已存在" in data["error"]


def test_register_missing_fields(client):
    resp = client.post("/api/register", json={"username": "charlie"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "必填" in data["error"]
    resp2 = client.post("/api/register", json={"password": "123456"})
    assert resp2.status_code == 400


def test_login_success(client):
    client.post("/api/register", json={"username": "david", "password": "123456"})
    resp = client.post("/api/login", json={"username": "david", "password": "123456"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "登录成功"
    assert "user_id" in data
    assert "access_token" in data
    # access_token 应为非空字符串
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 10


def test_login_wrong_password(client):
    client.post("/api/register", json={"username": "eva", "password": "123456"})
    resp = client.post("/api/login", json={"username": "eva", "password": "wrong"})
    assert resp.status_code == 401
    data = resp.get_json()
    assert "用户名或密码错误" in data["error"]


def test_login_wrong_username(client):
    resp = client.post(
        "/api/login", json={"username": "notexist", "password": "123456"}
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert "用户名或密码错误" in data["error"]


def test_login_missing_fields(client):
    resp = client.post("/api/login", json={"username": "david"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "必填" in data["error"]
    resp2 = client.post("/api/login", json={"password": "123456"})
    assert resp2.status_code == 400


def test_me_success(client):
    # 注册并登录获取token
    client.post("/api/register", json={"username": "frank", "password": "123456"})
    resp = client.post("/api/login", json={"username": "frank", "password": "123456"})
    token = resp.get_json()["access_token"]
    # 用token访问 /me
    resp2 = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["username"] == "frank"
    assert "id" in data


def test_me_no_token(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_me_invalid_token(client):
    resp = client.get("/api/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 422 or resp.status_code == 401
