#!/usr/bin/env python3
"""
韧性配置管理API使用示例

演示如何使用API端点动态配置韧性策略
"""

import requests
import json
import time

# API基础URL
BASE_URL = "http://localhost:5000/api/resilience"

# 模拟JWT token（实际使用时需要先登录获取）
JWT_TOKEN = "Bearer your_jwt_token_here"


def get_headers():
    """获取请求头"""
    return {"Content-Type": "application/json", "Authorization": JWT_TOKEN}


def set_rate_limit_config():
    """设置限流器配置示例"""
    print("=== 设置限流器配置 ===")

    config = {
        "name": "api_rate_limit",
        "enabled": True,
        "limit_type": "token_bucket",
        "max_requests": 100,
        "time_window": 60.0,
        "multi_dimensional": True,
        "user_id_limit": 50,
        "server_id_limit": 200,
        "ip_limit": 100,
        "combined_limit": 300,
    }

    response = requests.post(
        f"{BASE_URL}/rate-limit", headers=get_headers(), data=json.dumps(config)
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 限流器配置设置成功: {result['message']}")
        print(f"配置详情: {json.dumps(result['config'], indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 限流器配置设置失败: {response.text}")


def get_rate_limit_config():
    """获取限流器配置示例"""
    print("\n=== 获取限流器配置 ===")

    response = requests.get(
        f"{BASE_URL}/rate-limit?name=api_rate_limit", headers=get_headers()
    )

    if response.status_code == 200:
        config = response.json()
        print(f"✅ 获取限流器配置成功:")
        print(f"名称: {config['name']}")
        print(f"启用状态: {config['enabled']}")
        print(f"限流类型: {config['limit_type']}")
        print(f"最大请求数: {config['max_requests']}")
        print(f"时间窗口: {config['time_window']}秒")
        print(f"多维限流: {config['multi_dimensional']}")
        if config["multi_dimensional"]:
            print(f"用户ID限制: {config['user_id_limit']}")
            print(f"服务器ID限制: {config['server_id_limit']}")
            print(f"IP限制: {config['ip_limit']}")
            print(f"组合限制: {config['combined_limit']}")
    else:
        print(f"❌ 获取限流器配置失败: {response.text}")


def set_circuit_breaker_config():
    """设置熔断器配置示例"""
    print("\n=== 设置熔断器配置 ===")

    config = {
        "name": "api_circuit_breaker",
        "failure_threshold": 5,
        "recovery_timeout": 60.0,
        "expected_exception": "Exception",
        "monitor_interval": 10.0,
        "state": "closed",
    }

    response = requests.post(
        f"{BASE_URL}/circuit-breaker", headers=get_headers(), data=json.dumps(config)
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 熔断器配置设置成功: {result['message']}")
        print(f"配置详情: {json.dumps(result['config'], indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 熔断器配置设置失败: {response.text}")


def get_circuit_breaker_status():
    """获取熔断器状态示例"""
    print("\n=== 获取熔断器状态 ===")

    response = requests.get(
        f"{BASE_URL}/circuit-breaker?name=api_circuit_breaker", headers=get_headers()
    )

    if response.status_code == 200:
        status = response.json()
        print(f"✅ 获取熔断器状态成功:")
        print(f"名称: {status['name']}")
        print(f"状态: {status['state']}")
        print(f"失败计数: {status['failure_count']}")
        print(f"配置: {json.dumps(status['config'], indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 获取熔断器状态失败: {response.text}")


def set_degradation_config():
    """设置降级配置示例"""
    print("\n=== 设置降级配置 ===")

    config = {
        "name": "api_degradation",
        "level": "none",
        "fallback_function": "fallback_handler",
        "timeout": 5.0,
        "enabled": False,
    }

    response = requests.post(
        f"{BASE_URL}/degradation", headers=get_headers(), data=json.dumps(config)
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 降级配置设置成功: {result['message']}")
        print(f"配置详情: {json.dumps(result['config'], indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 降级配置设置失败: {response.text}")


def get_all_configs():
    """获取所有配置示例"""
    print("\n=== 获取所有韧性配置 ===")

    response = requests.get(f"{BASE_URL}/configs", headers=get_headers())

    if response.status_code == 200:
        configs = response.json()
        print(f"✅ 获取所有配置成功:")
        print(f"熔断器数量: {len(configs.get('circuit_breakers', {}))}")
        print(f"限流器数量: {len(configs.get('rate_limits', {}))}")
        print(f"降级配置数量: {len(configs.get('degradations', {}))}")
        print(f"全局开关数量: {len(configs.get('global_switches', {}))}")
        print(f"详细配置: {json.dumps(configs, indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 获取所有配置失败: {response.text}")


def clear_cache():
    """清理缓存示例"""
    print("\n=== 清理配置缓存 ===")

    response = requests.post(f"{BASE_URL}/cache/clear", headers=get_headers())

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 缓存清理成功: {result['message']}")
    else:
        print(f"❌ 缓存清理失败: {response.text}")


def main():
    """主函数"""
    print("🚀 韧性配置管理API使用示例")
    print("=" * 50)

    # 注意：在实际使用前，需要先获取有效的JWT token
    print("⚠️  注意：请确保已获取有效的JWT token并更新JWT_TOKEN变量")
    print("⚠️  可以通过登录API获取token: POST /api/auth/login")
    print()

    try:
        # 设置限流器配置
        set_rate_limit_config()

        # 获取限流器配置
        get_rate_limit_config()

        # 设置熔断器配置
        set_circuit_breaker_config()

        # 获取熔断器状态
        get_circuit_breaker_status()

        # 设置降级配置
        set_degradation_config()

        # 获取所有配置
        get_all_configs()

        # 清理缓存
        clear_cache()

        print("\n✅ 所有API调用示例完成！")

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败：请确保Flask应用正在运行")
        print("启动命令: python app.py")
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")


if __name__ == "__main__":
    main()
