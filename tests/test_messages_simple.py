"""
简化的消息持久化系统测试
专注于基本功能验证
"""

import pytest
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.servers.models import Server
from app.blueprints.channels.models import Channel, Message
from werkzeug.security import generate_password_hash


def test_message_model():
    """测试Message模型基本功能"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 创建测试数据
        user = User(
            username="testuser", password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()

        server = Server(name="Test Server", owner_id=user.id)
        db.session.add(server)
        db.session.commit()

        channel = Channel(name="Test Channel", server_id=server.id, type="text")
        db.session.add(channel)
        db.session.commit()

        # 创建消息
        message = Message(
            channel_id=channel.id, user_id=user.id, type="text", content="Test message"
        )
        db.session.add(message)
        db.session.commit()

        # 验证消息创建
        assert message.id is not None
        assert message.content == "Test message"
        assert message.type == "text"
        assert message.is_edited == False
        assert message.is_deleted == False

        # 测试编辑消息
        message.content = "Edited message"
        message.is_edited = True
        db.session.commit()

        assert message.content == "Edited message"
        assert message.is_edited == True

        # 测试软删除
        message.is_deleted = True
        db.session.commit()

        assert message.is_deleted == True

        db.drop_all()


def test_auth_login():
    """测试登录功能"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 创建用户
        user = User(
            username="testuser", password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()

        # 测试登录
        client = app.test_client()
        login_data = {"username": "testuser", "password": "password123"}

        resp = client.post("/api/auth/login", json=login_data)
        assert resp.status_code == 200

        data = resp.get_json()
        assert "access_token" in data
        assert "user_id" in data

        db.drop_all()


def test_send_message_api():
    """测试发送消息API"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # 创建测试数据
        user = User(
            username="testuser", password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()

        server = Server(name="Test Server", owner_id=user.id)
        db.session.add(server)
        db.session.commit()

        channel = Channel(name="Test Channel", server_id=server.id, type="text")
        db.session.add(channel)
        db.session.commit()

        # 登录获取token
        client = app.test_client()
        login_data = {"username": "testuser", "password": "password123"}

        resp = client.post("/api/auth/login", json=login_data)
        assert resp.status_code == 200

        data = resp.get_json()
        token = data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 发送消息
        message_data = {"content": "Hello, World!", "type": "text"}

        resp = client.post(
            f"/api/channels/{channel.id}/messages",
            json=message_data,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["content"] == "Hello, World!"
        assert data["type"] == "text"
        assert data["channel_id"] == channel.id

        db.drop_all()
