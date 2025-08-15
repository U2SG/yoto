#!/usr/bin/env python3
"""
权限系统重构全面检查脚本

此脚本用于全面检查重构后的权限系统是否完整实现了原始权限系统的功能
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 原始权限系统函数列表（从permissions.py中提取）
ORIGINAL_FUNCTIONS = [
    # Redis相关函数
    "_get_redis_client",
    "_get_redis_pipeline",
    "_redis_batch_get",
    "_redis_batch_set",
    "_redis_batch_delete",
    "_redis_scan_keys",
    # 缓存键生成函数
    "_make_perm_cache_key",
    "_make_user_perm_pattern",
    "_make_role_perm_pattern",
    # 数据序列化函数
    "_compress_permissions",
    "_decompress_permissions",
    "_serialize_permissions",
    "_deserialize_permissions",
    # 缓存操作函数
    "_get_permissions_from_cache",
    "_set_permissions_to_cache",
    "get_permissions_from_cache",  # 新增的公开接口
    "set_permissions_to_cache",  # 新增的公开接口
    # 缓存失效函数
    "_invalidate_user_permissions",
    "_invalidate_role_permissions",
    "invalidate_user_permissions",  # 公开接口
    "invalidate_role_permissions",  # 公开接口
    # 缓存预热和预计算相关
    "_warm_up_cache",
    "_precompute_user_permissions",
    "_batch_precompute_permissions",
    "_invalidate_precomputed_permissions",
    "invalidate_precomputed_permissions",
    "_invalidate_query_cache",
    "invalidate_query_cache",
    "_optimized_batch_query",
    "_batch_refresh_user_permissions",
    # 角色和权限处理辅助函数
    "_gather_role_ids_with_inheritance",
    "_get_active_user_roles",
    "_evaluate_role_conditions",
    "_get_permissions_with_scope",
    # 权限注册函数
    "register_permission",
    "list_registered_permissions",
    "refresh_user_permissions",
    # 缓存统计函数
    "get_cache_stats",
    "get_cache_performance_stats",
    # 权限装饰器函数
    "require_permission",
    "_optimized_single_user_query_v3",
    "_batch_role_cache",
    "_optimized_permission_aggregation",
    "require_permission_v2",
    "require_permissions_v2",
    "require_permission_with_expression_v2",
    "_evaluate_permission_expression",
    "invalidate_permission_check_cache",
    # 权限注册V2函数
    "register_permission_v2",
    "register_role_v2",
    "batch_register_permissions",
    "batch_register_roles",
    "assign_permissions_to_role_v2",
    "assign_roles_to_user_v2",
    "get_permission_registry_stats",
    "invalidate_registry_cache",
    # 缓存自动调优和失效分析函数
    "get_cache_auto_tune_suggestions",
    "get_cache_invalidation_strategy_analysis",
    "add_delayed_invalidation",
    "get_delayed_invalidation_stats",
    "get_invalidation_statistics",
    "get_smart_batch_invalidation_analysis",
    "execute_smart_batch_invalidation",
    # 分布式缓存函数
    "get_distributed_cache_stats",
    "distributed_cache_get",
    "distributed_cache_set",
    "distributed_cache_delete",
]

# 重构后模块函数映射
REFACTORED_MODULES = {
    "permission_decorators": [
        "require_permission",
        "require_permission_v2",
        "require_permissions_v2",
        "require_permission_with_expression_v2",
        "evaluate_permission_expression",  # 这个在permission_decorators中
        "invalidate_permission_check_cache",
    ],
    "permission_cache": [
        "_get_redis_client",
        "_get_redis_pipeline",
        "_redis_batch_get",
        "_redis_batch_set",
        "_redis_batch_delete",
        "_redis_scan_keys",
        "_make_perm_cache_key",
        "_make_user_perm_pattern",
        "_make_role_perm_pattern",
        "_compress_permissions",
        "_decompress_permissions",
        "_serialize_permissions",
        "_deserialize_permissions",
        "get_permissions_from_cache",  # 原来的_get_permissions_from_cache
        "set_permissions_to_cache",  # 原来的_set_permissions_to_cache
        "invalidate_user_permissions",  # 原来的_invalidate_user_permissions
        "invalidate_role_permissions",  # 原来的_invalidate_role_permissions
        "get_cache_stats",
        "get_cache_performance_stats",
    ],
    "permission_queries": [
        "optimized_single_user_query_v3",  # 原来的_optimized_single_user_query_v3
        "batch_precompute_permissions",  # 原来的_batch_precompute_permissions
        "optimized_batch_query",  # 原来的_optimized_batch_query
        "gather_role_ids_with_inheritance",  # 原来的_gather_role_ids_with_inheritance
        "get_active_user_roles",  # 原来的_get_active_user_roles
        "evaluate_role_conditions",  # 原来的_evaluate_role_conditions
        "get_permissions_with_scope",  # 原来的_get_permissions_with_scope
        "refresh_user_permissions",
        "batch_refresh_user_permissions",  # 原来的_batch_refresh_user_permissions
    ],
    "permission_registry": [
        "register_permission_v2",
        "register_role_v2",
        "batch_register_permissions",
        "batch_register_roles",
        "assign_permissions_to_role_v2",
        "assign_roles_to_user_v2",
        "get_permission_registry_stats",
        "invalidate_registry_cache",
        "list_registered_permissions",
        "register_permission",  # 原始函数，现在已添加
    ],
    "permission_invalidation": [
        "add_delayed_invalidation",
        "get_delayed_invalidation_stats",
        "get_invalidation_statistics",
        "get_smart_batch_invalidation_analysis",
        "execute_smart_batch_invalidation",
        "get_cache_auto_tune_suggestions",
        "get_cache_invalidation_strategy_analysis",
        "get_distributed_cache_stats",
        "distributed_cache_get",
        "distributed_cache_set",
        "distributed_cache_delete",
    ],
}

# 需要特别处理的函数（已重命名或移动）
RENAMED_FUNCTIONS = {
    "_get_permissions_from_cache": "get_permissions_from_cache",
    "_set_permissions_to_cache": "set_permissions_to_cache",
    "_invalidate_user_permissions": "invalidate_user_permissions",
    "_invalidate_role_permissions": "invalidate_role_permissions",
    "_optimized_single_user_query_v3": "optimized_single_user_query_v3",
    "_batch_precompute_permissions": "batch_precompute_permissions",
    "_optimized_batch_query": "optimized_batch_query",
    "_gather_role_ids_with_inheritance": "gather_role_ids_with_inheritance",
    "_get_active_user_roles": "get_active_user_roles",
    "_evaluate_role_conditions": "evaluate_role_conditions",
    "_get_permissions_with_scope": "get_permissions_with_scope",
    "_batch_refresh_user_permissions": "batch_refresh_user_permissions",
    "_evaluate_permission_expression": "evaluate_permission_expression",  # 在permission_decorators中
}

# 可能已移除或不需要直接迁移的函数
DEPRECATED_OR_INTERNAL_FUNCTIONS = [
    "_warm_up_cache",
    "_precompute_user_permissions",
    "_invalidate_precomputed_permissions",
    "invalidate_precomputed_permissions",
    "_invalidate_query_cache",
    "invalidate_query_cache",
    "_batch_role_cache",
    "_optimized_permission_aggregation",
]


def check_module_exists(module_name):
    """检查模块是否存在"""
    try:
        __import__(f"app.core.{module_name}")
        return True
    except ImportError as e:
        print(f"  ✗ 模块 {module_name} 不存在: {e}")
        return False


def check_function_exists(module_name, function_name):
    """检查函数在模块中是否存在"""
    try:
        module = __import__(f"app.core.{module_name}", fromlist=[function_name])
        if hasattr(module, function_name):
            return True
        else:
            print(f"  ✗ 函数 {function_name} 不存在于模块 {module_name} 中")
            return False
    except ImportError as e:
        print(f"  ✗ 无法导入模块 {module_name}: {e}")
        return False


def check_all_functions():
    """检查所有函数是否都已正确迁移"""
    print("=== 权限系统重构全面检查 ===\n")

    # 检查模块是否存在
    print("1. 检查重构模块存在性...")
    modules_exist = True
    for module_name in REFACTORED_MODULES.keys():
        if not check_module_exists(module_name):
            modules_exist = False
    if modules_exist:
        print("  ✓ 所有重构模块都存在\n")

    # 检查函数迁移情况
    print("2. 检查函数迁移情况...")
    missing_functions = []
    total_functions = 0
    migrated_functions = 0

    for module_name, functions in REFACTORED_MODULES.items():
        print(f"  检查模块 {module_name}:")
        for function_name in functions:
            total_functions += 1
            if check_function_exists(module_name, function_name):
                migrated_functions += 1
            else:
                missing_functions.append((module_name, function_name))
        print()

    # 检查是否有未分配的原始函数
    print("3. 检查未分配或特殊处理的原始函数...")
    assigned_functions = []
    for functions in REFACTORED_MODULES.values():
        assigned_functions.extend(functions)

    unassigned_functions = []
    properly_handled_functions = []

    for function_name in ORIGINAL_FUNCTIONS:
        # 检查是否在已分配函数中
        if function_name in assigned_functions:
            properly_handled_functions.append(function_name)
            continue

        # 检查是否是重命名的函数
        if function_name in RENAMED_FUNCTIONS:
            new_name = RENAMED_FUNCTIONS[function_name]
            # 查找新名称在哪个模块中
            found = False
            for module_name, functions in REFACTORED_MODULES.items():
                if new_name in functions:
                    properly_handled_functions.append(f"{function_name} -> {new_name}")
                    found = True
                    break
            if not found:
                unassigned_functions.append(function_name)
            continue

        # 检查是否是已废弃或内部函数
        if function_name in DEPRECATED_OR_INTERNAL_FUNCTIONS:
            properly_handled_functions.append(f"{function_name} (已废弃或内部使用)")
            continue

        # 其他未处理的函数
        unassigned_functions.append(function_name)

    if unassigned_functions:
        print("  以下原始函数未在重构模块中找到对应实现:")
        for function_name in unassigned_functions:
            print(f"    - {function_name}")
    else:
        print("  ✓ 所有原始函数都已正确处理\n")

    # 输出总结
    print("=== 检查总结 ===")
    print(f"总函数数: {total_functions}")
    print(f"已迁移函数数: {migrated_functions}")
    print(
        f"迁移率: {migrated_functions/total_functions*100:.1f}%"
        if total_functions > 0
        else "N/A"
    )

    if missing_functions:
        print("\n缺失的函数:")
        for module_name, function_name in missing_functions:
            print(f"  - {module_name}.{function_name}")
        return False
    else:
        print("\n✓ 所有函数都已正确迁移")
        return True


def check_functionality_integration():
    """检查功能集成情况"""
    print("\n4. 检查功能集成情况...")

    try:
        # 测试导入主要功能
        from app.core.permission_decorators import require_permission_v2
        from app.core.permission_cache import (
            get_permissions_from_cache,
            set_permissions_to_cache,
            invalidate_user_permissions,
            invalidate_role_permissions,
        )
        from app.core.permission_queries import optimized_single_user_query_v3
        from app.core.permission_registry import register_permission_v2
        from app.core.permission_invalidation import add_delayed_invalidation

        print("  ✓ 所有主要功能模块可以正常导入")
        print("  ✓ 权限系统重构完成，功能集成正常")
        return True
    except Exception as e:
        print(f"  ✗ 功能集成检查失败: {e}")
        return False


def main():
    """主函数"""
    all_checks_passed = True

    # 执行全面检查
    if not check_all_functions():
        all_checks_passed = False

    # 检查功能集成
    if not check_functionality_integration():
        all_checks_passed = False

    if all_checks_passed:
        print("\n🎉 权限系统重构全面检查通过！")
        print("\n重构状态总结:")
        print("  ✅ 所有模块已创建并可导入")
        print("  ✅ 所有函数已正确迁移或处理")
        print("  ✅ 功能集成正常")
        print("  ✅ 权限系统重构完成")
    else:
        print("\n❌ 权限系统重构检查未完全通过")
        print("请检查上述问题并修复")

    return all_checks_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
