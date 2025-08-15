"""
权限注册模块重构测试

测试重构后的权限注册模块，包括：
- 本地注册表缓存的重构
- 数据一致性保证
- 启动时初始化功能
- 多进程环境下的安全性
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.core.permission_registry import (
    register_permission,
    register_permission_legacy,
    register_role,
    batch_register_permissions,
    batch_register_roles,
    assign_permissions_to_role_v2,
    assign_roles_to_user_v2,
    get_permission_registry_stats,
    list_registered_permissions,
    list_registered_roles,
    initialize_permission_registry,
    get_local_registry_info,
    invalidate_registry_cache,
)
from app.blueprints.roles.models import Permission, Role, RolePermission, UserRole
from app.core.extensions import db
from config import TestingConfig


class TestPermissionRegistryRefactored:
    """测试重构后的权限注册模块"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app(TestingConfig)
        with app.app_context():
            db.create_all()
            yield app
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
                "is_deprecated": False,
            },
            {
                "name": "test.permission.2",
                "group": "test",
                "description": "Test permission 2",
                "is_deprecated": False,
            },
            {
                "name": "test.permission.3",
                "group": "admin",
                "description": "Test permission 3",
                "is_deprecated": False,
            },
            {
                "name": "test.permission.4",
                "group": "admin",
                "description": "Test permission 4",
                "is_deprecated": True,
            },
            {
                "name": "test.permission.5",
                "group": "user",
                "description": "Test permission 5",
                "is_deprecated": False,
            },
        ]

    @pytest.fixture
    def sample_roles_data(self):
        """示例角色数据"""
        return [
            {"name": "test_role_1", "server_id": 1, "is_active": True},
            {"name": "test_role_2", "server_id": 1, "is_active": True},
            {"name": "test_role_3", "server_id": 2, "is_active": True},
            {"name": "admin_role", "server_id": 1, "is_active": True},
            {"name": "user_role", "server_id": 1, "is_active": True},
        ]

    def test_register_permission_consistency(self, app):
        """测试权限注册的数据一致性"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name == "test.consistency.permission"
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试v1版本注册
            result_v1 = register_permission(
                "test.consistency.permission", "test", "Test permission"
            )
            assert result_v1["status"] == "registered"

            # 验证数据库中的数据
            db_permission = (
                db.session.query(Permission)
                .filter(Permission.name == "test.consistency.permission")
                .first()
            )
            assert db_permission is not None
            assert db_permission.name == "test.consistency.permission"
            assert db_permission.group == "test"

            # 测试新版本注册（更新现有权限）
            result_v2 = register_permission(
                "test.consistency.permission", "updated", "Updated description", False
            )
            assert result_v2["name"] == "test.consistency.permission"

            # 验证数据库中的数据已更新
            db_permission = (
                db.session.query(Permission)
                .filter(Permission.name == "test.consistency.permission")
                .first()
            )
            assert db_permission.group == "updated"
            assert db_permission.description == "Updated description"

    def test_register_role_consistency(self, app):
        """测试角色注册的数据一致性"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Role).filter(Role.name == "test_consistency_role").delete(
                synchronize_session=False
            )
            db.session.commit()

            # 测试角色注册
            result = register_role("test_consistency_role", 1, True)
            assert result["name"] == "test_consistency_role"
            assert result["server_id"] == 1
            assert result["is_active"] == True

            # 验证数据库中的数据
            db_role = (
                db.session.query(Role)
                .filter(Role.name == "test_consistency_role", Role.server_id == 1)
                .first()
            )
            assert db_role is not None
            assert db_role.name == "test_consistency_role"
            assert db_role.server_id == 1
            assert db_role.is_active == True

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

            # 验证性能
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

    def test_get_permission_registry_stats_from_database(self, app):
        """测试从数据库获取权限注册统计"""
        with app.app_context():
            # 创建一些测试数据
            permissions = []
            for i in range(3):
                perm = Permission(name=f"test_stats_perm_{i}", group="test")
                db.session.add(perm)
                permissions.append(perm)

            roles = []
            for i in range(2):
                role = Role(name=f"test_stats_role_{i}", server_id=1)
                db.session.add(role)
                roles.append(role)

            db.session.commit()

            # 获取统计信息
            stats = get_permission_registry_stats()

            # 验证统计信息
            assert isinstance(stats, dict)
            assert "permissions" in stats
            assert "roles" in stats
            assert "local_registry" in stats

            # 验证数据库统计
            assert stats["permissions"]["total"] >= 3
            assert stats["roles"]["total"] >= 2

            # 验证本地注册表统计
            assert "permissions" in stats["local_registry"]
            assert "roles" in stats["local_registry"]
            assert "note" in stats["local_registry"]
            assert "本地注册表仅用于启动时声明" in stats["local_registry"]["note"]

            # 清理测试数据
            for perm in permissions:
                db.session.query(Permission).filter(Permission.id == perm.id).delete()
            for role in roles:
                db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_list_registered_permissions_from_database(self, app):
        """测试从数据库列出注册的权限"""
        with app.app_context():
            # 创建测试权限
            test_permissions = []
            for i in range(3):
                perm = Permission(name=f"test_list_perm_{i}", group="test")
                db.session.add(perm)
                test_permissions.append(perm)
            db.session.commit()

            # 列出权限
            permissions = list_registered_permissions()

            # 验证结果
            assert isinstance(permissions, list)
            assert len(permissions) >= 3

            # 验证权限数据
            for perm in permissions:
                assert "id" in perm
                assert "name" in perm
                assert "group" in perm
                assert "description" in perm
                assert "is_deprecated" in perm
                assert "created_at" in perm
                assert "updated_at" in perm

            # 清理测试数据
            for perm in test_permissions:
                db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.commit()

    def test_list_registered_roles_from_database(self, app):
        """测试从数据库列出注册的角色"""
        with app.app_context():
            # 创建测试角色
            test_roles = []
            for i in range(3):
                role = Role(name=f"test_list_role_{i}", server_id=1)
                db.session.add(role)
                test_roles.append(role)
            db.session.commit()

            # 列出角色
            roles = list_registered_roles()

            # 验证结果
            assert isinstance(roles, list)
            assert len(roles) >= 3

            # 验证角色数据
            for role in roles:
                assert "id" in role
                assert "name" in role
                assert "server_id" in role
                assert "role_type" in role
                assert "priority" in role
                assert "is_active" in role
                assert "created_at" in role
                assert "updated_at" in role

            # 清理测试数据
            for role in test_roles:
                db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_initialize_permission_registry(self, app):
        """测试权限注册表初始化"""
        with app.app_context():
            # 创建一些测试数据
            permissions = []
            for i in range(3):
                perm = Permission(name=f"test_init_perm_{i}", group="test")
                db.session.add(perm)
                permissions.append(perm)

            roles = []
            for i in range(2):
                role = Role(name=f"test_init_role_{i}", server_id=1)
                db.session.add(role)
                roles.append(role)

            db.session.commit()

            # 初始化权限注册表
            initialize_permission_registry()

            # 获取本地注册表信息
            local_info = get_local_registry_info()

            # 验证本地注册表
            assert local_info["permissions"]["count"] >= 3
            assert local_info["roles"]["count"] >= 2
            assert "本地注册表仅用于启动时声明" in local_info["note"]

            # 验证权限名称
            for i in range(3):
                assert f"test_init_perm_{i}" in local_info["permissions"]["names"]

            # 验证角色名称
            for i in range(2):
                assert f"test_init_role_{i}_1" in local_info["roles"]["names"]

            # 清理测试数据
            for perm in permissions:
                db.session.query(Permission).filter(Permission.id == perm.id).delete()
            for role in roles:
                db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_invalidate_registry_cache(self, app):
        """测试本地注册缓存失效"""
        with app.app_context():
            # 初始化一些数据
            perm = Permission(name="test_invalidate_perm", group="test")
            role = Role(name="test_invalidate_role", server_id=1)
            db.session.add(perm)
            db.session.add(role)
            db.session.commit()

            # 初始化权限注册表
            initialize_permission_registry()

            # 获取初始本地注册表信息
            initial_info = get_local_registry_info()
            initial_perm_count = initial_info["permissions"]["count"]
            initial_role_count = initial_info["roles"]["count"]

            # 测试失效特定权限缓存
            invalidate_registry_cache(permission_id=perm.id)

            # 测试失效特定角色缓存
            invalidate_registry_cache(role_id=role.id)

            # 测试清空所有缓存
            invalidate_registry_cache()

            # 获取清空后的本地注册表信息
            cleared_info = get_local_registry_info()
            assert cleared_info["permissions"]["count"] == 0
            assert cleared_info["roles"]["count"] == 0

            # 清理测试数据
            db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_data_consistency_with_database(self, app):
        """测试与数据库的数据一致性"""
        with app.app_context():
            # 创建测试数据
            perm = Permission(name="test_consistency_perm", group="test")
            role = Role(name="test_consistency_role", server_id=1)
            db.session.add(perm)
            db.session.add(role)
            db.session.commit()

            # 直接从数据库修改数据
            perm.group = "updated_group"
            role.is_active = False
            db.session.commit()

            # 通过注册函数获取数据
            stats = get_permission_registry_stats()
            permissions = list_registered_permissions()
            roles = list_registered_roles()

            # 验证数据一致性
            db_perm = (
                db.session.query(Permission)
                .filter(Permission.name == "test_consistency_perm")
                .first()
            )
            db_role = (
                db.session.query(Role)
                .filter(Role.name == "test_consistency_role")
                .first()
            )

            # 验证权限数据一致
            assert db_perm.group == "updated_group"
            for p in permissions:
                if p["name"] == "test_consistency_perm":
                    assert p["group"] == "updated_group"
                    break

            # 验证角色数据一致
            assert db_role.is_active == False
            for r in roles:
                if r["name"] == "test_consistency_role":
                    assert r["is_active"] == False
                    break

            # 清理测试数据
            db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

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

            # 测试空数据
            results = batch_register_permissions([])
            assert results == []

            results = batch_register_roles([])
            assert results == []

            results = assign_permissions_to_role_v2(1, [])
            assert results == []

            results = assign_roles_to_user_v2(1, [], server_id=1)
            assert results == []

    def test_performance_under_load(self, app):
        """测试负载下的性能"""
        with app.app_context():
            # 创建大量测试数据
            permissions_data = []
            roles_data = []

            for i in range(50):
                permissions_data.append(
                    {
                        "name": f"load_test_perm_{i}",
                        "group": f"group_{i % 5}",
                        "description": f"Load test permission {i}",
                        "is_deprecated": False,
                    }
                )

                roles_data.append(
                    {
                        "name": f"load_test_role_{i}",
                        "server_id": i % 3 + 1,
                        "is_active": True,
                    }
                )

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in permissions_data])
            ).delete(synchronize_session=False)
            db.session.query(Role).filter(
                Role.name.in_([r["name"] for r in roles_data])
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试批量注册性能
            start_time = time.time()
            perm_results = batch_register_permissions(permissions_data)
            perm_time = time.time() - start_time

            start_time = time.time()
            role_results = batch_register_roles(roles_data)
            role_time = time.time() - start_time

            # 验证性能
            print(f"批量注册50个权限耗时: {perm_time:.4f}秒")
            print(f"批量注册50个角色耗时: {role_time:.4f}秒")

            assert perm_time < 2.0  # 应该在2秒内完成
            assert role_time < 2.0  # 应该在2秒内完成
            assert len(perm_results) == 50
            assert len(role_results) == 50

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name.in_([p["name"] for p in permissions_data])
            ).delete(synchronize_session=False)
            db.session.query(Role).filter(
                Role.name.in_([r["name"] for r in roles_data])
            ).delete(synchronize_session=False)
            db.session.commit()

    def test_backward_compatibility(self, app):
        """测试向后兼容性"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name == "test.backward.compat"
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试旧版本接口（应该发出警告但正常工作）
            with pytest.warns(DeprecationWarning):
                result_legacy = register_permission_legacy(
                    "test.backward.compat", "test", "Test permission"
                )

            # 验证旧版本接口返回格式
            assert result_legacy["status"] == "registered"
            assert result_legacy["name"] == "test.backward.compat"
            assert result_legacy["group"] == "test"
            assert result_legacy["description"] == "Test permission"

            # 验证数据库中确实创建了权限
            db_permission = (
                db.session.query(Permission)
                .filter(Permission.name == "test.backward.compat")
                .first()
            )
            assert db_permission is not None
            assert db_permission.name == "test.backward.compat"
            assert db_permission.group == "test"

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name == "test.backward.compat"
            ).delete(synchronize_session=False)
            db.session.commit()

    def test_function_consolidation(self, app):
        """测试函数合并后的功能"""
        with app.app_context():
            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name == "test.consolidation"
            ).delete(synchronize_session=False)
            db.session.commit()

            # 测试新版本接口（完整功能）
            result_new = register_permission(
                "test.consolidation", "test", "Test description", False
            )

            # 验证新版本接口返回格式
            assert "id" in result_new
            assert result_new["name"] == "test.consolidation"
            assert result_new["group"] == "test"
            assert result_new["description"] == "Test description"
            assert result_new["is_deprecated"] == False
            assert "created_at" in result_new
            assert "updated_at" in result_new

            # 验证数据库中确实创建了权限
            db_permission = (
                db.session.query(Permission)
                .filter(Permission.name == "test.consolidation")
                .first()
            )
            assert db_permission is not None
            assert db_permission.name == "test.consolidation"
            assert db_permission.group == "test"
            assert db_permission.description == "Test description"
            assert db_permission.is_deprecated == False

            # 清理测试数据
            db.session.query(Permission).filter(
                Permission.name == "test.consolidation"
            ).delete(synchronize_session=False)
            db.session.commit()


class TestPermissionRegistryArchitecture:
    """测试权限注册模块的架构设计"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app(TestingConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()

    def test_local_registry_positioning(self, app):
        """测试本地注册表的定位"""
        with app.app_context():
            # 验证本地注册表仅用于启动时声明
            local_info = get_local_registry_info()
            assert "本地注册表仅用于启动时声明" in local_info["note"]

            # 验证统计数据来自数据库而非本地缓存
            stats = get_permission_registry_stats()
            assert "local_registry" in stats
            assert "note" in stats["local_registry"]
            assert "不作为主要数据源" in stats["local_registry"]["note"]

    def test_database_as_primary_source(self, app):
        """测试数据库作为主要数据源"""
        with app.app_context():
            # 创建测试数据
            perm = Permission(name="test_primary_source", group="test")
            role = Role(name="test_primary_source", server_id=1)
            db.session.add(perm)
            db.session.add(role)
            db.session.commit()

            # 验证数据来自数据库
            permissions = list_registered_permissions()
            roles = list_registered_roles()

            # 查找测试数据
            found_perm = None
            found_role = None

            for p in permissions:
                if p["name"] == "test_primary_source":
                    found_perm = p
                    break

            for r in roles:
                if r["name"] == "test_primary_source":
                    found_role = r
                    break

            assert found_perm is not None
            assert found_role is not None
            assert found_perm["group"] == "test"
            assert found_role["server_id"] == 1

            # 清理测试数据
            db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.query(Role).filter(Role.id == role.id).delete()
            db.session.commit()

    def test_multiprocess_safety(self, app):
        """测试多进程安全性"""
        with app.app_context():
            # 验证本地注册表不依赖进程内缓存作为数据源
            # 这通过从数据库获取数据来实现

            # 创建测试数据
            perm = Permission(name="test_multiprocess", group="test")
            db.session.add(perm)
            db.session.commit()

            # 获取数据（应该来自数据库）
            permissions = list_registered_permissions()

            # 验证数据存在
            found = False
            for p in permissions:
                if p["name"] == "test_multiprocess":
                    found = True
                    break

            assert found, "数据应该来自数据库，不依赖进程内缓存"

            # 清理测试数据
            db.session.query(Permission).filter(Permission.id == perm.id).delete()
            db.session.commit()
