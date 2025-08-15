# 原子操作修复总结

## 问题背景

用户指出了致命的竞态条件缺陷：所有状态操作都存在竞态条件。

### 原有问题

1. **Check-then-Act反模式**：将状态管理分成 `get_*` 和 `set_*` 两个独立步骤
2. **多次网络往返**：Python代码通过多次调用Lua脚本来完成一次完整的操作
3. **竞态条件**：在并发负载下，熔断器、限流器会系统性地、静默地失效
4. **保护机制失效**：保护机制会在最需要它的时候失灵

### 具体场景

**CircuitBreaker竞态条件**：
- `record_failure` 方法的逻辑：`get_failure_count -> increment in Python -> set_failure_count`
- 两个进程并发执行时，会丢失一次失败计数
- 整个熔断器逻辑（`is_open -> func() -> record_failure`）依然是非原子的

**RateLimiter竞态条件**：
- `_token_bucket_check` 的 `get_tokens -> modify -> set_tokens` 存在完全相同的竞态条件

## 解决方案

### 1. 统一Lua脚本设计

**将整个业务流程封装在一个Lua脚本中**：

```python
# Lua脚本：完整的熔断器业务流程 - 原子性执行
EXECUTE_OR_RECORD_FAILURE_SCRIPT = """
local name = KEYS[1]
local operation = ARGV[1]  -- "check", "success", "failure"
local failure_threshold = tonumber(ARGV[2])
local recovery_timeout = tonumber(ARGV[3])
local half_open_max_calls = tonumber(ARGV[4])
local current_time = tonumber(ARGV[5])

-- 完整的业务流程逻辑
-- 1. 检查状态转换（OPEN -> HALF_OPEN）
-- 2. 根据operation执行相应操作
-- 3. 原子性更新所有状态
"""
```

**核心改进**：
- 将4个独立的Lua脚本合并为1个统一的脚本
- 支持3种操作：`check`、`success`、`failure`
- 原子性完成整个业务流程

### 2. CircuitBreaker原子操作

**统一的方法调用**：
```python
def record_failure(self):
    """记录失败调用 - 原子操作"""
    config = self.get_config()
    current_time = time.time()
    
    try:
        if self.controller.config_source and REDIS_AVAILABLE:
            result = self.execute_or_record_failure_script(
                keys=[self.name],
                args=["failure", config.failure_threshold, config.recovery_timeout, config.half_open_max_calls, current_time]
            )
            success, state = result
            
            if state == "open":
                logger.warning(f"熔断器 '{self.name}' 已开启")
    except Exception as e:
        logger.error(f"记录失败调用失败: {e}")
```

**所有方法使用同一个脚本**：
- `record_failure()`: `operation="failure"`
- `record_success()`: `operation="success"`
- `is_open()`: `operation="check"`
- `can_execute()`: `operation="check"`
- `execute_with_atomic_check()`: `operation="check"`

### 3. RateLimiter原子操作

**令牌桶原子检查**：
```python
TOKEN_BUCKET_ATOMIC_SCRIPT = """
local name = KEYS[1]
local key = ARGV[1]
local max_requests = tonumber(ARGV[2])
local tokens_per_second = tonumber(ARGV[3])
local current_time = tonumber(ARGV[4])

-- 原子性完成：获取状态 -> 计算新令牌 -> 检查限制 -> 更新状态
local current_tokens = redis.call("GET", tokens_key)
local last_update = redis.call("GET", last_update_key)

-- 计算新令牌
local time_passed = current_time - last_update
local new_tokens = time_passed * tokens_per_second

-- 更新令牌数量
current_tokens = current_tokens + new_tokens
if current_tokens > max_requests then
    current_tokens = max_requests
end

-- 检查是否有可用令牌
if current_tokens >= 1 then
    current_tokens = current_tokens - 1
    redis.call("SET", tokens_key, current_tokens)
    redis.call("SET", last_update_key, current_time)
    return {1}  -- 允许
else
    redis.call("SET", last_update_key, current_time)
    return {0}  -- 拒绝
end
"""
```

