# 权限系统迁移指南

## 概述

本文档旨在指导开发人员将项目中的权限系统从旧的 [permissions.py](file:///d:/project/Python/yoto/yoto_backend/app/core/permissions.py) 迁移到重构后的模块化权限系统。

## 迁移步骤

### 1. 更新导入语句

#### 旧导入方式:
```python
from app.core.permissions import require_permission
from app.core.permissions import _get_permissions_from_cache, _set_permissions_to_cache
from app.core.permissions import _make_perm_cache_key, _compress_permissions
from app.core.permissions import _get_redis_client, _get_redis_pipeline
from app.core.permissions import _redis_batch_get, _redis_batch_set, _redis_batch_delete
from app.core.permissions import monitored_cache
from app.core.permissions import register_permission
```

#### 新导入方式:
```python
# 装饰器相关
from app.core.permission_decorators import require_permission, require_permission_v2, require_permissions_v2, require_permission_with_expression_v2

# 缓存相关
from app.core.permission_cache import (
    get_permissions_from_cache, 
    set_permissions_to_cache,
    _make_perm_cache_key,
    _compress_permissions,
    _decompress_permissions,
    _make_user_perm_pattern,
    _make_role_perm_pattern,
    _get_redis_client,
    _get_redis_pipeline,
    _redis_batch_get,
    _redis_batch_set,
    _redis_batch_delete,
    _redis_scan_keys,
    monitored_cache,
    invalidate_user_permissions,
    invalidate_role_permissions
)

# 查询相关
from app.core.permission_queries import optimized_single_user_query_v3

# 注册相关
from app.core.permission_registry import (
    register_permission_v2, 
    register_role_v2, 
    register_permission,
    list_registered_permissions
)

# 失效相关
from app.core.permission_invalidation import (
    add_delayed_invalidation,
    distributed_cache_get,
    distributed_cache_set,
    distributed_cache_delete
)

# 系统主类（推荐）
from app.core.permissions_refactored import PermissionSystem, get_permission_system
```

### 2. 更新装饰器使用

#### 旧用法:
```python
@require_permission('perm_name', scope='server', scope_id_arg='server_id')
```

#### 新用法:
```python
@require_permission_v2('perm_name', scope='server', scope_id_arg='server_id')
```

或者使用统一接口:
```python
from app.core.permissions_refactored import require_permission_v2 as require_permission
```

### 3. 更新缓存操作

#### 旧用法:
```python
cached_permissions = _get_permissions_from_cache(cache_key)
_set_permissions_to_cache(cache_key, permissions)
key = _make_perm_cache_key(user_id, scope, scope_id)
compressed = _compress_permissions(permissions)

redis_client = _get_redis_client()
pipeline = _get_redis_pipeline()
results = _redis_batch_get(keys)
success = _redis_batch_set(key_value_pairs)
success = _redis_batch_delete(keys)

# 缓存失效
_invalidate_user_permissions(user_id)
_invalidate_role_permissions(role_id)

# 权限注册
register_permission('perm_name', 'group', 'description')
```

#### 新用法:
```python
from app.core.permission_cache import (
    get_permissions_from_cache, 
    set_permissions_to_cache,
    _make_perm_cache_key,
    _compress_permissions,
    _get_redis_client,
    _get_redis_pipeline,
    _redis_batch_get,
    _redis_batch_set,
    _redis_batch_delete,
    invalidate_user_permissions,
    invalidate_role_permissions
)

from app.core.permission_registry import register_permission

cached_permissions = get_permissions_from_cache(cache_key)
set_permissions_to_cache(cache_key, permissions)
key = _make_perm_cache_key(user_id, scope, scope_id)
compressed = _compress_permissions(permissions)

redis_client = _get_redis_client()
pipeline = _get_redis_pipeline()
results = _redis_batch_get(keys)
success = _redis_batch_set(key_value_pairs)
success = _redis_batch_delete(keys)

# 缓存失效
invalidate_user_permissions(user_id)
invalidate_role_permissions(role_id)

# 权限注册
register_permission('perm_name', 'group', 'description')
```

### 4. 使用统一权限系统接口（推荐）

```python
from app.core.permissions_refactored import get_permission_system

# 获取权限系统实例
permission_system = get_permission_system()

# 检查权限
has_permission = permission_system.check_permission(user_id, 'perm_name', scope='server', scope_id=server_id)

# 批量检查权限
results = permission_system.batch_check_permissions([user_id1, user_id2], 'perm_name')

# 注册权限
permission_system.register_permission('perm_name', 'group', 'description')

# 获取系统统计
stats = permission_system.get_system_stats()
```

## 已完成迁移的模块

1. `app/core/permission_business_flow.py`
2. `app/blueprints/admin/audit_views.py`
3. `app/blueprints/admin/views.py`
4. `app/blueprints/channels/views.py`
5. `app/blueprints/servers/views.py`

## 待迁移模块

请检查以下文件并更新权限系统导入:

```
grep -r "from app.core.permissions import" --include="*.py" .
```

## 测试验证

迁移完成后，请运行以下测试确保功能正常:

```bash
python -m pytest tests/test_permissions_basic.py
python -m pytest tests/test_permissions_cache.py
python -m pytest tests/test_permissions_mysql.py
python -m pytest tests/test_permissions_optimized.py
```

## 基础模块迁移说明

原始 [permissions.py](file:///d:/project/Python/yoto/yoto_backend/app/core/permissions.py) 文件中的基础模块和功能函数已根据其职责迁移到相应的重构模块中：

1. **缓存键生成函数** (`_make_perm_cache_key`, `_make_user_perm_pattern`, `_make_role_perm_pattern`) 已迁移至 `permission_cache.py`
2. **权限压缩/解压缩函数** (`_compress_permissions`, `_decompress_permissions`, `_serialize_permissions`, `_deserialize_permissions`) 已迁移至 `permission_cache.py`
3. **Redis操作函数** (`_get_redis_client`, `_get_redis_pipeline`, `_redis_batch_get`, `_redis_batch_set`, `_redis_batch_delete`, `_redis_scan_keys`) 已迁移至 `permission_cache.py`
4. **监控装饰器函数** (`monitored_cache`) 已迁移至 `permission_cache.py`
5. **缓存失效函数** (`invalidate_user_permissions`, `invalidate_role_permissions`) 已迁移至 `permission_cache.py`
6. **缓存操作函数** (`get_permissions_from_cache`, `_set_permissions_to_cache`) 已迁移至 `permission_cache.py`
7. **权限查询函数** (`_optimized_single_user_query_v3`, `_gather_role_ids_with_inheritance`, `_get_active_user_roles`, `_evaluate_role_conditions`, `_get_permissions_with_scope`, `refresh_user_permissions`, `_batch_refresh_user_permissions`, `_batch_precompute_permissions`, `_optimized_batch_query`) 已迁移至 `permission_queries.py`
8. **权限注册函数** (`register_permission`, `register_permission_v2`, `register_role_v2`, `batch_register_permissions`, `batch_register_roles`, `assign_permissions_to_role_v2`, `assign_roles_to_user_v2`, `get_permission_registry_stats`, `invalidate_registry_cache`, `list_registered_permissions`) 已迁移至 `permission_registry.py`
9. **缓存失效管理函数** (`add_delayed_invalidation`, `get_delayed_invalidation_stats`, `get_invalidation_statistics`, `get_smart_batch_invalidation_analysis`, `execute_smart_batch_invalidation`, `get_cache_auto_tune_suggestions`, `get_cache_invalidation_strategy_analysis`, `get_distributed_cache_stats`, `distributed_cache_get`, `distributed_cache_set`, `distributed_cache_delete`) 已迁移至 `permission_invalidation.py`

这些基础功能在新模块中保持了相同的接口和功能，确保了向后兼容性。

## 回滚计划

如果迁移过程中出现问题，可以通过以下方式回滚:

1. 恢复修改过的文件
2. 确保 [permissions.py](file:///d:/project/Python/yoto/yoto_backend/app/core/permissions.py) 文件未被删除
3. 重新运行原有测试确保功能正常

## 注意事项

1. 重构后的权限系统功能与旧系统完全兼容
2. 所有公共接口名称保持一致，仅模块路径发生变化
3. 建议逐步迁移，避免一次性修改过多文件
4. 迁移过程中注意测试关键业务流程
5. 完成迁移后可考虑删除旧的 [permissions.py](file:///d:/project/Python/yoto/yoto_backend/app/core/permissions.py) 文件