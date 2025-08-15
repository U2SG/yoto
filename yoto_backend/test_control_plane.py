#!/usr/bin/env python3
"""
控制平面测试脚本

测试控制平面的各项功能
"""

import requests
import json
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 控制平面基础URL
BASE_URL = "http://localhost:5000/control"


def test_system_status():
    """测试系统状态API"""
    logger.info("测试系统状态API...")

    try:
        response = requests.get(f"{BASE_URL}/api/status")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"系统状态: {data['status']}")
            logger.info(f"组件数量: {len(data.get('components', {}))}")
            return True
        else:
            logger.error(f"系统状态API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试系统状态失败: {e}")
        return False


def test_detailed_status():
    """测试详细状态API"""
    logger.info("测试详细状态API...")

    try:
        response = requests.get(f"{BASE_URL}/api/status/detailed")
        if response.status_code == 200:
            data = response.json()
            logger.info("详细状态获取成功")
            logger.info(f"系统统计: {len(data.get('system_stats', {}))} 项")
            logger.info(f"优化建议: {len(data.get('optimization_suggestions', []))} 项")
            return True
        else:
            logger.error(f"详细状态API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试详细状态失败: {e}")
        return False


def test_performance_stats():
    """测试性能统计API"""
    logger.info("测试性能统计API...")

    try:
        response = requests.get(f"{BASE_URL}/api/stats/performance")
        if response.status_code == 200:
            data = response.json()
            logger.info("性能统计获取成功")
            logger.info(f"系统统计: {len(data.get('system_stats', {}))} 项")
            logger.info(f"缓存统计: {len(data.get('cache_stats', {}))} 项")
            return True
        else:
            logger.error(f"性能统计API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试性能统计失败: {e}")
        return False


def test_cache_stats():
    """测试缓存统计API"""
    logger.info("测试缓存统计API...")

    try:
        response = requests.get(f"{BASE_URL}/api/stats/cache")
        if response.status_code == 200:
            data = response.json()
            logger.info("缓存统计获取成功")
            logger.info(f"缓存状态: {data.get('status', 'unknown')}")
            return True
        else:
            logger.error(f"缓存统计API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试缓存统计失败: {e}")
        return False


def test_monitor_stats():
    """测试监控统计API"""
    logger.info("测试监控统计API...")

    try:
        response = requests.get(f"{BASE_URL}/api/stats/monitor")
        if response.status_code == 200:
            data = response.json()
            logger.info("监控统计获取成功")
            logger.info(f"监控状态: {data.get('status', 'unknown')}")
            return True
        else:
            logger.error(f"监控统计API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试监控统计失败: {e}")
        return False


def test_recent_events():
    """测试最近事件API"""
    logger.info("测试最近事件API...")

    try:
        response = requests.get(f"{BASE_URL}/api/events/recent")
        if response.status_code == 200:
            data = response.json()
            logger.info("最近事件获取成功")
            logger.info(f"事件数量: {len(data.get('events', []))}")
            return True
        else:
            logger.error(f"最近事件API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试最近事件失败: {e}")
        return False


def test_maintenance_operations():
    """测试维护操作API"""
    logger.info("测试维护操作API...")

    # 测试预热操作
    try:
        response = requests.post(f"{BASE_URL}/api/maintenance/warmup")
        if response.status_code == 200:
            data = response.json()
            logger.info("预热操作执行成功")
            logger.info(f"预热结果: {data.get('success', False)}")
            return True
        else:
            logger.error(f"预热操作失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试维护操作失败: {e}")
        return False


def test_circuit_breaker_config():
    """测试熔断器配置API"""
    logger.info("测试熔断器配置API...")

    try:
        # 获取配置
        response = requests.get(f"{BASE_URL}/api/config/circuit_breaker/test_breaker")
        if response.status_code == 200:
            data = response.json()
            logger.info("熔断器配置获取成功")
            logger.info(f"熔断器状态: {data.get('state', 'unknown')}")
            return True
        else:
            logger.error(f"熔断器配置API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试熔断器配置失败: {e}")
        return False


def test_rate_limiter_config():
    """测试限流器配置API"""
    logger.info("测试限流器配置API...")

    try:
        # 获取配置
        response = requests.get(f"{BASE_URL}/api/config/rate_limiter/test_limiter")
        if response.status_code == 200:
            data = response.json()
            logger.info("限流器配置获取成功")
            logger.info(f"限流器状态: {data.get('enabled', False)}")
            return True
        else:
            logger.error(f"限流器配置API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试限流器配置失败: {e}")
        return False


def test_cache_config():
    """测试缓存配置API"""
    logger.info("测试缓存配置API...")

    try:
        response = requests.get(f"{BASE_URL}/api/config/cache")
        if response.status_code == 200:
            data = response.json()
            logger.info("缓存配置获取成功")
            logger.info(f"缓存配置项: {len(data)} 项")
            return True
        else:
            logger.error(f"缓存配置API失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"测试缓存配置失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("开始控制平面功能测试...")

    tests = [
        ("系统状态", test_system_status),
        ("详细状态", test_detailed_status),
        ("性能统计", test_performance_stats),
        ("缓存统计", test_cache_stats),
        ("监控统计", test_monitor_stats),
        ("最近事件", test_recent_events),
        ("维护操作", test_maintenance_operations),
        ("熔断器配置", test_circuit_breaker_config),
        ("限流器配置", test_rate_limiter_config),
        ("缓存配置", test_cache_config),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"测试: {test_name}")
        logger.info(f"{'='*50}")

        try:
            success = test_func()
            results.append((test_name, success))
            logger.info(f"测试结果: {'通过' if success else '失败'}")
        except Exception as e:
            logger.error(f"测试异常: {e}")
            results.append((test_name, False))

    # 输出测试总结
    logger.info(f"\n{'='*50}")
    logger.info("测试总结")
    logger.info(f"{'='*50}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "通过" if success else "失败"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\n总计: {passed}/{total} 个测试通过")

    if passed == total:
        logger.info("所有测试通过！控制平面功能正常。")
    else:
        logger.warning(f"{total - passed} 个测试失败，请检查控制平面配置。")


if __name__ == "__main__":
    run_all_tests()
