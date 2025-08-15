# 装饰器工厂修复总结

## 问题背景

用户指出了装饰器工厂的"致命Bug"：在 `circuit_breaker`, `rate_limit`, `bulkhead` 的装饰器工厂函数中，每次定义被装饰的函数时都会创建新的韧性组件实例。

### 原有问题

1. **每次装饰都创建新实例**：装饰器工厂每次都调用 `CircuitBreaker(name, controller)` 创建新实例
2. **状态管理失效**：特别是 `Bulkhead` 的状态是本地的，每次调用都得到全新的、`active_calls=0` 的实例
3. **舱壁隔离失效**：舱壁隔离永远不会生效，因为状态无法累积
4. **资源浪费**：对于 `CircuitBreaker` 和 `RateLimiter`，虽然状态在Redis，但每次都创建新对象是资源浪费

## 解决方案

### 1. 全局注册表设计

**实现线程安全的全局注册表**：
```python
# 全局韧性组件注册表 - 线程安全
_resilience_instances = {}
_resilience_lock = threading.RLock()
```

**核心原则**：
- 对于同一个名字的韧性策略，整个应用中只存在一个实例
- 使用线程安全的锁机制确保并发安全
- 提供统一的获取或创建接口

### 2. 单例获取函数

**熔断器单例获取**：
```python
def get_or_create_circuit_breaker(name: str) -> CircuitBreaker:
    """获取或创建熔断器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = CircuitBreaker(name, controller)
            logger.debug(f"创建新的熔断器实例: {name}")
        return _resilience_instances[name]
```

**限流器单例获取**：
```python
def get_or_create_rate_limiter(name: str) -> RateLimiter:
    """获取或创建限流器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = RateLimiter(name, controller)
            logger.debug(f"创建新的限流器实例: {name}")
        return _resilience_instances[name]
```

**舱壁隔离器单例获取**：
```python
def get_or_create_bulkhead(name: str) -> Bulkhead:
    """获取或创建舱壁隔离器实例 - 线程安全"""
    with _resilience_lock:
        if name not in _resilience_instances:
            controller = get_resilience_controller()
            _resilience_instances[name] = Bulkhead(name, controller)
            logger.debug(f"创建新的舱壁隔离器实例: {name}")
        return _resilience_instances[name]
```

### 3. 装饰器工厂修复

**熔断器装饰器修复**：
```python
def circuit_breaker(name: str, fallback_function: Optional[Callable] = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用全局注册表获取或创建熔断器实例
            breaker = get_or_create_circuit_breaker(name)
            # ... 其余逻辑不变
```

**限流器装饰器修复**：
```python
def rate_limit(name: str, key_func: Optional[Callable] = None, multi_key_func: Optional[Callable] = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用全局注册表获取或创建限流器实例
            limiter = get_or_create_rate_limiter(name)
            # ... 其余逻辑不变
```

**舱壁隔离器装饰器修复**：
```python
def bulkhead(name: str, strategy: IsolationStrategy = IsolationStrategy.USER):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用全局注册表获取或创建舱壁隔离器实例
            bulkhead_instance = get_or_create_bulkhead(name)
            # ... 其余逻辑不变
```

### 4. 管理工具函数

**清空注册表**（主要用于测试）：
```python
def clear_resilience_instances():
    """清空韧性组件注册表 - 主要用于测试"""
    with _resilience_lock:
        _resilience_instances.clear()
        logger.info("已清空韧性组件注册表")
```

**获取注册表信息**（用于调试）：
```python
def get_resilience_instances_info() -> Dict[str, str]:
    """获取韧性组件注册表信息 - 用于调试"""
    with _resilience_lock:
        return {name: type(instance).__name__ for name, instance in _resilience_instances.items()}
```

## 技术优势

### 1. 状态持久性
- **舱壁隔离器**：`active_calls`、`total_calls`、`failed_calls` 等状态在多次调用间保持
- **熔断器**：状态在Redis中持久化，多个实例共享同一状态
- **限流器**：状态在Redis中持久化，多个实例共享同一状态

### 2. 资源优化
- 避免重复创建实例，减少内存占用
- 减少对象创建和销毁的开销
- 提高系统性能

### 3. 线程安全
- 使用 `threading.RLock()` 确保并发安全
- 支持多线程环境下的正确行为

### 4. 设计清晰
- 统一的实例管理机制
- 清晰的API设计
- 便于调试和监控

## 测试验证

创建了专门的测试文件 `test_decorator_factory.py` 来验证：

1. **单例行为测试**：验证相同名称的装饰器使用同一实例
2. **状态持久性测试**：验证舱壁隔离器状态在多次调用间保持
3. **多组件独立性测试**：验证不同类型的韧性组件独立管理
4. **注册表管理测试**：验证注册表的清空和信息获取功能

## 使用示例

### 装饰器使用（API不变）
```python
@circuit_breaker("user_service")
def get_user_info(user_id: str):
    # 业务逻辑
    pass

@rate_limit("api_rate_limit")
def api_endpoint():
    # API逻辑
    pass

@bulkhead("database_operations")
def database_query():
    # 数据库操作
    pass
```

### 直接获取实例
```python
# 获取熔断器实例
breaker = get_or_create_circuit_breaker("user_service")

# 获取限流器实例
limiter = get_or_create_rate_limiter("api_rate_limit")

# 获取舱壁隔离器实例
bulkhead_instance = get_or_create_bulkhead("database_operations")
```

### 调试和监控
```python
# 获取注册表信息
instances_info = get_resilience_instances_info()
print(f"当前韧性组件: {instances_info}")

# 清空注册表（主要用于测试）
clear_resilience_instances()
```

## 总结

这次修复解决了装饰器工厂的"致命Bug"，通过实现全局注册表确保了：

1. **状态持久性**：特别是舱壁隔离器的本地状态能够正确累积
2. **资源优化**：避免重复创建实例，提高系统性能
3. **线程安全**：支持多线程环境下的正确行为
4. **设计清晰**：统一的实例管理机制，便于维护和扩展

修复后的装饰器工厂符合单例模式的最佳实践，确保了韧性策略的正确性和有效性。 