#!/usr/bin/env python3
"""
单用户查询瓶颈分析工具
分析缓存访问路径、权限聚合算法、数据库查询优化
"""
import sys
import os
import time
import statistics
import cProfile
import pstats
import io
from typing import Dict, List, Set, Tuple

# 添加父目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import (
    _optimized_single_user_query_v2,
    _precompute_user_permissions,
    _get_permissions_from_cache,
    _set_permissions_to_cache,
    _make_perm_cache_key,
    _permission_cache,
    _precomputed_permissions,
)


class BottleneckAnalyzer:
    """瓶颈分析器"""

    def __init__(self):
        self.app = create_app("mysql_testing")
        self.setup_database()

        # 分析结果
        self.analysis_results = {
            "cache_access": {},
            "permission_aggregation": {},
            "database_query": {},
            "overall_performance": {},
        }

    def setup_database(self):
        """设置数据库"""
        with self.app.app_context():
            try:
                db.create_all()
                self.create_test_data()
            except Exception as e:
                print(f"数据库设置失败: {e}")

    def create_test_data(self):
        """创建测试数据"""
        print("创建瓶颈分析测试数据...")

        import time

        unique_id = int(time.time() * 1000) % 100000

        # 创建用户
        user = User(username=f"bottleneck_user_{unique_id}", password_hash="test_hash")
        db.session.add(user)
        db.session.commit()
        self.test_user_id = user.id

        # 创建角色
        roles = []
        for i in range(10):  # 10个角色
            role = Role(name=f"bottleneck_role_{unique_id}_{i}", server_id=1)
            roles.append(role)
        db.session.add_all(roles)
        db.session.commit()

        # 创建权限
        permissions = []
        for i in range(100):  # 100个权限
            perm = Permission(
                name=f"bottleneck_perm_{unique_id}_{i}",
                group="bottleneck",
                description=f"Bottleneck permission {i}",
            )
            permissions.append(perm)
        db.session.add_all(permissions)
        db.session.commit()

        # 分配用户角色
        user_roles = []
        for role in roles:
            user_role = UserRole(user_id=user.id, role_id=role.id)
            user_roles.append(user_role)
        db.session.add_all(user_roles)
        db.session.commit()

        # 分配角色权限
        role_permissions = []
        for i, role in enumerate(roles):
            for j in range(10):  # 每个角色10个权限
                perm = permissions[i * 10 + j]
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                role_permissions.append(rp)
        db.session.add_all(role_permissions)
        db.session.commit()

        print(
            f"创建了测试用户 {user.id}, {len(roles)} 个角色, {len(permissions)} 个权限"
        )

    def analyze_cache_access_path(self):
        """分析缓存访问路径瓶颈"""
        print("\n=== 缓存访问路径分析 ===")

        cache_metrics = {
            "l1_cache_hit_time": [],
            "l1_cache_miss_time": [],
            "l2_cache_hit_time": [],
            "l2_cache_miss_time": [],
            "cache_key_generation_time": [],
            "serialization_time": [],
            "deserialization_time": [],
        }

        with self.app.app_context():
            # 1. 分析缓存键生成性能
            print("1. 分析缓存键生成性能...")
            for i in range(1000):
                start_time = time.time()
                cache_key = _make_perm_cache_key(self.test_user_id, "server", 1)
                key_gen_time = time.time() - start_time
                cache_metrics["cache_key_generation_time"].append(key_gen_time)

            # 2. 分析L1缓存访问性能
            print("2. 分析L1缓存访问性能...")
            # 先填充缓存
            permissions = {"test_perm_1", "test_perm_2", "test_perm_3"}
            cache_key = _make_perm_cache_key(self.test_user_id, "server", 1)
            _permission_cache.set(cache_key, permissions)

            # 测试L1缓存命中
            for i in range(1000):
                start_time = time.time()
                result = _permission_cache.get(cache_key)
                hit_time = time.time() - start_time
                cache_metrics["l1_cache_hit_time"].append(hit_time)

            # 测试L1缓存未命中
            for i in range(1000):
                start_time = time.time()
                result = _permission_cache.get(f"miss_key_{i}")
                miss_time = time.time() - start_time
                cache_metrics["l1_cache_miss_time"].append(miss_time)

            # 3. 分析序列化/反序列化性能
            print("3. 分析序列化/反序列化性能...")
            from app.core.permissions import (
                _serialize_permissions,
                _deserialize_permissions,
            )

            for i in range(1000):
                test_permissions = {f"perm_{j}" for j in range(50)}

                # 序列化测试
                start_time = time.time()
                serialized = _serialize_permissions(test_permissions)
                serialize_time = time.time() - start_time
                cache_metrics["serialization_time"].append(serialize_time)

                # 反序列化测试
                start_time = time.time()
                deserialized = _deserialize_permissions(serialized)
                deserialize_time = time.time() - start_time
                cache_metrics["deserialization_time"].append(deserialize_time)

        # 计算统计结果
        cache_results = {}
        for metric, times in cache_metrics.items():
            if times:
                cache_results[metric] = {
                    "avg_time": statistics.mean(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                }

        self.analysis_results["cache_access"] = cache_results
        return cache_results

    def analyze_permission_aggregation(self):
        """分析权限聚合算法瓶颈"""
        print("\n=== 权限聚合算法分析 ===")

        aggregation_metrics = {
            "role_collection_time": [],
            "permission_collection_time": [],
            "inheritance_resolution_time": [],
            "scope_filtering_time": [],
            "set_operations_time": [],
        }

        with self.app.app_context():
            # 1. 分析角色收集性能
            print("1. 分析角色收集性能...")
            for i in range(100):
                start_time = time.time()
                roles = (
                    db.session.query(UserRole.role_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .filter(
                        UserRole.user_id == self.test_user_id,
                        Role.is_active == True,
                        Role.deleted_at.is_(None),
                    )
                    .all()
                )
                role_time = time.time() - start_time
                aggregation_metrics["role_collection_time"].append(role_time)

            # 2. 分析权限收集性能
            print("2. 分析权限收集性能...")
            role_ids = [
                r[0]
                for r in db.session.query(UserRole.role_id)
                .filter(UserRole.user_id == self.test_user_id)
                .all()
            ]

            for i in range(100):
                start_time = time.time()
                permissions = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .filter(
                        RolePermission.role_id.in_(role_ids),
                        Permission.is_deprecated == False,
                    )
                    .distinct()
                    .all()
                )
                perm_time = time.time() - start_time
                aggregation_metrics["permission_collection_time"].append(perm_time)

            # 3. 分析作用域过滤性能
            print("3. 分析作用域过滤性能...")
            for i in range(100):
                start_time = time.time()
                scoped_permissions = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .filter(
                        RolePermission.role_id.in_(role_ids),
                        RolePermission.scope_type == "server",
                        RolePermission.scope_id == 1,
                        Permission.is_deprecated == False,
                    )
                    .distinct()
                    .all()
                )
                scope_time = time.time() - start_time
                aggregation_metrics["scope_filtering_time"].append(scope_time)

            # 4. 分析集合操作性能
            print("4. 分析集合操作性能...")
            for i in range(1000):
                set1 = {f"perm_{j}" for j in range(50)}
                set2 = {f"perm_{j+25}" for j in range(50)}

                start_time = time.time()
                union_result = set1.union(set2)
                intersection_result = set1.intersection(set2)
                difference_result = set1.difference(set2)
                set_time = time.time() - start_time
                aggregation_metrics["set_operations_time"].append(set_time)

        # 计算统计结果
        aggregation_results = {}
        for metric, times in aggregation_metrics.items():
            if times:
                aggregation_results[metric] = {
                    "avg_time": statistics.mean(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                }

        self.analysis_results["permission_aggregation"] = aggregation_results
        return aggregation_results

    def analyze_database_query(self):
        """分析数据库查询瓶颈"""
        print("\n=== 数据库查询分析 ===")

        query_metrics = {
            "join_query_time": [],
            "subquery_time": [],
            "index_usage_time": [],
            "distinct_operation_time": [],
            "filter_operation_time": [],
        }

        with self.app.app_context():
            # 1. 分析JOIN查询性能
            print("1. 分析JOIN查询性能...")
            for i in range(50):
                start_time = time.time()
                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .join(UserRole, RolePermission.role_id == UserRole.role_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .filter(
                        UserRole.user_id == self.test_user_id,
                        Role.is_active == True,
                        Role.deleted_at.is_(None),
                        Permission.is_deprecated == False,
                    )
                    .distinct()
                )
                result = query.all()
                join_time = time.time() - start_time
                query_metrics["join_query_time"].append(join_time)

            # 2. 分析子查询性能
            print("2. 分析子查询性能...")
            for i in range(50):
                start_time = time.time()
                valid_roles_subquery = (
                    db.session.query(UserRole.role_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .filter(
                        UserRole.user_id == self.test_user_id,
                        Role.is_active == True,
                        Role.deleted_at.is_(None),
                    )
                    .subquery()
                )

                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .filter(
                        RolePermission.role_id.in_(valid_roles_subquery),
                        Permission.is_deprecated == False,
                    )
                    .distinct()
                )
                result = query.all()
                subquery_time = time.time() - start_time
                query_metrics["subquery_time"].append(subquery_time)

            # 3. 分析DISTINCT操作性能
            print("3. 分析DISTINCT操作性能...")
            for i in range(100):
                start_time = time.time()
                query = db.session.query(Permission.name).distinct()
                result = query.all()
                distinct_time = time.time() - start_time
                query_metrics["distinct_operation_time"].append(distinct_time)

            # 4. 分析过滤操作性能
            print("4. 分析过滤操作性能...")
            for i in range(100):
                start_time = time.time()
                query = db.session.query(Permission.name).filter(
                    Permission.is_deprecated == False
                )
                result = query.all()
                filter_time = time.time() - start_time
                query_metrics["filter_operation_time"].append(filter_time)

        # 计算统计结果
        query_results = {}
        for metric, times in query_metrics.items():
            if times:
                query_results[metric] = {
                    "avg_time": statistics.mean(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                }

        self.analysis_results["database_query"] = query_results
        return query_results

    def profile_optimized_query(self):
        """使用cProfile分析优化查询的性能"""
        print("\n=== 性能分析器分析 ===")

        with self.app.app_context():
            # 创建性能分析器
            profiler = cProfile.Profile()
            profiler.enable()

            # 执行优化查询
            for i in range(100):
                permissions = _optimized_single_user_query_v2(
                    self.test_user_id, "server", 1
                )

            profiler.disable()

            # 获取分析结果
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)  # 显示前20个最耗时的函数

            profile_output = s.getvalue()
            print("性能分析结果:")
            print(profile_output)

            return profile_output

    def identify_bottlenecks(self):
        """识别主要瓶颈"""
        print("\n=== 瓶颈识别 ===")

        bottlenecks = []

        # 分析缓存瓶颈
        cache_results = self.analysis_results["cache_access"]
        if cache_results:
            # 检查缓存键生成是否过慢
            if "cache_key_generation_time" in cache_results:
                avg_key_time = cache_results["cache_key_generation_time"]["avg_time"]
                if avg_key_time > 0.001:  # 超过1ms
                    bottlenecks.append(f"缓存键生成过慢: {avg_key_time:.6f}s")

            # 检查序列化是否过慢
            if "serialization_time" in cache_results:
                avg_serialize_time = cache_results["serialization_time"]["avg_time"]
                if avg_serialize_time > 0.001:  # 超过1ms
                    bottlenecks.append(f"序列化过慢: {avg_serialize_time:.6f}s")

        # 分析权限聚合瓶颈
        aggregation_results = self.analysis_results["permission_aggregation"]
        if aggregation_results:
            # 检查角色收集是否过慢
            if "role_collection_time" in aggregation_results:
                avg_role_time = aggregation_results["role_collection_time"]["avg_time"]
                if avg_role_time > 0.01:  # 超过10ms
                    bottlenecks.append(f"角色收集过慢: {avg_role_time:.6f}s")

            # 检查权限收集是否过慢
            if "permission_collection_time" in aggregation_results:
                avg_perm_time = aggregation_results["permission_collection_time"][
                    "avg_time"
                ]
                if avg_perm_time > 0.01:  # 超过10ms
                    bottlenecks.append(f"权限收集过慢: {avg_perm_time:.6f}s")

        # 分析数据库查询瓶颈
        query_results = self.analysis_results["database_query"]
        if query_results:
            # 检查JOIN查询是否过慢
            if "join_query_time" in query_results:
                avg_join_time = query_results["join_query_time"]["avg_time"]
                if avg_join_time > 0.05:  # 超过50ms
                    bottlenecks.append(f"JOIN查询过慢: {avg_join_time:.6f}s")

            # 检查子查询是否过慢
            if "subquery_time" in query_results:
                avg_subquery_time = query_results["subquery_time"]["avg_time"]
                if avg_subquery_time > 0.05:  # 超过50ms
                    bottlenecks.append(f"子查询过慢: {avg_subquery_time:.6f}s")

        return bottlenecks

    def generate_optimization_recommendations(self):
        """生成优化建议"""
        print("\n=== 优化建议 ===")

        recommendations = []
        bottlenecks = self.identify_bottlenecks()

        for bottleneck in bottlenecks:
            if "缓存键生成过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "cache_access",
                        "issue": "缓存键生成过慢",
                        "solution": "使用更简单的键生成算法，避免MD5哈希",
                        "priority": "high",
                    }
                )

            elif "序列化过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "cache_access",
                        "issue": "序列化过慢",
                        "solution": "使用更快的序列化格式，如pickle或msgpack",
                        "priority": "medium",
                    }
                )

            elif "角色收集过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "permission_aggregation",
                        "issue": "角色收集过慢",
                        "solution": "添加角色缓存，减少数据库查询",
                        "priority": "high",
                    }
                )

            elif "权限收集过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "permission_aggregation",
                        "issue": "权限收集过慢",
                        "solution": "使用批量查询，减少JOIN操作",
                        "priority": "high",
                    }
                )

            elif "JOIN查询过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "database_query",
                        "issue": "JOIN查询过慢",
                        "solution": "优化索引，使用覆盖索引，减少JOIN表数量",
                        "priority": "high",
                    }
                )

            elif "子查询过慢" in bottleneck:
                recommendations.append(
                    {
                        "area": "database_query",
                        "issue": "子查询过慢",
                        "solution": "使用EXISTS替代IN子查询，优化索引",
                        "priority": "medium",
                    }
                )

        return recommendations

    def run_full_analysis(self):
        """运行完整分析"""
        print("开始单用户查询瓶颈分析...")
        print("=" * 60)

        # 1. 缓存访问路径分析
        self.analyze_cache_access_path()

        # 2. 权限聚合算法分析
        self.analyze_permission_aggregation()

        # 3. 数据库查询分析
        self.analyze_database_query()

        # 4. 性能分析器分析
        profile_output = self.profile_optimized_query()

        # 5. 识别瓶颈
        bottlenecks = self.identify_bottlenecks()

        # 6. 生成优化建议
        recommendations = self.generate_optimization_recommendations()

        # 7. 生成分析报告
        self.generate_analysis_report(bottlenecks, recommendations, profile_output)

    def generate_analysis_report(self, bottlenecks, recommendations, profile_output):
        """生成分析报告"""
        print("\n" + "=" * 60)
        print("单用户查询瓶颈分析报告")
        print("=" * 60)

        print(f"\n1. 发现的瓶颈 ({len(bottlenecks)} 个):")
        for i, bottleneck in enumerate(bottlenecks, 1):
            print(f"   {i}. {bottleneck}")

        print(f"\n2. 优化建议 ({len(recommendations)} 个):")
        for i, rec in enumerate(recommendations, 1):
            priority_icon = (
                "🔴"
                if rec["priority"] == "high"
                else "🟡" if rec["priority"] == "medium" else "🟢"
            )
            print(f"   {i}. {priority_icon} {rec['area']}: {rec['issue']}")
            print(f"      解决方案: {rec['solution']}")

        print(f"\n3. 性能指标:")
        for area, results in self.analysis_results.items():
            if results:
                print(f"   {area}:")
                for metric, stats in results.items():
                    if isinstance(stats, dict) and "avg_time" in stats:
                        print(f"     - {metric}: {stats['avg_time']:.6f}s (avg)")

        print(f"\n4. 关键发现:")
        if bottlenecks:
            print("   ⚠️  发现性能瓶颈，需要优化")
        else:
            print("   ✅ 未发现明显瓶颈")

        # 保存详细报告
        self.save_detailed_report(bottlenecks, recommendations, profile_output)

    def save_detailed_report(self, bottlenecks, recommendations, profile_output):
        """保存详细报告"""
        report_content = f"""
# 单用户查询瓶颈分析详细报告

## 发现的瓶颈
{chr(10).join(f"- {bottleneck}" for bottleneck in bottlenecks)}

## 优化建议
{chr(10).join(f"- **{rec['area']}**: {rec['issue']} -> {rec['solution']}" for rec in recommendations)}

## 性能分析器输出
```
{profile_output}
```

## 详细性能指标
"""

        for area, results in self.analysis_results.items():
            if results:
                report_content += f"\n### {area}\n"
                for metric, stats in results.items():
                    if isinstance(stats, dict) and "avg_time" in stats:
                        report_content += f"- {metric}: {stats['avg_time']:.6f}s (avg), {stats['min_time']:.6f}s (min), {stats['max_time']:.6f}s (max)\n"

        with open("bottleneck_analysis_report.md", "w", encoding="utf-8") as f:
            f.write(report_content)

        print("详细报告已保存到: bottleneck_analysis_report.md")

    def cleanup(self):
        """清理测试数据"""
        with self.app.app_context():
            try:
                from sqlalchemy import text

                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.execute(text("DROP TABLE IF EXISTS role_permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS user_roles"))
                db.session.execute(text("DROP TABLE IF EXISTS permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS roles"))
                db.session.execute(text("DROP TABLE IF EXISTS users"))
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
                print("测试数据清理完成")
            except Exception as e:
                print(f"清理失败: {e}")


def main():
    """主函数"""
    analyzer = BottleneckAnalyzer()

    try:
        analyzer.run_full_analysis()
    finally:
        analyzer.cleanup()


if __name__ == "__main__":
    main()
