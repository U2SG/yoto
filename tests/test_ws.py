import pytest
import socketio
import threading
import time
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from flask_jwt_extended import create_access_token

# 使用pytest标记集成测试
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def flask_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="module")
def ws_server(flask_app):
    from app.ws import socketio as wsio

    # 在后台线程启动SocketIO服务
    def run():
        wsio.run(flask_app, port=6001, debug=False, use_reloader=False)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(1)  # 等待服务启动
    yield
    # 无需手动关闭，线程daemon


@pytest.fixture
def user_token(flask_app):
    with flask_app.app_context():
        user = User.query.filter_by(username="wsuser").first()
        if not user:
            user = User(username="wsuser", password_hash="dummy")
            db.session.add(user)
            db.session.commit()
        # 确保identity是字符串类型
        token = create_access_token(identity=str(user.id))
        return token, user.id


@pytest.fixture
def sio_client(user_token, ws_server):
    token, _ = user_token
    client = socketio.Client()
    client.connect(
        "http://localhost:6001",
        transports=["websocket"],
        headers={"Authorization": f"Bearer {token}"},
    )
    yield client
    client.disconnect()


def test_ws_connect_and_auth(user_token, ws_server):
    token, _ = user_token
    client = socketio.Client()
    msgs = {}

    @client.on("connected")
    def on_connected(data):
        msgs["connected"] = data

    client.connect(
        "http://localhost:6001",
        transports=["websocket"],
        headers={"Authorization": f"Bearer {token}"},
    )
    time.sleep(0.5)
    assert "connected" in msgs
    assert "user_id" in msgs["connected"]
    assert msgs["connected"]["message"] == "连接成功"
    client.disconnect()


def test_ws_join_channel_and_send_message(flask_app, user_token, ws_server):
    token, user_id = user_token
    client = socketio.Client()
    join_result = {}
    msg_result = {}

    @client.on("joined_channel")
    def on_joined(data):
        join_result["joined"] = data

    @client.on("new_message")
    def on_msg(data):
        msg_result["msg"] = data

    client.connect(
        "http://localhost:6001",
        transports=["websocket"],
        headers={"Authorization": f"Bearer {token}"},
    )
    # 创建频道
    from app.blueprints.channels.models import Channel
    from app.blueprints.servers.models import Server, ServerMember

    with flask_app.app_context():
        server = Server(name="ws星球", owner_id=user_id)
        db.session.add(server)
        db.session.commit()
        member = ServerMember(server_id=server.id, user_id=user_id)
        db.session.add(member)
        db.session.commit()
        channel = Channel(name="ws频道", server_id=server.id)
        db.session.add(channel)
        db.session.commit()
        channel_id = channel.id
    # 加入频道
    client.emit("join_channel", {"channel_id": channel_id})
    time.sleep(0.5)
    assert "joined" in join_result
    assert join_result["joined"]["channel_id"] == channel_id
    # 发送消息
    client.emit("send_message", {"channel_id": channel_id, "message": "ws测试消息"})
    time.sleep(0.5)
    assert "msg" in msg_result
    assert msg_result["msg"]["message"] == "ws测试消息"
    assert msg_result["msg"]["channel_id"] == channel_id
    assert str(msg_result["msg"]["user_id"]) == str(user_id)  # 修复：类型统一
    client.disconnect()
