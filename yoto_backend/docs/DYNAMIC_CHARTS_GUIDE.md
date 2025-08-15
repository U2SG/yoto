# 动态图表可视化使用指南

## 概述

动态图表可视化模块提供了实时滚动的性能监控图表，支持多种图表类型和实时数据更新。该模块包含两个主要组件：

1. **性能可视化模块** (`performance_visualization.py`)：负责数据收集和实时更新
2. **WebSocket图表服务器** (`websocket_charts.py`)：提供WebSocket接口供前端访问

## 功能特性

### 🎯 支持的图表类型

1. **缓存命中率图表** (`cache_hit_rate`)
   - L1本地缓存命中率
   - L2分布式缓存命中率
   - 总体命中率

2. **响应时间图表** (`response_time`)
   - 本地缓存响应时间
   - 分布式缓存响应时间
   - 锁操作响应时间

3. **操作频率图表** (`operation_frequency`)
   - 获取操作频率
   - 设置操作频率
   - 失效操作频率

4. **内存使用图表** (`memory_usage`)
   - 本地缓存大小
   - 分布式缓存键数
   - 总内存使用

5. **错误率图表** (`error_rate`)
   - 缓存错误率
   - 锁超时率
   - 连接错误率

### ⚡ 实时特性

- **实时数据收集**：每秒收集一次性能数据
- **实时图表更新**：通过WebSocket实时推送数据
- **滚动图表**：支持时间轴滚动显示
- **多客户端支持**：支持多个客户端同时订阅
- **自动清理**：自动清理过期数据点

## 快速开始

### 1. 启动可视化模块

```python
from app.core.performance_visualization import get_performance_visualization

# 获取可视化实例
viz = get_performance_visualization()

# 模块会自动开始收集数据
print("可视化模块已启动")
```

### 2. 获取实时图表数据

```python
from app.core.performance_visualization import get_real_time_chart_data

# 获取缓存命中率图表数据
chart_data = get_real_time_chart_data('cache_hit_rate', time_range=300)
print(f"图表配置: {chart_data['config']}")
print(f"数据点数量: {len(chart_data['data'])}")
```

### 3. 订阅数据更新

```python
from app.core.performance_visualization import subscribe_to_performance_updates

def on_data_update(data):
    print(f"收到数据更新: {data}")

# 订阅数据更新
subscribe_to_performance_updates(on_data_update)
```

### 4. 启动WebSocket服务器

```python
from app.core.websocket_charts import create_demo_app

# 创建演示应用
app = create_demo_app()

# 启动服务器
app.run(debug=True, host='0.0.0.0', port=5000)
```

## 详细使用说明

### 性能可视化模块

#### 初始化配置

```python
from app.core.performance_visualization import PerformanceVisualization

# 创建自定义配置的可视化实例
viz = PerformanceVisualization(max_data_points=2000)  # 最多保存2000个数据点
```

#### 数据流管理

```python
# 获取最新数据
latest_data = viz.get_latest_data()

# 获取特定图表配置
config = viz.get_chart_config('cache_hit_rate')
print(f"图表标题: {config['title']}")
print(f"图表类型: {config['type']}")
```

#### 订阅系统

```python
# 订阅数据更新
def my_callback(data):
    print(f"缓存命中率: {data['cache_hit_rate']}")
    print(f"响应时间: {data['response_time']}")

viz.subscribe(my_callback)

# 取消订阅
viz.unsubscribe(my_callback)
```

### WebSocket图表服务器

#### 服务器配置

```python
from flask import Flask
from app.core.websocket_charts import get_websocket_chart_server

app = Flask(__name__)
websocket_server = get_websocket_chart_server(app)

@app.route('/status')
def status():
    return websocket_server.get_status()
```

#### 客户端连接

```javascript
// 连接WebSocket服务器
const socket = io('http://localhost:5000');

// 订阅图表数据
socket.emit('subscribe_chart', {
    chart_type: 'cache_hit_rate',
    time_range: 300
});

// 接收图表数据
socket.on('chart_data', function(data) {
    console.log('收到图表数据:', data);
    updateChart(data);
});

// 接收实时更新
socket.on('chart_update', function(data) {
    console.log('收到图表更新:', data);
    updateChart(data);
});
```

