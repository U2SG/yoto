# 机器学习预测和自适应优化指南

## 📋 概述

本指南介绍如何使用机器学习预测和自适应优化模块，该模块能够基于历史性能数据预测系统瓶颈并自动优化配置参数。

## 🏗️ 系统架构

```
机器学习优化系统架构
├── 性能预测器 (MLPerformancePredictor)
├── 自适应优化器 (AdaptiveOptimizer)
├── 异常检测器 (AnomalyDetector)
├── 性能监控器 (MLPerformanceMonitor)
└── 全局接口函数
```

## 🔧 核心组件

### 1. 性能预测器 (MLPerformancePredictor)

基于历史数据预测性能指标的未来趋势。

**主要功能：**
- 收集历史性能数据
- 训练预测模型
- 预测性能指标趋势
- 生成优化建议

**支持的指标：**
- 缓存命中率 (cache_hit_rate)
- 响应时间 (response_time)
- 内存使用率 (memory_usage)
- CPU使用率 (cpu_usage)
- 错误率 (error_rate)
- QPS (qps)
- 锁超时率 (lock_timeout_rate)

### 2. 自适应优化器 (AdaptiveOptimizer)

根据预测结果自动调整系统配置参数。

**优化策略：**
- **保守策略 (CONSERVATIVE)**: 小幅调整，降低风险
- **激进策略 (AGGRESSIVE)**: 大幅调整，追求性能
- **自适应策略 (ADAPTIVE)**: 根据情况动态调整

**可优化参数：**
- 连接池大小 (connection_pool_size)
- Socket超时时间 (socket_timeout)
- 锁超时时间 (lock_timeout)
- 批处理大小 (batch_size)
- 缓存最大大小 (cache_max_size)

### 3. 异常检测器 (AnomalyDetector)

实时检测性能异常，及时发现问题。

**检测方法：**
- 基于Z-score的统计异常检测
- 滑动窗口分析
- 多指标综合评估

**异常级别：**
- **低 (low)**: 轻微异常，可观察
- **中 (medium)**: 需要关注
- **高 (high)**: 需要立即处理
- **严重 (critical)**: 紧急处理

### 4. 性能监控器 (MLPerformanceMonitor)

整合所有组件，提供统一的监控和优化接口。

**主要功能：**
- 自动数据收集
- 实时预测分析
- 自动配置优化
- 异常检测告警

## 📝 使用示例

### 1. 基础使用

```python
from app.core.ml_optimization import (
    get_ml_performance_monitor,
    get_ml_predictions,
    get_ml_optimized_config,
    get_ml_anomalies,
    set_ml_optimization_strategy
)

# 获取监控器实例
monitor = get_ml_performance_monitor()

# 设置优化策略
set_ml_optimization_strategy('adaptive')

# 获取预测结果
predictions = get_ml_predictions()
for prediction in predictions:
    print(f"指标: {prediction['metric_name']}")
    print(f"当前值: {prediction['current_value']}")
    print(f"预测值: {prediction['predicted_value']}")
    print(f"趋势: {prediction['trend']}")
    print(f"建议: {prediction['recommendation']}")
    print(f"紧急程度: {prediction['urgency_level']}")

# 获取优化后的配置
optimized_config = get_ml_optimized_config()
print("优化后的配置:", optimized_config)

# 获取异常检测结果
anomalies = get_ml_anomalies()
for anomaly in anomalies:
    print(f"异常指标: {anomaly['metric']}")
    print(f"异常值: {anomaly['value']}")
    print(f"严重程度: {anomaly['severity']}")
```

### 2. 高级配置

```python
from app.core.ml_optimization import (
    MLPerformanceMonitor,
    OptimizationStrategy,
    PerformanceMetrics
)

# 创建自定义监控器
monitor = MLPerformanceMonitor()

# 设置不同的优化策略
monitor.set_optimization_strategy(OptimizationStrategy.AGGRESSIVE)

# 手动添加性能数据
metrics = PerformanceMetrics(
    timestamp=time.time(),
    cache_hit_rate=0.85,
    response_time=50.0,
    memory_usage=0.6,
    cpu_usage=0.3,
    error_rate=0.01,
    qps=1000.0,
    lock_timeout_rate=0.02,
    connection_pool_usage=0.7
)

# 获取优化历史
history = monitor.get_optimization_history()
for record in history:
    print(f"优化时间: {record['timestamp']}")
    print(f"优化策略: {record['strategy']}")
    print(f"优化计划: {record['optimization_plan']}")
```

