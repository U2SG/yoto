#!/usr/bin/env python3
"""
MySQL测试环境设置脚本
用于创建MySQL测试数据库和配置
"""
import os
import sys
import pymysql
from sqlalchemy import create_engine, text


def setup_mysql_test_db():
    """设置MySQL测试数据库"""

    # MySQL连接配置
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "gt123456")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "yoto_test")

    try:
        # 连接到MySQL服务器
        print(f"连接到MySQL服务器: {MYSQL_HOST}:{MYSQL_PORT}")
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset="utf8mb4",
        )

        with connection.cursor() as cursor:
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{MYSQL_DATABASE}'")
            db_exists = cursor.fetchone()

            if not db_exists:
                print(f"创建测试数据库: {MYSQL_DATABASE}")
                cursor.execute(
                    f"CREATE DATABASE {MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                print(f"数据库 {MYSQL_DATABASE} 创建成功")
            else:
                print(f"数据库 {MYSQL_DATABASE} 已存在")

            # 设置环境变量
            os.environ["MYSQL_TEST_URI"] = (
                f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
            )

        connection.close()
        print("MySQL测试环境设置完成")
        return True

    except Exception as e:
        print(f"设置MySQL测试环境失败: {e}")
        print("\n请确保:")
        print("1. MySQL服务器正在运行")
        print("2. 连接参数正确")
        print("3. 用户有创建数据库的权限")
        return False


def test_mysql_connection():
    """测试MySQL连接"""
    try:
        from app import create_app
        from app.core.extensions import db

        app = create_app("mysql_testing")
        with app.app_context():
            # 测试数据库连接
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                connection.commit()
            print("MySQL连接测试成功")
            return True
    except Exception as e:
        print(f"MySQL连接测试失败: {e}")
        return False


def run_mysql_tests():
    """运行MySQL测试"""
    try:
        import pytest
        import sys

        # 运行MySQL测试
        test_args = ["tests/test_permissions_mysql.py", "-v", "-s", "--tb=short"]

        print("运行MySQL性能测试...")
        exit_code = pytest.main(test_args)

        if exit_code == 0:
            print("MySQL测试全部通过")
        else:
            print(f"MySQL测试失败，退出码: {exit_code}")

        return exit_code == 0

    except Exception as e:
        print(f"运行MySQL测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=== MySQL测试环境设置 ===")

    # 设置数据库
    if not setup_mysql_test_db():
        sys.exit(1)

    # 测试连接
    if not test_mysql_connection():
        sys.exit(1)

    # 运行测试
    if not run_mysql_tests():
        sys.exit(1)

    print("=== MySQL测试环境设置完成 ===")
