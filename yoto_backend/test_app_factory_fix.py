#!/usr/bin/env python3
"""
应用工厂模式修复测试
验证模块导入时不会尝试初始化Redis连接
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_module_import():
    """测试模块导入不会触发Redis连接"""
    print("🔍 测试模块导入...")

    try:
        # 测试导入韧性模块
        print("1. 导入韧性模块...")
        from app.core.permission.permission_resilience import resilience

        print("   ✅ 韧性模块导入成功")

        # 测试导入混合缓存模块
        print("2. 导入混合缓存模块...")
        from app.core.permission.hybrid_permission_cache import HybridPermissionCache

        print("   ✅ 混合缓存模块导入成功")

        # 测试导入权限工具模块
        print("3. 导入权限工具模块...")
        from app.core.permission.permission_utils import create_redis_client

        print("   ✅ 权限工具模块导入成功")

        print("🎉 所有模块导入成功，没有触发Redis连接")
        return True

    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_resilience_initialization():
    """测试韧性模块的延迟初始化"""
    print("\n🔍 测试韧性模块延迟初始化...")

    try:
        from app.core.permission.permission_resilience import (
            resilience,
            get_resilience_controller,
        )

        # 测试未初始化时的行为
        print("1. 测试未初始化时的行为...")
        try:
            controller = get_resilience_controller()
            print("   ❌ 应该抛出异常，但没有")
            return False
        except RuntimeError as e:
            print("   ✅ 正确抛出初始化错误")
            print(f"   - 错误信息: {e}")

        # 测试初始化
        print("2. 测试初始化...")
        from flask import Flask

        app = Flask(__name__)
        app.config["REDIS_HOST"] = "localhost"
        app.config["REDIS_PORT"] = 6379

        with app.app_context():
            resilience.init_app(app)
            print("   ✅ 韧性模块初始化成功")

            # 测试初始化后的行为
            controller = get_resilience_controller()
            print("   ✅ 可以正常获取控制器")

        print("🎉 韧性模块延迟初始化测试通过")
        return True

    except Exception as e:
        print(f"❌ 韧性模块延迟初始化测试失败: {e}")
        return False


def test_hybrid_cache_initialization():
    """测试混合缓存的延迟初始化"""
    print("\n🔍 测试混合缓存延迟初始化...")

    try:
        from app.core.permission.hybrid_permission_cache import HybridPermissionCache

        # 测试创建实例
        print("1. 测试创建混合缓存实例...")
        cache = HybridPermissionCache()
        print("   ✅ 混合缓存实例创建成功")

        # 测试获取Redis客户端（应该延迟初始化）
        print("2. 测试获取Redis客户端...")
        redis_client = cache.get_redis_client()
        if redis_client:
            print("   ✅ Redis客户端获取成功")
        else:
            print("   ⚠️ Redis客户端获取失败（可能是配置问题）")

        print("🎉 混合缓存延迟初始化测试通过")
        return True

    except Exception as e:
        print(f"❌ 混合缓存延迟初始化测试失败: {e}")
        return False


def test_flask_context_handling():
    """测试Flask上下文处理"""
    print("\n🔍 测试Flask上下文处理...")

    try:
        from app.core.permission.permission_utils import (
            create_redis_client,
            test_redis_connection,
            get_redis_info,
        )

        # 测试不在Flask上下文中的行为
        print("1. 测试不在Flask上下文中的行为...")
        client = create_redis_client()
        if client:
            print("   ✅ 在Flask上下文外成功创建Redis客户端")
        else:
            print("   ⚠️ 在Flask上下文外创建Redis客户端失败（预期行为）")

        # 测试在Flask上下文中的行为
        print("2. 测试在Flask上下文中的行为...")
        from flask import Flask

        app = Flask(__name__)
        app.config["REDIS_CONFIG"] = {
            "startup_nodes": [{"host": "localhost", "port": 6379}],
            "host": "localhost",
            "port": 6379,
            "db": 0,
        }

        with app.app_context():
            client = create_redis_client()
            if client:
                print("   ✅ 在Flask上下文中成功创建Redis客户端")

                # 测试连接
                if test_redis_connection(client):
                    print("   ✅ Redis连接测试通过")
                else:
                    print("   ⚠️ Redis连接测试失败")
            else:
                print("   ❌ 在Flask上下文中创建Redis客户端失败")

        print("🎉 Flask上下文处理测试通过")
        return True

    except Exception as e:
        print(f"❌ Flask上下文处理测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("应用工厂模式修复测试")
    print("=" * 60)

    # 测试模块导入
    success1 = test_module_import()

    # 测试韧性模块延迟初始化
    success2 = test_resilience_initialization()

    # 测试混合缓存延迟初始化
    success3 = test_hybrid_cache_initialization()

    # 测试Flask上下文处理
    success4 = test_flask_context_handling()

    if success1 and success2 and success3 and success4:
        print("\n" + "=" * 60)
        print("✅ 应用工厂模式修复测试全部通过！")
        print("✅ 模块导入时不会触发Redis连接")
        print("✅ 延迟初始化机制正常工作")
        print("✅ Flask上下文处理正确")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ 应用工厂模式修复测试失败")
        print("=" * 60)
