"""
QPS（每秒查询数）性能对比测试
比较原有权限系统和高级优化模块在高并发下的吞吐能力
"""

import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

try:
    from app.core.permissions import (
        _get_permissions_from_cache,
        _set_permissions_to_cache,
    )
    from app.core.advanced_optimization import (
        advanced_get_permissions_from_cache,
        advanced_set_permissions_to_cache,
    )

    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"模块导入失败: {e}")
    MODULES_AVAILABLE = False

import pytest


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
def test_qps_comparison():
    from app import create_app

    app = create_app("testing")

    with app.app_context():
        test_key = "qps_test_key"
        test_permissions = {"read", "write", "delete"}
        _set_permissions_to_cache(test_key, test_permissions)
        advanced_set_permissions_to_cache(test_key, test_permissions)

        duration = 5  # 测试时长（秒）
        thread_count = 20  # 并发线程数

        def run_qps_test(get_func, label):
            total_queries = 0
            stop_flag = threading.Event()

            def worker():
                nonlocal total_queries
                while not stop_flag.is_set():
                    perms = get_func(test_key)
                    total_queries += 1

            threads = [threading.Thread(target=worker) for _ in range(thread_count)]
            start_time = time.time()
            for t in threads:
                t.start()
            time.sleep(duration)
            stop_flag.set()
            for t in threads:
                t.join()
            end_time = time.time()
            qps = total_queries / (end_time - start_time)
            print(
                f"{label} QPS: {qps:.2f} ({total_queries} queries in {end_time - start_time:.2f}s, {thread_count} threads)"
            )
            return qps

        print("\n=== QPS 性能对比测试 ===")
        qps_old = run_qps_test(_get_permissions_from_cache, "原有方式")
        qps_new = run_qps_test(advanced_get_permissions_from_cache, "新优化方式")

        print(f"\nQPS提升倍数: {qps_new/qps_old:.2f}x")
        assert qps_new > 0.8 * qps_old  # 新方式QPS不应低于原有方式的80%


if __name__ == "__main__":
    test_qps_comparison()
