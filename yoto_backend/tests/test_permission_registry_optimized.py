"""
权限注册模块优化测试

测试优化后的批量操作功能，验证N+1查询问题的解决效果
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.core.permission_registry import (
    batch_register_permissions,
    batch_register_roles,
    assign_permissions_to_role_v2,
    assign_roles_to_user_v2,
    get_permission_registry_stats,
    list_registered_permissions,
    list_registered_roles,
)
from app.blueprints.roles.models import Permission, Role, RolePermission, UserRole
from app.core.extensions import db
from config import TestingConfig


class TestPermissionRegistryOptimized:
    """测试优化后的权限注册模块批量操作"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app(TestingConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return app.test_client()

    @pytest.fixture
    def sample_permissions_data(self):
        """示例权限数据"""
        return [
            {
                "name": "test.permission.1",
                "group": "test",
                "description": "Test permission 1",
            },
            {
                "name": "test.permission.2",
                "group": "test",
                "description": "Test permission 2",
            },
            {
                "name": "test.permission.3",
                "group": "admin",
                "description": "Test permission 3",
            },
            {
                "name": "test.permission.4",
                "group": "admin",
                "description": "Test permission 4",
            },
            {
                "name": "test.permission.5",
                "group": "user",
                "description": "Test permission 5",
            },
        ]

    @pytest.fixture
    def sample_roles_data(self):
        """示例角色数据"""
        return [
            {"name": "test_role_1", "server_id": 1, "is_active": True},
            {"name": "test_role_2", "server_id": 1, "is_active": True},
            {"name": "test_role_3", "server_id": 2, "is_active": True},
            {
                "name": "admin_role",
                "server_id": 1,
                "is_active": True,
            },  # 使用有效的server_id
            {
                "name": "user_role",
                "server_id": 1,
                "is_active": True,
            },  # 使用有效的server_id
        ]

    def test_batch_register_permissions_optimized(self, app, sample_permissions_data):
        """测试优化后的批量注册权限功能"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in sample_permissions_data])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试批量注册
            start_time = time.time()
            results = batch_register_permissions(sample_permissions_data)
            end_time = time.time()

            # 验证结果
            assert len(results) == len(sample_permissions_data)
            assert all(result["status"] in ["created", "updated"] for result in results)

            # 验证数据库中的权限
            permissions = (
                db.session.query(Permission)
                .filter(
                    Permission.name.in_([p["name"] for p in sample_permissions_data])
                )
                .all()
            )
            assert len(permissions) == len(sample_permissions_data)

            # 验证性能（应该比优化前快很多）
            execution_time = end_time - start_time
            print(f"批量注册权限执行时间: {execution_time:.4f}秒")
            assert execution_time < 1.0  # 应该在1秒内完成

            # 测试重复注册（应该更新而不是创建）
            update_results = batch_register_permissions(sample_permissions_data)
            assert len(update_results) == len(sample_permissions_data)
            assert all(result["status"] == "updated" for result in update_results)

    def test_batch_register_roles_optimized(self, app, sample_roles_data):
        """测试优化后的批量注册角色功能"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Role).filter(
                Role.name.in_([r["name"] for r in sample_roles_data])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试批量注册
            start_time = time.time()
            results = batch_register_roles(sample_roles_data)
            end_time = time.time()

            # 验证结果
            assert len(results) == len(sample_roles_data)
            assert all(result["status"] in ["created", "updated"] for result in results)

            # 验证数据库中的角色
            roles = (
                db.session.query(Role)
                .filter(Role.name.in_([r["name"] for r in sample_roles_data]))
                .all()
            )
            assert len(roles) == len(sample_roles_data)

            # 验证性能
            execution_time = end_time - start_time
            print(f"批量注册角色执行时间: {execution_time:.4f}秒")
            assert execution_time < 1.0

            # 测试重复注册
            update_results = batch_register_roles(sample_roles_data)
            assert len(update_results) == len(sample_roles_data)
            assert all(result["status"] == "updated" for result in update_results)

    def test_assign_permissions_to_role_optimized(self, app):
        """测试优化后的批量分配权限功能"""
        with app.app_context():
            # 创建测试角色
            role = Role(name="test_role_assign", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建测试权限
            permissions = []
            for i in range(5):
                perm = Permission(name=f"test_perm_{i}", group="test")
                db.session.add(perm)
                permissions.append(perm)
            db.session.commit()

            permission_ids = [p.id for p in permissions]

            # 清理已存在的分配关系
            db.session.query(RolePermission).filter(
                RolePermission.role_id == role.id,
                RolePermission.permission_id.in_(permission_ids),
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试批量分配
            start_time = time.time()
            results = assign_permissions_to_role_v2(
                role.id, permission_ids, "server", 1
            )
            end_time = time.time()

            # 验证结果
            assert len(results) == len(permission_ids)
            assert all(result["status"] == "assigned" for result in results)

            # 验证数据库中的分配关系
            role_permissions = (
                db.session.query(RolePermission)
                .filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id.in_(permission_ids),
                )
                .all()
            )
            assert len(role_permissions) == len(permission_ids)

            # 验证性能
            execution_time = end_time - start_time
            print(f"批量分配权限执行时间: {execution_time:.4f}秒")
            assert execution_time < 1.0

            # 测试重复分配（应该跳过已存在的）
            repeat_results = assign_permissions_to_role_v2(
                role.id, permission_ids, "server", 1
            )
            assert len(repeat_results) == 0  # 应该没有新的分配

            # 清理测试数据
            db.session.query(RolePermission).filter(
                RolePermission.role_id == role.id
            ).delete()
            db.session.query(Role).filter(Role.id == role.id).delete()
            for perm in permissions:
                db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.commit()

    def test_assign_roles_to_user_optimized(self, app):
        """测试优化后的批量分配角色功能"""
        with app.app_context():
            # 创建测试用户（模拟）
            user_id = 999

            # 创建测试角色
            roles = []
            for i in range(3):
                role = Role(name=f"test_role_user_{i}", server_id=1)
                db.session.add(role)
                roles.append(role)
            db.session.commit()

            role_ids = [r.id for r in roles]

            # 清理已存在的分配关系
            db.session.query(UserRole).filter(
                UserRole.user_id == user_id, UserRole.role_id.in_(role_ids)
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试批量分配
            start_time = time.time()
            results = assign_roles_to_user_v2(user_id, role_ids, server_id=1)
            end_time = time.time()

            # 验证结果
            assert len(results) == len(role_ids)
            assert all(result["status"] == "assigned" for result in results)

            # 验证数据库中的分配关系
            user_roles = (
                db.session.query(UserRole)
                .filter(UserRole.user_id == user_id, UserRole.role_id.in_(role_ids))
                .all()
            )
            assert len(user_roles) == len(role_ids)

            # 验证性能
            execution_time = end_time - start_time
            print(f"批量分配角色执行时间: {execution_time:.4f}秒")
            assert execution_time < 1.0

            # 测试重复分配
            repeat_results = assign_roles_to_user_v2(user_id, role_ids, server_id=1)
            assert len(repeat_results) == 0  # 应该没有新的分配

            # 清理测试数据
            db.session.query(UserRole).filter(UserRole.user_id == user_id).delete()
            for role in roles:
                db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_empty_data_handling(self, app):
        """测试空数据处理"""
        with app.app_context():
            # 测试空权限数据
            empty_permissions = []
            results = batch_register_permissions(empty_permissions)
            assert results == []

            # 测试空角色数据
            empty_roles = []
            results = batch_register_roles(empty_roles)
            assert results == []

            # 测试空权限ID列表
            results = assign_permissions_to_role_v2(1, [])
            assert results == []

            # 测试空角色ID列表
            results = assign_roles_to_user_v2(1, [], server_id=1)
            assert results == []

    def test_error_handling(self, app):
        """测试错误处理"""
        with app.app_context():
            # 测试无效权限数据
            invalid_permissions = [
                {"name": ""},  # 空名称
                {"description": "test"},  # 缺少名称
                None,  # None值
            ]
            results = batch_register_permissions(invalid_permissions)
            assert len(results) == 0

            # 测试无效角色数据
            invalid_roles = [
                {"name": ""},  # 空名称
                {"server_id": 1},  # 缺少名称
                None,  # None值
            ]
            results = batch_register_roles(invalid_roles)
            assert len(results) == 0

    def test_performance_comparison(self, app, sample_permissions_data):
        """测试性能对比（优化前后）"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in sample_permissions_data])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试优化后的批量操作
            start_time = time.time()
            results = batch_register_permissions(sample_permissions_data)
            optimized_time = time.time() - start_time

            print(f"优化后批量注册权限时间: {optimized_time:.4f}秒")
            print(f"处理 {len(sample_permissions_data)} 个权限")
            print(f"平均每个权限: {optimized_time/len(sample_permissions_data):.6f}秒")

            # 验证性能提升（应该比优化前快很多）
            assert optimized_time < 0.5  # 应该在0.5秒内完成
            assert len(results) == len(sample_permissions_data)

    def test_registry_stats(self, app):
        """测试注册统计功能"""
        with app.app_context():
            stats = get_permission_registry_stats()
            assert isinstance(stats, dict)
            assert "permissions" in stats
            assert "roles" in stats
            assert "registry" in stats

    def test_list_functions(self, app):
        """测试列表查询功能"""
        with app.app_context():
            # 测试权限列表
            permissions = list_registered_permissions()
            assert isinstance(permissions, list)

            # 测试角色列表
            roles = list_registered_roles()
            assert isinstance(roles, list)

    def test_database_consistency(self, app, sample_permissions_data):
        """测试数据库一致性"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in sample_permissions_data])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 执行批量注册
            results = batch_register_permissions(sample_permissions_data)

            # 验证数据库一致性
            for perm_data in sample_permissions_data:
                name = perm_data["name"]
                db_perm = (
                    db.session.query(Permission).filter(Permission.name == name).first()
                )
                assert db_perm is not None
                assert db_perm.group == perm_data["group"]
                assert db_perm.description == perm_data["description"]

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in sample_permissions_data])
            ).delete(synchronize_session=False)
            db.session.commit()


class TestPermissionRegistryPerformance:
    """性能测试类"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app(TestingConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    def test_large_batch_performance(self, app):
        """测试大批量操作性能"""
        with app.app_context():
            # 生成大批量测试数据
            large_permissions = []
            for i in range(100):
                large_permissions.append(
                    {
                        "name": f"large_test_perm_{i}",
                        "group": f"group_{i % 5}",
                        "description": f"Large test permission {i}",
                        "is_deprecated": False,
                    }
                )

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in large_permissions])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试大批量注册性能
            start_time = time.time()
            results = batch_register_permissions(large_permissions)
            end_time = time.time()

            execution_time = end_time - start_time
            print(f"大批量注册性能测试:")
            print(f"  数据量: {len(large_permissions)} 个权限")
            print(f"  执行时间: {execution_time:.4f}秒")
            print(f"  平均每个权限: {execution_time/len(large_permissions):.6f}秒")
            print(f"  每秒处理: {len(large_permissions)/execution_time:.2f} 个权限")

            # 验证性能要求
            assert execution_time < 2.0  # 100个权限应该在2秒内完成
            assert len(results) == len(large_permissions)

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in large_permissions])
            ).delete(synchronize_session=False)
            db.session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
