"""
简单修复测试
验证蓝图注册问题是否已解决
"""


def test_app_creation():
    """测试应用创建"""
    from app import create_app

    app = create_app("testing")

    # 检查蓝图注册
    blueprints = list(app.blueprints.keys())
    print(f"注册的蓝图: {blueprints}")

    # 检查路由
    routes = list(app.url_map.iter_rules())
    print(f"路由数量: {len(routes)}")

    # 检查auth路由
    auth_routes = [rule.rule for rule in routes if "auth" in rule.rule]
    print(f"Auth路由: {auth_routes}")

    assert "auth" in blueprints
    assert len(auth_routes) > 0


def test_auth_login_route():
    """测试auth登录路由"""
    from app import create_app

    app = create_app("testing")

    with app.test_client() as client:
        resp = client.post("/api/auth/login")
        print(f"POST /api/auth/login: {resp.status_code}")
        # 应该返回400（参数错误），而不是404（路由不存在）
        assert resp.status_code in [400, 401]  # 400是参数错误，401是认证失败


def test_auth_register_route():
    """测试auth注册路由"""
    from app import create_app

    app = create_app("testing")

    with app.test_client() as client:
        resp = client.post("/api/auth/register")
        print(f"POST /api/auth/register: {resp.status_code}")
        # 应该返回400（参数错误），而不是404（路由不存在）
        assert resp.status_code in [400, 409]  # 400是参数错误，409是用户名已存在
