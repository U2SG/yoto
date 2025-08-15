#!/usr/bin/env python3
"""
创建超级管理员用户脚本

用于创建超级管理员用户并生成登录token，以便访问控制平面
"""

import sys
import os
import time
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token, JWTManager


def create_admin_user():
    """创建超级管理员用户"""
    app = create_app("development")

    with app.app_context():
        # 创建数据库表
        db.create_all()

        # 检查是否已存在admin用户
        admin_user = User.query.filter_by(username="admin").first()

        if admin_user:
            print(f"✅ 超级管理员用户已存在: {admin_user.username}")
            print(f"   用户ID: {admin_user.id}")
            print(f"   超级管理员: {admin_user.is_super_admin}")
        else:
            # 创建新的超级管理员用户
            admin_user = User(
                username="admin",
                password_hash=generate_password_hash("admin123"),
                is_super_admin=True,
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f"✅ 创建超级管理员用户成功: {admin_user.username}")
            print(f"   用户ID: {admin_user.id}")
            print(f"   密码: admin123")

        # 生成JWT token
        jwt = JWTManager(app)

        # 创建访问token
        token = create_access_token(
            identity=str(admin_user.id),
            additional_claims={
                "username": admin_user.username,
                "is_super_admin": admin_user.is_super_admin,
                "user_id": admin_user.id,
            },
            expires_delta=timedelta(hours=24),
        )

        print(f"\n🔑 登录信息:")
        print(f"   用户名: {admin_user.username}")
        print(f"   密码: admin123")
        print(f"   JWT Token: {token}")

        print(f"\n🌐 访问控制平面:")
        print(f"   1. 启动应用: python run.py")
        print(f"   2. 访问控制平面: http://localhost:5000/control")
        print(f"   3. 使用以下信息登录:")
        print(f"      - 用户名: {admin_user.username}")
        print(f"      - 密码: admin123")
        print(f"      - 或者使用JWT Token: {token}")

        print(f"\n📊 控制平面功能:")
        print(f"   - 实时事件流监控")
        print(f"   - 权限系统状态")
        print(f"   - 性能指标")
        print(f"   - 缓存统计")
        print(f"   - 韧性系统状态")

        return admin_user, token


def main():
    """主函数"""
    print("🚀 创建超级管理员用户...")
    print("=" * 50)

    try:
        admin_user, token = create_admin_user()
        print("\n✅ 设置完成！")
        print("=" * 50)

    except Exception as e:
        print(f"❌ 创建管理员用户失败: {e}")
        return False

    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 超级管理员用户创建成功！")
    else:
        print("\n💥 创建失败，请检查错误信息")