## 图表配置

### 缓存命中率图表

```python
config = {
    'title': '缓存命中率',
    'type': 'line',
    'yAxis': {
        'min': 0,
        'max': 1,
        'format': 'percentage'
    },
    'colors': ['#4CAF50', '#2196F3', '#FF9800'],
    'legend': ['L1缓存', 'L2缓存', '总体']
}
```

### 响应时间图表

```python
config = {
    'title': '响应时间',
    'type': 'line',
    'yAxis': {
        'min': 0,
        'max': 100,
        'format': 'milliseconds'
    },
    'colors': ['#4CAF50', '#2196F3', '#FF9800'],
    'legend': ['本地缓存', '分布式缓存', '锁操作']
}
```

## 前端集成示例

### HTML页面

```html
<!DOCTYPE html>
<html>
<head>
    <title>性能监控实时图表</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>性能监控实时图表</h1>
    
    <div class="controls">
        <select id="chartType">
            <option value="cache_hit_rate">缓存命中率</option>
            <option value="response_time">响应时间</option>
            <option value="operation_frequency">操作频率</option>
            <option value="memory_usage">内存使用</option>
            <option value="error_rate">错误率</option>
        </select>
        <button onclick="subscribeChart()">订阅图表</button>
    </div>
    
    <div class="chart-container">
        <canvas id="performanceChart"></canvas>
    </div>
    
    <script>
        const socket = io();
        let currentChart = null;
        
        function subscribeChart() {
            const chartType = document.getElementById('chartType').value;
            socket.emit('subscribe_chart', {
                chart_type: chartType,
                time_range: 300
            });
        }
        
        socket.on('chart_data', function(data) {
            updateChart(data);
        });
        
        socket.on('chart_update', function(data) {
            updateChart(data);
        });
        
        function updateChart(data) {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            
            if (currentChart) {
                currentChart.destroy();
            }
            
            const config = data.data.config;
            const chartData = data.data.data;
            
            const datasets = [];
            const colors = config.colors || ['#4CAF50', '#2196F3', '#FF9800'];
            
            Object.keys(chartData).forEach((key, index) => {
                const points = chartData[key];
                datasets.push({
                    label: config.legend ? config.legend[index] : key,
                    data: points.map(p => ({
                        x: new Date(p.timestamp * 1000),
                        y: p.value
                    })),
                    borderColor: colors[index % colors.length],
                    backgroundColor: colors[index % colors.length] + '20',
                    fill: false
                });
            });
            
            currentChart = new Chart(ctx, {
                type: config.type || 'line',
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    title: {
                        display: true,
                        text: config.title || '性能监控'
                    },
                    scales: {
                        xAxes: [{
                            type: 'time',
                            time: { unit: 'second' }
                        }],
                        yAxes: [{
                            ticks: { beginAtZero: true }
                        }]
                    },
                    animation: { duration: 0 }
                }
            });
        }
        
        // 自动订阅第一个图表
        window.onload = function() {
            setTimeout(subscribeChart, 1000);
        };
    </script>
</body>
</html>
```

## 性能优化

### 数据收集优化

```python
# 调整数据收集频率
class CustomPerformanceVisualization(PerformanceVisualization):
    def _data_collection_worker(self):
        while self._running:
            try:
                # 自定义数据收集逻辑
                self._collect_cache_hit_rate_data()
                self._collect_response_time_data()
                
                # 调整收集间隔
                time.sleep(2)  # 每2秒收集一次
                
            except Exception as e:
                print(f"数据收集错误: {e}")
                time.sleep(10)  # 错误时等待10秒
```

### 内存优化

```python
# 减少数据点数量以节省内存
viz = PerformanceVisualization(max_data_points=500)  # 只保存500个数据点

# 定期清理过期数据
def cleanup_old_data():
    current_time = time.time()
    for stream_name, streams in viz.data_streams.items():
        for metric_name, data_queue in streams.items():
            # 清理超过1小时的数据
            while data_queue and current_time - data_queue[0]['timestamp'] > 3600:
                data_queue.popleft()
```

