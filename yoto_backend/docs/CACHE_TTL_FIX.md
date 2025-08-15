# 缓存TTL机制修复

## 问题描述

在原始的 `ResilienceController` 设计中，存在一个严重的逻辑漏洞：**配置缓存永不过期**。

### 问题详情

- **问题**：`_get_from_cache_or_source` 方法中，一旦配置被读入本地缓存，就再也不会从Redis中更新
- **影响**：完全违背了"动态配置，无需重启即可生效"的核心设计目标
- **后果**：运维人员在Redis中做的任何配置变更（如开启降级、调整限流），都无法被正在运行的进程感知到

## 修复方案

### 1. 添加缓存时间戳跟踪

```python
def __init__(self, config_source: Optional[redis.Redis] = None):
    self.local_cache = {}  # 本地缓存
    self.cache_timestamps = {}  # 缓存时间戳
    self.cache_ttl = 30  # 缓存TTL（秒）
```

### 2. 实现TTL检查机制

```python
def _get_from_cache_or_source(self, key: str, default: Any = None) -> Any:
    current_time = time.time()
    
    with self.cache_lock:
        # 检查缓存是否存在且未过期
        if key in self.local_cache:
            cache_timestamp = self.cache_timestamps.get(key, 0)
            if current_time - cache_timestamp < self.cache_ttl:
                # 缓存未过期，直接返回
                return self.local_cache[key]
            else:
                # 缓存已过期，删除缓存
                logger.debug(f"缓存已过期，重新获取配置: {key}")
                del self.local_cache[key]
                if key in self.cache_timestamps:
                    del self.cache_timestamps[key]
        
        # 从数据源获取并更新缓存
        # ... 获取逻辑 ...
        self.cache_timestamps[key] = current_time
```

### 3. 提供TTL管理接口

```python
def set_cache_ttl(self, ttl_seconds: float):
    """设置缓存TTL（秒）"""
    with self.cache_lock:
        self.cache_ttl = ttl_seconds

def get_cache_info(self) -> Dict[str, Any]:
    """获取缓存信息"""
    return {
        'cache_size': len(self.local_cache),
        'cache_ttl': self.cache_ttl,
        'cached_keys': list(self.local_cache.keys()),
        'timestamps': {k: v for k, v in self.cache_timestamps.items()}
    }
```

## 修复效果

### 1. 动态配置更新

- ✅ 配置变更能够在TTL过期后被进程感知
- ✅ 支持实时调整限流、熔断、降级等策略
- ✅ 无需重启进程即可生效

### 2. 性能优化

- ✅ 减少Redis访问频率，提高性能
- ✅ 可配置的TTL，平衡实时性和性能
- ✅ 线程安全的缓存操作

### 3. 运维友好

- ✅ 支持手动清除缓存
- ✅ 提供缓存状态监控
- ✅ 可调整的TTL设置

## 使用示例

### 设置TTL

```python
controller = get_resilience_controller()
controller.set_cache_ttl(60.0)  # 设置60秒TTL
```

### 监控缓存状态

```python
cache_info = controller.get_cache_info()
print(f"缓存大小: {cache_info['cache_size']}")
print(f"TTL设置: {cache_info['cache_ttl']} 秒")
```

### 手动清除缓存

```python
controller.clear_cache()  # 立即清除所有缓存
```

## 测试验证

### 1. TTL过期测试

```python
def test_cache_ttl_expiration(self):
    # 设置短TTL
    controller.set_cache_ttl(0.1)  # 100ms
    
    # 获取配置
    result1 = controller._get_from_cache_or_source("test", {})
    
    # 等待过期
    time.sleep(0.15)
    
    # 过期后重新获取
    result2 = controller._get_from_cache_or_source("test", {})
    # 应该重新从Redis获取
```

### 2. 配置更新测试

```python
def test_cache_ttl_refresh(self):
    # 设置初始配置
    initial_config = {"enabled": True}
    
    # 获取配置
    result1 = controller._get_from_cache_or_source("test", initial_config)
    
    # 模拟配置更新
    updated_config = {"enabled": False}
    
    # 等待TTL过期后获取新配置
    time.sleep(0.25)
    result2 = controller._get_from_cache_or_source("test", updated_config)
    assert result2 != result1  # 应该获取到新配置
```

## 最佳实践

### 1. TTL设置建议

- **开发环境**：5-10秒，便于调试
- **测试环境**：15-30秒，平衡实时性和性能
- **生产环境**：30-60秒，优先考虑性能

### 2. 监控建议

- 定期检查缓存命中率
- 监控配置更新延迟
- 设置合理的告警阈值

### 3. 故障处理

- 配置变更后等待TTL过期
- 紧急情况下可手动清除缓存
- 监控Redis连接状态

## 总结

通过实现缓存TTL机制，成功解决了"配置缓存永不过期"的严重逻辑漏洞，确保了：

1. **动态配置能力**：配置变更能够及时生效
2. **性能优化**：减少不必要的Redis访问
3. **运维友好**：提供完整的缓存管理接口
4. **可靠性**：线程安全的实现

这个修复是韧性模块设计中的关键改进，确保了系统的可维护性和可靠性。 