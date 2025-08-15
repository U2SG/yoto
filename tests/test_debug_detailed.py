"""
详细调试测试
逐步诊断导入和路由注册问题
"""


def test_import_auth_blueprint():
    """测试auth蓝图导入"""
    try:
        from app.blueprints.auth import auth_bp

        print("✓ Auth蓝图导入成功")
        print(f"  - 蓝图名称: {auth_bp.name}")
        print(f"  - URL前缀: {auth_bp.url_prefix}")
        print(f"  - 视图函数: {list(auth_bp.view_functions.keys())}")
    except Exception as e:
        print(f"✗ Auth蓝图导入失败: {e}")
        return False
    return True


def test_import_auth_views():
    """测试auth视图导入"""
    try:
        from app.blueprints.auth.views import login, register

        print("✓ Auth视图函数导入成功")
    except Exception as e:
        print(f"✗ Auth视图函数导入失败: {e}")
        return False
    return True


def test_import_pydantic_schemas():
    """测试pydantic schemas导入"""
    try:
        from app.core.pydantic_schemas import UserSchema

        print("✓ UserSchema导入成功")
    except Exception as e:
        print(f"✗ UserSchema导入失败: {e}")
        return False
    return True


def test_app_creation_with_debug():
    """测试应用创建并调试"""
    try:
        from app import create_app

        app = create_app("testing")
        print("✓ 应用创建成功")

        # 检查蓝图
        blueprints = list(app.blueprints.keys())
        print(f"  - 蓝图: {blueprints}")

        # 检查auth蓝图
        auth_bp = app.blueprints.get("auth")
        if auth_bp:
            print(f"  - Auth蓝图视图函数: {list(auth_bp.view_functions.keys())}")
        else:
            print("  - Auth蓝图未找到!")

        # 检查所有路由
        routes = list(app.url_map.iter_rules())
        auth_routes = [rule.rule for rule in routes if "auth" in rule.rule]
        print(f"  - Auth路由: {auth_routes}")

        return True
    except Exception as e:
        print(f"✗ 应用创建失败: {e}")
        return False


def test_step_by_step_import():
    """逐步测试导入"""
    print("\n=== 逐步导入测试 ===")

    # 测试1: 基础模块
    try:
        import flask

        print("✓ Flask导入成功")
    except Exception as e:
        print(f"✗ Flask导入失败: {e}")

    # 测试2: 扩展模块
    try:
        from app.core.extensions import db

        print("✓ 数据库扩展导入成功")
    except Exception as e:
        print(f"✗ 数据库扩展导入失败: {e}")

    # 测试3: 模型模块
    try:
        from app.blueprints.auth.models import User

        print("✓ User模型导入成功")
    except Exception as e:
        print(f"✗ User模型导入失败: {e}")

    # 测试4: JWT模块
    try:
        from flask_jwt_extended import create_access_token

        print("✓ JWT扩展导入成功")
    except Exception as e:
        print(f"✗ JWT扩展导入失败: {e}")

    # 测试5: 安全模块
    try:
        from werkzeug.security import generate_password_hash

        print("✓ Werkzeug安全模块导入成功")
    except Exception as e:
        print(f"✗ Werkzeug安全模块导入失败: {e}")


def test_auth_blueprint_registration():
    """测试auth蓝图注册"""
    print("\n=== Auth蓝图注册测试 ===")

    # 测试蓝图创建
    try:
        from flask import Blueprint

        auth_bp = Blueprint("auth", __name__)
        print("✓ Auth蓝图创建成功")
    except Exception as e:
        print(f"✗ Auth蓝图创建失败: {e}")
        return False

    # 测试视图导入
    try:
        from app.blueprints.auth import views

        print("✓ Auth视图模块导入成功")
    except Exception as e:
        print(f"✗ Auth视图模块导入失败: {e}")
        return False

    # 测试路由注册
    try:
        from app.blueprints.auth import auth_bp

        print(f"✓ Auth蓝图路由数量: {len(auth_bp.view_functions)}")
        print(f"  - 路由: {list(auth_bp.view_functions.keys())}")
    except Exception as e:
        print(f"✗ Auth蓝图路由注册失败: {e}")
        return False

    return True