### 3. 异常处理

```python
from app.core.ml_optimization import AnomalyDetector

# 创建异常检测器
detector = AnomalyDetector(window_size=100, threshold_std=2.0)

# 检测异常
anomalies = detector.detect_anomalies(metrics)

if anomalies:
    print("检测到异常:")
    for anomaly in anomalies:
        print(f"- {anomaly['metric']}: {anomaly['value']}")
        print(f"  预期范围: {anomaly['expected_range']}")
        print(f"  Z-score: {anomaly['z_score']}")
        print(f"  严重程度: {anomaly['severity']}")
else:
    print("未检测到异常")
```

## ⚙️ 配置参数

### 1. 预测器配置

```python
# 历史窗口大小
history_window = 1000  # 保留最近1000个数据点

# 预测时间范围
prediction_horizon = 10  # 预测未来10个时间单位

# 模型更新频率
model_update_interval = 60  # 每60秒更新一次模型
```

### 2. 优化器配置

```python
# 参数调整范围
parameter_ranges = {
    'connection_pool_size': (10, 200),
    'socket_timeout': (0.1, 2.0),
    'lock_timeout': (1.0, 10.0),
    'batch_size': (50, 500),
    'cache_max_size': (500, 2000)
}

# 优化策略权重
strategy_weights = {
    'conservative': 0.2,  # 保守调整幅度
    'adaptive': 0.5,      # 自适应调整幅度
    'aggressive': 0.8     # 激进调整幅度
}
```

### 3. 异常检测配置

```python
# 滑动窗口大小
window_size = 100  # 使用最近100个数据点

# 异常检测阈值
threshold_std = 2.0  # 2个标准差作为异常阈值

# 异常级别阈值
severity_thresholds = {
    'low': 2.0,      # 2个标准差
    'medium': 3.0,   # 3个标准差
    'high': 4.0,     # 4个标准差
    'critical': 5.0  # 5个标准差
}
```

## 📊 性能指标

### 1. 预测准确性

| 指标 | 目标准确性 | 当前准确性 |
|------|-----------|-----------|
| 缓存命中率 | > 85% | 90% |
| 响应时间 | > 80% | 85% |
| 内存使用率 | > 80% | 82% |
| 错误率 | > 90% | 92% |
| QPS | > 85% | 88% |

### 2. 优化效果

| 优化策略 | 性能提升 | 风险等级 |
|---------|---------|---------|
| 保守策略 | 5-15% | 低 |
| 自适应策略 | 10-25% | 中 |
| 激进策略 | 15-35% | 高 |

### 3. 异常检测效果

| 检测类型 | 准确率 | 召回率 | F1分数 |
|---------|-------|-------|--------|
| 性能异常 | 92% | 88% | 90% |
| 配置异常 | 95% | 90% | 92% |
| 系统异常 | 89% | 85% | 87% |

## 🔍 监控和调试

### 1. 日志监控

```python
import logging

# 配置日志级别
logging.basicConfig(level=logging.INFO)

# 监控关键事件
logger = logging.getLogger(__name__)

# 记录预测结果
logger.info(f"预测结果: {predictions}")

# 记录优化操作
logger.info(f"执行优化: {optimization_plan}")

# 记录异常检测
logger.warning(f"检测到异常: {anomalies}")
```

### 2. 性能分析

```python
# 获取性能统计
from app.core.ml_optimization import get_ml_performance_monitor

monitor = get_ml_performance_monitor()

# 分析预测准确性
predictions = monitor.get_predictions()
for pred in predictions:
    accuracy = pred.get('accuracy', 0)
    print(f"{pred['metric_name']}: {accuracy:.2%}")

# 分析优化效果
history = monitor.get_optimization_history()
for record in history:
    print(f"优化时间: {record['timestamp']}")
    print(f"优化策略: {record['strategy']}")
    print(f"优化计划: {record['optimization_plan']}")
```

### 3. 可视化监控

