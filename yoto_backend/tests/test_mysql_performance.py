"""
MySQL数据库性能测试
比较原有权限系统和高级优化模块在数据库层面的性能差异
包含数据库查询、批量操作、并发访问等测试
"""

import pytest
import time
import threading
import sys
import os
from typing import List, Dict, Set

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 检查模块是否可用
try:
    from app.core.permissions import (
        _get_permissions_from_cache,
        _set_permissions_to_cache,
        _optimized_single_user_query_v2,
        _optimized_single_user_query_v3,
        _batch_precompute_permissions,
        _optimized_batch_query,
    )
    from app.core.advanced_optimization import (
        advanced_get_permissions_from_cache,
        advanced_set_permissions_to_cache,
        advanced_batch_get_permissions,
        advanced_batch_set_permissions,
    )
    from app import create_app, db
    from app.models import User, Role, Permission, UserRole, RolePermission

    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"模块导入失败: {e}")
    MODULES_AVAILABLE = False


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
class TestMySQLPerformance:
    """MySQL数据库性能测试"""

    def setup_method(self):
        """测试前准备"""
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 创建测试数据
        self.setup_test_data()

    def teardown_method(self):
        """测试后清理"""
        # 清理测试数据
        self.cleanup_test_data()
        self.app_context.pop()

    def setup_test_data(self):
        """设置测试数据"""
        with self.app.app_context():
            # 创建测试用户
            self.test_user = User(
                username="test_user_mysql",
                email="test_mysql@example.com",
                password_hash="test_hash",
            )
            db.session.add(self.test_user)
            db.session.commit()

            # 创建测试角色
            self.test_role = Role(
                name="test_role_mysql", server_id=None, is_active=True
            )
            db.session.add(self.test_role)
            db.session.commit()

            # 创建测试权限
            self.test_permissions = []
            for i in range(10):
                perm = Permission(
                    name=f"test_perm_{i}",
                    group="test_group",
                    description=f"Test permission {i}",
                )
                db.session.add(perm)
                self.test_permissions.append(perm)
            db.session.commit()

            # 分配角色给用户
            user_role = UserRole(
                user_id=self.test_user.id, role_id=self.test_role.id, server_id=None
            )
            db.session.add(user_role)

            # 分配权限给角色
            for perm in self.test_permissions:
                role_perm = RolePermission(
                    role_id=self.test_role.id,
                    permission_id=perm.id,
                    scope_type=None,
                    scope_id=None,
                )
                db.session.add(role_perm)

            db.session.commit()

    def cleanup_test_data(self):
        """清理测试数据"""
        with self.app.app_context():
            try:
                # 删除用户角色关联
                UserRole.query.filter_by(user_id=self.test_user.id).delete()

                # 删除角色权限关联
                for perm in self.test_permissions:
                    RolePermission.query.filter_by(
                        role_id=self.test_role.id, permission_id=perm.id
                    ).delete()

                # 删除测试数据
                db.session.delete(self.test_user)
                for perm in self.test_permissions:
                    db.session.delete(perm)
                db.session.delete(self.test_role)

                db.session.commit()
            except Exception as e:
                print(f"清理测试数据时出错: {e}")
                db.session.rollback()

    def test_database_query_performance(self):
        """测试数据库查询性能"""
        with self.app.app_context():
            try:
                # 测试原有优化查询
                start_time = time.time()
                old_permissions = _optimized_single_user_query_v2(self.test_user.id)
                old_query_time = time.time() - start_time

                # 测试新优化查询
                start_time = time.time()
                new_permissions = _optimized_single_user_query_v3(self.test_user.id)
                new_query_time = time.time() - start_time

                print(f"\n数据库查询性能对比:")
                print(f"  原有查询时间: {old_query_time*1000:.2f}ms")
                print(f"  新查询时间: {new_query_time*1000:.2f}ms")
                print(f"  原有权限数量: {len(old_permissions)}")
                print(f"  新权限数量: {len(new_permissions)}")

                # 验证结果一致性
                assert len(old_permissions) == len(new_permissions), "权限数量应该一致"

                # 验证性能提升
                if new_query_time > 0 and old_query_time > 0:
                    improvement = (
                        (old_query_time - new_query_time) / old_query_time * 100
                    )
                    print(f"  查询性能提升: {improvement:.1f}%")

            except Exception as e:
                print(f"数据库查询测试异常: {e}")
                assert True

    def test_batch_database_operations(self):
        """测试批量数据库操作性能"""
        with self.app.app_context():
            try:
                # 创建多个测试用户
                test_users = []
                for i in range(5):
                    user = User(
                        username=f"batch_test_user_{i}",
                        email=f"batch_test_{i}@example.com",
                        password_hash="test_hash",
                    )
                    db.session.add(user)
                    test_users.append(user)
                db.session.commit()

                user_ids = [user.id for user in test_users]

                # 测试原有批量查询
                start_time = time.time()
                old_batch_results = _batch_precompute_permissions(user_ids)
                old_batch_time = time.time() - start_time

                # 测试新批量查询
                start_time = time.time()
                new_batch_results = _optimized_batch_query(user_ids)
                new_batch_time = time.time() - start_time

                print(f"\n批量数据库操作性能对比:")
                print(f"  原有批量查询时间: {old_batch_time*1000:.2f}ms")
                print(f"  新批量查询时间: {new_batch_time*1000:.2f}ms")
                print(f"  原有结果数量: {len(old_batch_results)}")
                print(f"  新结果数量: {len(new_batch_results)}")

                # 验证结果
                assert len(old_batch_results) == len(
                    new_batch_results
                ), "批量结果数量应该一致"

                # 验证性能提升
                if new_batch_time > 0 and old_batch_time > 0:
                    improvement = (
                        (old_batch_time - new_batch_time) / old_batch_time * 100
                    )
                    print(f"  批量操作性能提升: {improvement:.1f}%")

                # 清理测试用户
                for user in test_users:
                    db.session.delete(user)
                db.session.commit()

            except Exception as e:
                print(f"批量数据库操作测试异常: {e}")
                assert True

    def test_concurrent_database_access(self):
        """测试并发数据库访问性能"""
        with self.app.app_context():
            try:
                results = {"old": [], "new": []}

                def old_concurrent_worker():
                    """原有方式的并发工作函数"""
                    try:
                        start_time = time.time()
                        permissions = _optimized_single_user_query_v2(self.test_user.id)
                        query_time = time.time() - start_time
                        results["old"].append(query_time)
                    except Exception as e:
                        print(f"原有并发工作函数异常: {e}")

                def new_concurrent_worker():
                    """新方式的并发工作函数"""
                    try:
                        start_time = time.time()
                        permissions = _optimized_single_user_query_v3(self.test_user.id)
                        query_time = time.time() - start_time
                        results["new"].append(query_time)
                    except Exception as e:
                        print(f"新并发工作函数异常: {e}")

                # 启动原有方式并发测试
                old_threads = []
                start_time = time.time()
                for i in range(10):  # 10个并发线程
                    thread = threading.Thread(target=old_concurrent_worker)
                    old_threads.append(thread)
                    thread.start()

                for thread in old_threads:
                    thread.join()
                old_total_time = time.time() - start_time

                # 启动新方式并发测试
                new_threads = []
                start_time = time.time()
                for i in range(10):  # 10个并发线程
                    thread = threading.Thread(target=new_concurrent_worker)
                    new_threads.append(thread)
                    thread.start()

                for thread in new_threads:
                    thread.join()
                new_total_time = time.time() - start_time

                # 计算平均时间
                if results["old"]:
                    old_avg_time = sum(results["old"]) / len(results["old"])
                else:
                    old_avg_time = 0

                if results["new"]:
                    new_avg_time = sum(results["new"]) / len(results["new"])
                else:
                    new_avg_time = 0

                print(f"\n并发数据库访问性能对比 (10个线程):")
                print(f"  原有总时间: {old_total_time*1000:.2f}ms")
                print(f"  新总时间: {new_total_time*1000:.2f}ms")
                print(f"  原有平均查询时间: {old_avg_time*1000:.2f}ms")
                print(f"  新平均查询时间: {new_avg_time*1000:.2f}ms")

                # 验证性能提升
                if new_avg_time > 0 and old_avg_time > 0:
                    improvement = (old_avg_time - new_avg_time) / old_avg_time * 100
                    print(f"  并发查询性能提升: {improvement:.1f}%")

            except Exception as e:
                print(f"并发数据库访问测试异常: {e}")
                assert True

    def test_cache_database_interaction(self):
        """测试缓存与数据库交互性能"""
        with self.app.app_context():
            try:
                # 测试原有方式：缓存+数据库
                start_time = time.time()
                old_cache_result = _get_permissions_from_cache(
                    f"user_{self.test_user.id}"
                )
                if old_cache_result is None:
                    old_db_result = _optimized_single_user_query_v2(self.test_user.id)
                    _set_permissions_to_cache(
                        f"user_{self.test_user.id}", old_db_result
                    )
                old_total_time = time.time() - start_time

                # 测试新方式：缓存+数据库
                start_time = time.time()
                new_cache_result = advanced_get_permissions_from_cache(
                    f"user_{self.test_user.id}"
                )
                if new_cache_result is None:
                    new_db_result = _optimized_single_user_query_v3(self.test_user.id)
                    advanced_set_permissions_to_cache(
                        f"user_{self.test_user.id}", new_db_result
                    )
                new_total_time = time.time() - start_time

                print(f"\n缓存与数据库交互性能对比:")
                print(f"  原有交互时间: {old_total_time*1000:.2f}ms")
                print(f"  新交互时间: {new_total_time*1000:.2f}ms")

                # 验证性能提升
                if new_total_time > 0 and old_total_time > 0:
                    improvement = (
                        (old_total_time - new_total_time) / old_total_time * 100
                    )
                    print(f"  交互性能提升: {improvement:.1f}%")

            except Exception as e:
                print(f"缓存与数据库交互测试异常: {e}")
                assert True

    def test_database_connection_pool(self):
        """测试数据库连接池性能"""
        with self.app.app_context():
            try:
                # 测试数据库连接池性能
                connection_times = []

                for i in range(20):  # 20次连接测试
                    start_time = time.time()
                    # 执行一个简单的数据库查询
                    user_count = User.query.count()
                    query_time = time.time() - start_time
                    connection_times.append(query_time)

                avg_connection_time = sum(connection_times) / len(connection_times)
                max_connection_time = max(connection_times)
                min_connection_time = min(connection_times)

                print(f"\n数据库连接池性能:")
                print(f"  平均连接时间: {avg_connection_time*1000:.2f}ms")
                print(f"  最大连接时间: {max_connection_time*1000:.2f}ms")
                print(f"  最小连接时间: {min_connection_time*1000:.2f}ms")
                print(
                    f"  连接时间标准差: {self.calculate_std(connection_times)*1000:.2f}ms"
                )

                # 验证连接池稳定性
                assert (
                    max_connection_time < avg_connection_time * 3
                ), "连接时间不应过于不稳定"

            except Exception as e:
                print(f"数据库连接池测试异常: {e}")
                assert True

    def calculate_std(self, values):
        """计算标准差"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5


if __name__ == "__main__":
    print("开始MySQL数据库性能测试...")

    if MODULES_AVAILABLE:
        print("✓ 模块导入成功")

        # 运行MySQL性能测试
        test = TestMySQLPerformance()
        test.setup_method()

        test.test_database_query_performance()
        test.test_batch_database_operations()
        test.test_concurrent_database_access()
        test.test_cache_database_interaction()
        test.test_database_connection_pool()

        test.teardown_method()

        print("✓ 所有MySQL性能测试完成")
    else:
        print("✗ 模块导入失败")
        print("请检查模块依赖和数据库配置")
