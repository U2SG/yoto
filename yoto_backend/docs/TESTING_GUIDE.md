# 🧪 测试指南

## 📋 概述

本文档提供了完整的测试方法，包括单元测试、集成测试和手动测试，涵盖了所有已开发的模块。

## 🚀 快速开始

### 1. 环境准备

```bash
# 激活虚拟环境
cd yoto_backend
source env/Scripts/activate  # Windows
# source env/bin/activate    # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 基础测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_visualization.py
pytest tests/test_advanced_optimization.py
pytest tests/test_performance_comparison.py
```

## 📊 模块测试详解

### 1. 动态图表可视化模块

#### 1.1 简化测试
```bash
# 运行简化的可视化测试（避免应用上下文问题）
python test_visualization_simple.py
```

**预期输出：**
```
开始简化的动态图表可视化测试...
==================================================

🧪 运行测试: 基础可视化功能
=== 开始基础可视化功能测试 ===
✓ 模块导入成功
✓ 可视化实例创建成功
等待数据收集...
✓ 数据收集完成，数据流数量: 5
  - cache_hit_rate: 3 个指标
    * l1_cache: 3 个数据点
    * l2_cache: 3 个数据点
    * overall: 3 个数据点
✓ cache_hit_rate 图表配置: 缓存命中率监控
✓ response_time 图表配置: 响应时间监控
✓ operation_frequency 图表配置: 操作频率监控
✓ memory_usage 图表配置: 内存使用监控
✓ error_rate 图表配置: 错误率监控
✓ cache_hit_rate 图表数据获取成功
✓ response_time 图表数据获取成功
✓ operation_frequency 图表数据获取成功
✓ memory_usage 图表数据获取成功
✓ error_rate 图表数据获取成功
✓ 订阅系统测试成功
⚠ 未收到数据更新（可能是正常的）
✓ 清理完成
✅ 基础可视化功能 测试通过
```

#### 1.2 WebSocket演示服务器
```bash
# 启动演示服务器
python demo_websocket_server.py
```

**访问地址：**
- 主页：http://localhost:5000
- 状态：http://localhost:5000/status
- 健康检查：http://localhost:5000/health

**功能测试：**
1. 打开浏览器访问 http://localhost:5000
2. 选择不同的图表类型（缓存命中率、响应时间等）
3. 点击"订阅图表"按钮
4. 观察实时数据更新
5. 测试"获取所有图表"功能

### 2. 高级优化模块

#### 2.1 基础功能测试
```bash
# 运行高级优化测试
pytest tests/test_advanced_optimization.py -v
```

**预期输出：**
```
test_advanced_optimization_config_loading PASSED
test_optimized_distributed_lock_creation PASSED
test_advanced_optimizer_initialization PASSED
test_advanced_performance_stats PASSED
test_basic_function_imports PASSED
```

#### 2.2 性能对比测试
```bash
# 运行性能对比测试
pytest tests/test_performance_comparison.py -v
```

**测试内容：**
- 单次操作性能对比
- 大数据量性能测试（1000个权限）
- 批量操作性能对比
- 并发操作性能对比
- 内存使用对比
- 压力测试（1000次迭代）

### 3. 权限系统测试

#### 3.1 简化权限测试
```bash
# 运行简化的权限测试
pytest tests/test_permission_slow_query_simple.py -v
```

#### 3.2 完整权限测试
```bash
# 运行完整权限测试
pytest tests/test_permission_slow_query.py -v
```

### 4. QPS性能测试

```bash
# 运行QPS对比测试
python tests/test_qps_comparison.py
```

**预期输出：**
```
开始QPS性能对比测试...
原始系统 QPS: 1250.5
优化系统 QPS: 2850.3
性能提升: 128.0%
```

### 5. MySQL性能测试

```bash
# 运行MySQL性能测试
python tests/test_mysql_simple.py
```

**测试内容：**
- 数据库连接性能
- 缓存-数据库交互性能
- 并发操作性能
- 压力测试

## 🔧 故障排除

### 1. 应用上下文错误

**错误信息：**
```
RuntimeError: Working outside of application context.
```

**解决方案：**
```python
from app import create_app

app = create_app('testing')
with app.app_context():
    # 你的测试代码
    pass
```

### 2. Redis连接错误

**错误信息：**
```
ConnectionError: Error 10061 connecting to localhost:6379
```

**解决方案：**
```bash
# 启动Redis服务
redis-server

# 或者使用Docker
docker run -d -p 6379:6379 redis:latest
```

### 3. 模块导入错误

**错误信息：**
```
ModuleNotFoundError: No module named 'app.core.performance_visualization'
```

**解决方案：**
```bash
# 确保在正确的目录
cd yoto_backend

# 设置PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## 📈 性能基准

### 预期性能指标

| 测试类型 | 原始系统 | 优化系统 | 提升幅度 |
|---------|---------|---------|---------|
| 单次操作 | 2.5ms | 0.8ms | 68% |
| 批量操作 | 150ms | 45ms | 70% |
| 并发操作 | 500ms | 120ms | 76% |
| QPS | 1200 | 2800 | 133% |
| 内存使用 | 85MB | 45MB | 47% |

### 测试通过标准

- **单元测试**：所有测试通过率 > 95%
- **性能测试**：响应时间 < 100ms
- **内存测试**：内存使用 < 100MB
- **并发测试**：支持 > 50 并发用户

## 🎯 测试最佳实践

### 1. 测试顺序

1. **单元测试**：先运行基础功能测试
2. **集成测试**：测试模块间交互
3. **性能测试**：验证性能优化效果
4. **可视化测试**：测试实时图表功能

### 2. 测试环境

- **开发环境**：使用测试配置
- **隔离环境**：避免影响生产数据
- **清理机制**：测试后清理临时数据

### 3. 持续集成

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ -v
```

## 📝 测试报告

### 生成测试报告

```bash
# 生成HTML报告
pytest tests/ --html=reports/test_report.html --self-contained-html

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### 查看报告

- HTML报告：打开 `reports/test_report.html`
- 覆盖率报告：打开 `htmlcov/index.html`

## 🔍 调试技巧

### 1. 启用详细输出

```bash
# 显示详细输出
pytest -v -s

# 显示最详细输出
pytest -vv -s --tb=long
```

### 2. 调试特定测试

```bash
# 运行特定测试
pytest tests/test_visualization.py::test_visualization_basic -v -s

# 在失败时停止
pytest -x
```

### 3. 性能分析

```bash
# 使用cProfile分析性能
python -m cProfile -o profile.stats tests/test_performance_comparison.py

# 查看分析结果
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(10)"
```

## 📞 获取帮助

如果遇到测试问题：

1. **检查错误日志**：查看详细的错误信息
2. **验证环境**：确保所有依赖已安装
3. **查看文档**：参考相关模块的文档
4. **提交Issue**：在GitHub上提交问题报告

---

**最后更新：** 2024年12月
**版本：** 1.0.0 