## 监控和调试

### 服务器状态监控

```python
# 获取服务器状态
status = websocket_server.get_status()
print(f"连接客户端数: {status['connected_clients']}")
print(f"图表订阅数: {status['chart_subscribers']}")
print(f"可用图表: {status['available_charts']}")
```

### 数据质量检查

```python
# 检查数据质量
def check_data_quality():
    latest_data = viz.get_latest_data()
    
    for stream_name, streams in latest_data.items():
        for metric_name, data_points in streams.items():
            if data_points:
                # 检查数据点完整性
                for point in data_points:
                    assert 'timestamp' in point
                    assert 'value' in point
                    assert 'label' in point
                    
                    # 检查时间戳合理性
                    assert 0 < point['timestamp'] < time.time() + 3600
                    
                    # 检查数值合理性
                    assert isinstance(point['value'], (int, float))
```

## 故障排除

### 常见问题

1. **WebSocket连接失败**
   ```python
   # 检查Flask-SocketIO是否正确安装
   pip install flask-socketio
   
   # 检查CORS设置
   socketio = SocketIO(app, cors_allowed_origins="*")
   ```

2. **数据收集异常**
   ```python
   # 检查性能监控模块是否可用
   try:
       from app.core.cache_monitor import get_cache_hit_rate_stats
       stats = get_cache_hit_rate_stats()
   except Exception as e:
       print(f"性能监控模块不可用: {e}")
   ```

3. **内存使用过高**
   ```python
   # 减少数据点数量
   viz = PerformanceVisualization(max_data_points=100)
   
   # 定期清理数据
   viz.data_streams['cache_hit_rate']['l1_cache'].clear()
   ```

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 添加自定义回调进行调试
def debug_callback(data):
    print(f"DEBUG: 收到数据更新")
    print(f"DEBUG: 数据流数量: {len(data)}")
    for stream_name, streams in data.items():
        print(f"DEBUG: {stream_name}: {len(streams)} 个指标")

viz.subscribe(debug_callback)
```

## 最佳实践

1. **合理设置数据点数量**：根据内存限制和精度要求设置合适的`max_data_points`
2. **定期清理数据**：避免内存泄漏，定期清理过期数据
3. **错误处理**：为所有回调函数添加异常处理
4. **性能监控**：监控可视化模块本身的性能影响
5. **安全考虑**：在生产环境中限制WebSocket连接数和数据访问权限

## 扩展开发

### 添加新的图表类型

```python
# 在PerformanceVisualization中添加新的数据流
def _init_data_streams(self):
    # 现有数据流...
    
    # 添加新的数据流
    self.data_streams['custom_metric'] = {
        'metric1': deque(maxlen=self.max_data_points),
        'metric2': deque(maxlen=self.max_data_points)
    }

# 添加新的图表配置
def get_chart_config(self, chart_type: str) -> Dict[str, Any]:
    configs = {
        # 现有配置...
        'custom_metric': {
            'title': '自定义指标',
            'type': 'line',
            'yAxis': {'min': 0, 'max': 100, 'format': 'count'},
            'colors': ['#FF5722', '#9C27B0'],
            'legend': ['指标1', '指标2']
        }
    }
    return configs.get(chart_type, {})
```

### 自定义数据收集

```python
def _collect_custom_metric_data(self):
    """收集自定义指标数据"""
    try:
        timestamp = time.time()
        
        # 自定义数据收集逻辑
        metric1_value = self._calculate_metric1()
        metric2_value = self._calculate_metric2()
        
        with self._lock:
            self.data_streams['custom_metric']['metric1'].append({
                'timestamp': timestamp,
                'value': metric1_value,
                'label': f"{metric1_value:.2f}"
            })
            
            self.data_streams['custom_metric']['metric2'].append({
                'timestamp': timestamp,
                'value': metric2_value,
                'label': f"{metric2_value:.2f}"
            })
            
    except Exception as e:
        print(f"收集自定义指标数据错误: {e}")
```

这个动态图表可视化模块提供了完整的实时性能监控解决方案，支持多种图表类型、实时数据更新和WebSocket通信，可以满足各种性能监控需求。 