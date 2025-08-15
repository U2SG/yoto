# API迁移指南

## 概述

本文档提供了从旧版兼容性函数迁移到新版HybridPermissionCache API的详细指南。

## 弃用时间表

- **当前版本**: 1.5.0
- **弃用开始**: 1.5.0
- **迁移截止**: 1.9.0
- **移除版本**: 2.0.0

## 迁移映射表

### 1. 缓存获取函数

**旧API**:
```python
from app.core.hybrid_permission_cache import get_permissions_from_cache

# 直接操作缓存
permissions = get_permissions_from_cache("perm:abc123")
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例方法
cache = HybridPermissionCache()
permissions = cache.get_permission(user_id, permission, strategy='hybrid')
```

### 2. 缓存设置函数

**旧API**:
```python
from app.core.hybrid_permission_cache import set_permissions_to_cache

# 直接设置缓存
set_permissions_to_cache("perm:abc123", {'read_channel', 'send_message'})
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例方法，会自动缓存
cache = HybridPermissionCache()
permissions = cache.get_permission(user_id, permission)  # 自动缓存
```

### 3. 权限获取函数

**旧API**:
```python
from app.core.hybrid_permission_cache import get_permission

# 全局便捷函数
result = get_permission(user_id, 'read_channel')
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例方法
cache = HybridPermissionCache()
result = cache.get_permission(user_id, 'read_channel')
```

### 4. 批量权限获取

**旧API**:
```python
from app.core.hybrid_permission_cache import batch_get_permissions

# 全局便捷函数
results = batch_get_permissions([1, 2, 3], 'read_channel')
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例方法
cache = HybridPermissionCache()
results = cache.batch_get_permissions([1, 2, 3], 'read_channel')
```

### 5. 缓存统计

**旧API**:
```python
from app.core.hybrid_permission_cache import get_cache_performance_stats

# 兼容性函数
stats = get_cache_performance_stats()
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例方法
cache = HybridPermissionCache()
stats = cache.get_stats()
```

### 6. LRU缓存访问

**旧API**:
```python
from app.core.hybrid_permission_cache import get_lru_cache

# 全局函数
lru_cache = get_lru_cache()
```

**新API**:
```python
from app.core.hybrid_permission_cache import HybridPermissionCache

# 使用实例属性
cache = HybridPermissionCache()
lru_cache = cache.complex_cache  # 或 cache.simple_cache
```

## 最佳实践

### 1. 实例管理

```python
# 推荐：在应用级别创建单例
class PermissionService:
    def __init__(self):
        self.cache = HybridPermissionCache()
    
    def check_permission(self, user_id, permission):
        return self.cache.get_permission(user_id, permission)

# 使用
permission_service = PermissionService()
result = permission_service.check_permission(user_id, 'read_channel')
```

### 2. 依赖注入

```python
# 推荐：使用依赖注入模式
class UserController:
    def __init__(self, permission_cache: HybridPermissionCache):
        self.cache = permission_cache
    
    def get_user_permissions(self, user_id):
        return self.cache.get_permission(user_id, 'all_permissions')

# 使用
cache = HybridPermissionCache()
controller = UserController(cache)
```

### 3. 测试友好

```python
# 推荐：每个测试使用独立实例
def test_permission_check():
    cache = HybridPermissionCache()  # 独立实例
    result = cache.get_permission(1, 'read_channel')
    assert result is True
```

## 迁移检查清单

- [ ] 替换所有 `get_permissions_from_cache()` 调用
- [ ] 替换所有 `set_permissions_to_cache()` 调用
- [ ] 替换所有 `get_permission()` 调用
- [ ] 替换所有 `batch_get_permissions()` 调用
- [ ] 替换所有 `get_cache_performance_stats()` 调用
- [ ] 替换所有 `get_lru_cache()` 调用
- [ ] 更新测试代码使用独立实例
- [ ] 更新文档和注释

## 常见问题

### Q: 为什么需要迁移？

A: 旧API存在以下问题：
- 全局状态依赖，影响测试和隔离
- 绕过精心设计的新架构
- 可能导致缓存一致性问题

### Q: 迁移会影响性能吗？

A: 不会，新API性能更好：
- 实例级别的缓存，避免全局竞争
- 更精确的缓存失效机制
- 更好的内存管理

### Q: 如何确保向后兼容？

A: 在v2.0.0之前：
- 旧API仍然可用
- 会显示弃用警告
- 建议尽快迁移

## 支持

如果在迁移过程中遇到问题，请：
1. 查看本文档
2. 检查弃用警告信息
3. 参考代码示例
4. 联系开发团队 