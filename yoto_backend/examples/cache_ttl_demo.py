"""
缓存TTL机制演示

展示配置缓存的TTL功能，演示动态配置更新
"""

import time
import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.permission_resilience import (
    get_resilience_controller,
    set_circuit_breaker_config,
    set_rate_limit_config,
    set_degradation_config,
)


def demo_cache_ttl_mechanism():
    """演示缓存TTL机制"""
    print("=== 缓存TTL机制演示 ===")

    # 获取控制器
    controller = get_resilience_controller()

    # 设置较短的TTL以便演示
    controller.set_cache_ttl(2.0)  # 2秒TTL
    print(f"缓存TTL设置为: {controller.cache_ttl} 秒")

    # 设置初始配置
    print("\n1. 设置初始配置...")
    set_circuit_breaker_config(
        "demo_circuit", failure_threshold=5, recovery_timeout=60.0
    )

    set_rate_limit_config("demo_rate_limit", max_requests=100, time_window=60.0)

    set_degradation_config("demo_degradation", enabled=True, level="medium")

    # 显示缓存信息
    cache_info = controller.get_cache_info()
    print(f"缓存信息: {json.dumps(cache_info, indent=2, default=str)}")

    # 模拟配置更新
    print("\n2. 模拟Redis中的配置更新...")
    print("   (在实际环境中，这会在Redis中直接修改)")

    # 等待一段时间，然后"更新"配置
    print("\n3. 等待缓存过期...")
    for i in range(3):
        print(f"   倒计时: {3-i} 秒")
        time.sleep(1)

    # 模拟配置变更
    print("\n4. 配置已更新，等待下次获取时刷新...")

    # 获取配置（这会触发缓存刷新）
    print("\n5. 获取配置（触发缓存刷新）...")
    configs = controller.get_all_configs()
    print(f"当前配置: {json.dumps(configs, indent=2, default=str)}")

    # 显示更新后的缓存信息
    cache_info_updated = controller.get_cache_info()
    print(
        f"\n更新后的缓存信息: {json.dumps(cache_info_updated, indent=2, default=str)}"
    )

    print("\n=== 演示完成 ===")


def demo_cache_ttl_settings():
    """演示不同的TTL设置"""
    print("\n=== TTL设置演示 ===")

    controller = get_resilience_controller()

    # 测试不同的TTL设置
    ttl_settings = [1.0, 5.0, 30.0, 60.0]

    for ttl in ttl_settings:
        print(f"\n设置TTL为 {ttl} 秒...")
        controller.set_cache_ttl(ttl)

        cache_info = controller.get_cache_info()
        print(f"当前TTL: {cache_info['cache_ttl']} 秒")
        print(f"缓存大小: {cache_info['cache_size']} 项")

    print("\n=== TTL设置演示完成 ===")


def demo_cache_clear():
    """演示缓存清除功能"""
    print("\n=== 缓存清除演示 ===")

    controller = get_resilience_controller()

    # 设置一些配置
    print("1. 设置配置...")
    set_circuit_breaker_config("clear_demo", failure_threshold=10)

    # 显示缓存信息
    cache_info_before = controller.get_cache_info()
    print(f"清除前缓存大小: {cache_info_before['cache_size']}")

    # 清除缓存
    print("\n2. 清除缓存...")
    controller.clear_cache()

    # 显示清除后的缓存信息
    cache_info_after = controller.get_cache_info()
    print(f"清除后缓存大小: {cache_info_after['cache_size']}")

    print("\n=== 缓存清除演示完成 ===")


def main():
    """主函数"""
    print("缓存TTL机制演示")
    print("=" * 50)

    try:
        # 运行各种演示
        demo_cache_ttl_mechanism()
        demo_cache_ttl_settings()
        demo_cache_clear()

        print("\n所有演示完成！")
        print("\n关键特性:")
        print("- 配置缓存有TTL机制，确保动态配置能够及时更新")
        print("- 默认TTL为30秒，可以根据需要调整")
        print("- 支持手动清除缓存")
        print("- 线程安全的缓存操作")

    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