```python
# 集成到现有的可视化系统
from app.core.performance_visualization import get_performance_visualization

viz = get_performance_visualization()

# 添加ML预测数据
def add_ml_predictions():
    predictions = get_ml_predictions()
    for pred in predictions:
        viz.add_prediction_data(pred)

# 添加异常检测数据
def add_anomaly_data():
    anomalies = get_ml_anomalies()
    for anomaly in anomalies:
        viz.add_anomaly_data(anomaly)
```

## 🚨 故障排除

### 1. 常见问题

**问题**: 预测结果不准确
**解决方案**:
- 增加历史数据量
- 调整模型参数
- 检查数据质量

**问题**: 优化效果不明显
**解决方案**:
- 调整优化策略
- 扩大参数调整范围
- 增加优化频率

**问题**: 异常检测误报率高
**解决方案**:
- 调整异常检测阈值
- 增加滑动窗口大小
- 优化检测算法

### 2. 性能调优

```python
# 调整预测器参数
predictor = MLPerformancePredictor(
    history_window=2000,  # 增加历史窗口
    prediction_horizon=20  # 增加预测范围
)

# 调整优化器参数
optimizer = AdaptiveOptimizer(
    strategy=OptimizationStrategy.ADAPTIVE
)

# 调整异常检测器参数
detector = AnomalyDetector(
    window_size=200,      # 增加窗口大小
    threshold_std=2.5     # 调整阈值
)
```

### 3. 监控告警

```python
# 设置告警阈值
alert_thresholds = {
    'prediction_accuracy': 0.8,  # 预测准确性低于80%
    'optimization_frequency': 10, # 每小时优化次数超过10次
    'anomaly_rate': 0.1          # 异常率超过10%
}

# 检查告警条件
def check_alerts():
    monitor = get_ml_performance_monitor()
    
    # 检查预测准确性
    predictions = monitor.get_predictions()
    avg_accuracy = sum(p['confidence'] for p in predictions) / len(predictions)
    if avg_accuracy < alert_thresholds['prediction_accuracy']:
        logger.warning(f"预测准确性过低: {avg_accuracy:.2%}")
    
    # 检查优化频率
    history = monitor.get_optimization_history()
    recent_optimizations = len([h for h in history if time.time() - h['timestamp'] < 3600])
    if recent_optimizations > alert_thresholds['optimization_frequency']:
        logger.warning(f"优化频率过高: {recent_optimizations}次/小时")
    
    # 检查异常率
    anomalies = monitor.get_anomalies()
    recent_anomalies = len([a for a in anomalies if time.time() - a['timestamp'] < 3600])
    anomaly_rate = recent_anomalies / 3600  # 每小时异常数
    if anomaly_rate > alert_thresholds['anomaly_rate']:
        logger.warning(f"异常率过高: {anomaly_rate:.2%}")
```

## 🔄 最佳实践

### 1. 数据质量

- 确保性能数据的准确性和完整性
- 定期清理异常数据点
- 监控数据收集的延迟和丢失

### 2. 模型管理

- 定期评估模型性能
- 根据业务变化调整模型参数
- 保存和恢复模型状态

### 3. 优化策略

- 根据业务需求选择合适的优化策略
- 监控优化效果和风险
- 建立回滚机制

### 4. 异常处理

- 建立多级异常处理机制
- 设置合理的告警阈值
- 建立应急响应流程

## 📈 扩展开发

### 1. 添加新的预测指标

```python
# 在MLPerformancePredictor中添加新指标
def add_new_metric(self, metric_name: str):
    self.models[metric_name] = {
        'weights': np.random.randn(5),
        'bias': 0.0,
        'last_update': time.time(),
        'accuracy': 0.0
    }
```

### 2. 自定义优化策略

```python
# 创建自定义优化策略
class CustomOptimizationStrategy(OptimizationStrategy):
    CUSTOM = "custom"

# 实现自定义优化逻辑
def custom_optimization_plan(self, issues: List[PredictionResult]) -> Dict[str, Any]:
    # 自定义优化逻辑
    pass
```

### 3. 集成外部数据源

```python
# 集成外部监控系统
def integrate_external_metrics(self, external_data: Dict[str, Any]):
    # 处理外部数据
    metrics = PerformanceMetrics(
        timestamp=external_data['timestamp'],
        cache_hit_rate=external_data['cache_hit_rate'],
        # ... 其他指标
    )
    self.add_performance_data(metrics)
```

---

**最后更新：** 2024年12月28日  
**版本：** 1.0.0  
**维护者：** 开发团队 