# MySQL测试环境使用说明

## 概述

本项目现在支持MySQL数据库的测试环境，用于验证权限系统在真实数据库环境下的性能优化效果。

## 环境要求

1. **MySQL服务器** (推荐8.0+)
2. **Python依赖**:
   - `pymysql`
   - `sqlalchemy`
   - `pytest`

## 快速开始

### 1. 设置MySQL连接

设置环境变量（可选，有默认值）：

```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=gt123456
export MYSQL_DATABASE=yoto_test
```

### 2. 运行MySQL测试环境设置

```bash
cd yoto_backend
python setup_mysql_test.py
```

这个脚本会：
- 自动创建测试数据库
- 测试数据库连接
- 运行MySQL性能测试

### 3. 手动运行MySQL测试

```bash
# 运行所有MySQL测试
python -m pytest tests/test_permissions_mysql.py -v -s

# 运行特定测试
python -m pytest tests/test_permissions_mysql.py::TestPermissionMySQLPerformance::test_mysql_cache_performance -v -s

# 运行并发测试
python -m pytest tests/test_permissions_mysql.py::TestPermissionMySQLPerformance::test_mysql_concurrent_cache_access -v -s
```

## 测试类型

### 1. 缓存性能测试
- 测试LRU缓存在MySQL环境下的性能
- 验证设置和获取操作的时间性能

### 2. 压缩性能测试
- 测试gzip压缩在MySQL环境下的效率
- 验证压缩比和时间性能

### 3. 并发测试
- 测试多线程环境下的缓存访问
- 验证线程安全性和数据一致性

### 4. 数据库集成测试
- 测试权限系统与MySQL数据库的集成
- 验证权限查询性能

### 5. 缓存命中率测试
- 测试LRU策略在MySQL环境下的命中率
- 验证缓存优化效果

### 6. 内存效率测试
- 测试压缩算法在MySQL环境下的内存节省
- 验证内存优化效果

### 7. 压力测试
- 模拟高并发场景
- 验证系统在MySQL环境下的稳定性

## 配置说明

### MySQL测试配置

在 `config.py` 中定义了 `MySQLTestingConfig` 类：

```python
class MySQLTestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('MYSQL_TEST_URI', 'mysql+pymysql://root:password@localhost:3306/yoto_test')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'echo': False
    }
```

### 应用工厂支持

在 `app/__init__.py` 中添加了MySQL测试配置支持：

```python
elif config_name == 'mysql_testing':
    from config import MySQLTestingConfig
    config_class = MySQLTestingConfig
```

## 性能对比

### SQLite vs MySQL 测试环境

| 测试项目 | SQLite | MySQL | 说明 |
|---------|--------|-------|------|
| 缓存性能 | 内存数据库 | 真实数据库 | MySQL更接近生产环境 |
| 并发支持 | 有限 | 完整 | MySQL支持真正的并发 |
| 数据持久化 | 无 | 有 | MySQL测试数据持久化 |
| 网络延迟 | 无 | 有 | MySQL模拟真实网络环境 |

## 故障排除

### 常见问题

1. **连接失败**
   ```
   错误: Can't connect to MySQL server
   解决: 检查MySQL服务是否启动，连接参数是否正确
   ```

2. **权限不足**
   ```
   错误: Access denied for user
   解决: 确保用户有创建数据库的权限
   ```

3. **数据库不存在**
   ```
   错误: Unknown database 'yoto_test'
   解决: 运行 setup_mysql_test.py 自动创建数据库
   ```

### 调试模式

启用SQL语句日志：

```python
# 在 config.py 中设置
SQLALCHEMY_ENGINE_OPTIONS = {
    'echo': True  # 显示SQL语句
}
```

## 性能基准

### 预期性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 缓存设置时间 | < 1ms | 内存操作应该很快 |
| 缓存获取时间 | < 1ms | 内存操作应该很快 |
| 压缩时间 | < 10ms | 压缩算法应该高效 |
| 并发测试 | 100%成功率 | 线程安全 |
| 数据库查询 | < 100ms | 权限查询应该快速 |
| 压力测试 | < 10秒 | 高并发场景稳定性 |

## 扩展测试

### 添加新的MySQL测试

1. 在 `tests/test_permissions_mysql.py` 中添加新的测试方法
2. 使用 `mysql_app` fixture 获取MySQL测试应用
3. 在测试中使用 `with mysql_app.app_context():` 确保数据库上下文

### 自定义测试数据

```python
def test_custom_mysql_test(mysql_app):
    with mysql_app.app_context():
        # 创建自定义测试数据
        user = User(username='custom_user', password_hash='hash')
        db.session.add(user)
        db.session.commit()
        
        # 执行测试逻辑
        # ...
```

## 注意事项

1. **数据清理**: 测试会自动清理数据库，但建议在测试前备份重要数据
2. **并发安全**: MySQL测试涉及真实数据库操作，确保测试环境隔离
3. **性能监控**: 使用 `get_cache_performance_stats()` 监控缓存性能
4. **资源管理**: 大量测试数据可能占用较多内存，注意监控系统资源 