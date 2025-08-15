"""
调试测试
逐步诊断问题
"""

import pytest
from app import create_app


def test_app_import():
    """测试应用导入"""
    print("开始测试应用导入...")
    app = create_app("testing")
    print("应用创建成功")

    # 检查蓝图注册
    print(f"注册的蓝图: {list(app.blueprints.keys())}")

    # 检查路由
    print("注册的路由:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")

    # 特别检查auth路由
    auth_routes = [rule for rule in app.url_map.iter_rules() if "auth" in rule.rule]
    print(f"Auth相关路由: {auth_routes}")

    assert "auth" in app.blueprints


def test_auth_blueprint_specifically():
    """专门测试auth蓝图"""
    app = create_app("testing")

    # 检查auth蓝图
    auth_bp = app.blueprints.get("auth")
    if auth_bp:
        print(f"Auth蓝图URL前缀: {auth_bp.url_prefix}")
        print(f"Auth蓝图URL规则: {auth_bp.url_defaults}")
        print(f"Auth蓝图视图函数: {list(auth_bp.view_functions.keys())}")
    else:
        print("Auth蓝图未找到!")

    # 测试路由
    with app.test_client() as client:
        resp = client.get("/api/auth/register")
        print(f"GET /api/auth/register: {resp.status_code}")

        resp = client.post("/api/auth/register")
        print(f"POST /api/auth/register: {resp.status_code}")

        resp = client.post("/api/auth/login")
        print(f"POST /api/auth/login: {resp.status_code}")


def test_import_errors():
    """测试导入错误"""
    try:
        from app.blueprints.auth import auth_bp

        print("Auth蓝图导入成功")
    except Exception as e:
        print(f"Auth蓝图导入失败: {e}")

    try:
        from app.blueprints.auth.views import register, login

        print("Auth视图函数导入成功")
    except Exception as e:
        print(f"Auth视图函数导入失败: {e}")

    try:
        from app.core.pydantic_schemas import UserSchema

        print("UserSchema导入成功")
    except Exception as e:
        print(f"UserSchema导入失败: {e}")