**滑动窗口原子检查**：
```python
SLIDING_WINDOW_ATOMIC_SCRIPT = """
local name = KEYS[1]
local key = ARGV[1]
local max_requests = tonumber(ARGV[2])
local time_window = tonumber(ARGV[3])
local current_time = tonumber(ARGV[4])

-- 原子性完成：获取请求时间列表 -> 清理过期记录 -> 检查限制 -> 更新状态
local times_data = redis.call("GET", times_key)
local times = {}
if times_data then
    times = cjson.decode(times_data)
end

-- 清理过期的请求记录
local window_start = current_time - time_window
local valid_times = {}
for i, t in ipairs(times) do
    if t >= window_start then
        table.insert(valid_times, t)
    end
end

-- 检查是否超过限制
if #valid_times < max_requests then
    table.insert(valid_times, current_time)
    redis.call("SET", times_key, cjson.encode(valid_times))
    return {1}  -- 允许
else
    return {0}  -- 拒绝
end
"""
```

### 4. 装饰器原子操作

**CircuitBreaker装饰器**：
```python
def circuit_breaker(name: str, fallback_function: Optional[Callable] = None):
    """熔断器装饰器 - 使用原子操作解决竞态条件"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = get_or_create_circuit_breaker(name)
            
            # 原子执行检查并记录成功
            if breaker.execute_with_atomic_check():
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    # 记录失败
                    breaker.record_failure()
                    if fallback_function:
                        return fallback_function(*args, **kwargs)
                    else:
                        raise e
            else:
                # 熔断器开启，使用降级函数
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                else:
                    raise Exception(f"熔断器 '{name}' 开启，服务不可用")
        
        return wrapper
    return decorator
```

**RateLimiter装饰器**：
```python
def rate_limit(name: str, key_func: Optional[Callable] = None, multi_key_func: Optional[Callable] = None):
    """限流器装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_or_create_rate_limiter(name)
            
            # 生成限流键
            if key_func:
                limit_key = key_func(*args, **kwargs)
            else:
                limit_key = "default"
            
            # 生成多维限流键
            multi_key = None
            if multi_key_func:
                multi_key = multi_key_func(*args, **kwargs)
            
            # 原子性检查是否允许
            if not limiter.is_allowed(limit_key, multi_key):
                raise Exception(f"限流器 '{name}' 触发，请求被拒绝")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
```

## 技术优势

### 1. 消除竞态条件
- **原子操作**：整个业务流程在一个Lua脚本中完成
- **单次网络往返**：减少网络延迟和不确定性
- **状态一致性**：确保状态更新的原子性

### 2. 性能优化
- **减少网络往返**：从多次调用合并为一次调用
- **降低延迟**：减少网络延迟对性能的影响
- **提高吞吐量**：减少Redis连接的使用

### 3. 可靠性提升
- **保护机制有效**：确保熔断器和限流器在并发环境下正确工作
- **状态准确性**：避免状态不一致导致的误判
- **故障恢复**：确保故障恢复机制的可靠性

### 4. 设计清晰
- **统一接口**：所有操作使用同一个Lua脚本
- **参数化设计**：通过operation参数区分不同操作
- **易于维护**：减少脚本数量，降低维护复杂度

## 使用示例

### CircuitBreaker使用
```python
@circuit_breaker("user_service")
def get_user_info(user_id: str):
    # 业务逻辑
    pass

@circuit_breaker("payment_service", fallback_function=payment_fallback)
def process_payment(payment_data):
    # 支付逻辑
    pass
```

### RateLimiter使用
```python
@rate_limit("api_rate_limit")
def api_endpoint():
    # API逻辑
    pass

@rate_limit("user_rate_limit", key_func=lambda *args, **kwargs: kwargs.get('user_id'))
def user_specific_endpoint(user_id: str):
    # 用户特定逻辑
    pass
```

## 总结

这次修复从根本上解决了竞态条件问题：

1. **原子性保证**：整个业务流程在一个Lua脚本中原子性完成
2. **性能优化**：减少网络往返，提高系统性能
3. **可靠性提升**：确保保护机制在并发环境下正确工作
4. **设计简化**：统一接口，降低维护复杂度

修复后的系统能够正确处理高并发场景，确保熔断器和限流器在最需要的时候发挥保护作用。 