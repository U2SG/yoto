"""
WebSocket演示服务器
用于测试动态图表可视化功能
"""

import time
import threading
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# 导入可视化模块
from app.core.performance_visualization import get_performance_visualization
from app.core.websocket_charts import get_websocket_chart_server

# 创建Flask应用
app = Flask(__name__)
app.config["SECRET_KEY"] = "demo_secret_key"

# 初始化WebSocket服务器
websocket_server = get_websocket_chart_server(app)

# 配置SocketIO使用eventlet
import eventlet

eventlet.monkey_patch()

# HTML模板
DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>动态图表可视化演示</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .status {
            background: #e8f5e8;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .controls {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .controls select, .controls button {
            padding: 8px 12px;
            margin: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .controls button {
            background: #007bff;
            color: white;
            cursor: pointer;
        }
        .controls button:hover {
            background: #0056b3;
        }
        .chart-container {
            width: 100%;
            height: 400px;
            margin: 20px 0;
            position: relative;
        }
        .info-panel {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .info-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .info-card h3 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 16px;
        }
        .info-card p {
            margin: 5px 0;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 动态图表可视化演示</h1>
            <p>实时性能监控图表系统</p>
        </div>
        
        <div class="status" id="status">
            连接状态: 正在连接...
        </div>
        
        <div class="controls">
            <select id="chartType">
                <option value="cache_hit_rate">缓存命中率</option>
                <option value="response_time">响应时间</option>
                <option value="operation_frequency">操作频率</option>
                <option value="memory_usage">内存使用</option>
                <option value="error_rate">错误率</option>
            </select>
            <button onclick="subscribeChart()">订阅图表</button>
            <button onclick="unsubscribeChart()">取消订阅</button>
            <button onclick="getAllCharts()">获取所有图表</button>
            <button onclick="clearChart()">清空图表</button>
        </div>
        
        <div class="info-panel">
            <div class="info-card">
                <h3>📊 当前图表</h3>
                <p id="currentChart">未选择</p>
            </div>
            <div class="info-card">
                <h3>⏱️ 数据点数量</h3>
                <p id="dataPointCount">0</p>
            </div>
            <div class="info-card">
                <h3>🔄 更新频率</h3>
                <p id="updateFrequency">1秒</p>
            </div>
            <div class="info-card">
                <h3>📈 最新数据</h3>
                <p id="latestData">等待数据...</p>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="performanceChart"></canvas>
        </div>
    </div>
    
    <script>
        const socket = io();
        let currentChart = null;
        let chartData = {};
        let updateCount = 0;
        let lastUpdateTime = Date.now();
        
        socket.on('connect', function() {
            document.getElementById('status').innerHTML = 
                '<strong>✅ 连接状态: 已连接</strong><br>服务器地址: ' + window.location.host;
        });
        
        socket.on('disconnect', function() {
            document.getElementById('status').innerHTML = 
                '<strong>❌ 连接状态: 已断开</strong>';
        });
        
        socket.on('chart_data', function(data) {
            console.log('收到图表数据:', data);
            updateChart(data);
            updateInfo(data);
        });
        
        socket.on('chart_update', function(data) {
            console.log('收到图表更新:', data);
            updateChart(data);
            updateInfo(data);
            updateCount++;
            lastUpdateTime = Date.now();
        });
        
        socket.on('all_charts_data', function(data) {
            console.log('收到所有图表数据:', data);
            chartData = data.data;
            updateInfo(data);
        });
        
        function subscribeChart() {
            const chartType = document.getElementById('chartType').value;
            socket.emit('subscribe_chart', {
                chart_type: chartType,
                time_range: 300
            });
            document.getElementById('currentChart').textContent = chartType;
        }
        
        function unsubscribeChart() {
            const chartType = document.getElementById('chartType').value;
            socket.emit('unsubscribe_chart', {
                chart_type: chartType
            });
            document.getElementById('currentChart').textContent = '未选择';
        }
        
        function getAllCharts() {
            socket.emit('get_all_charts');
        }
        
        function clearChart() {
            if (currentChart) {
                currentChart.destroy();
                currentChart = null;
            }
            document.getElementById('dataPointCount').textContent = '0';
            document.getElementById('latestData').textContent = '图表已清空';
        }
        
        function updateChart(data) {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            
            if (currentChart) {
                currentChart.destroy();
            }
            
            const config = data.data.config;
            const chartData = data.data.data;
            
            console.log('图表数据:', chartData);
            
            const datasets = [];
            const colors = config.colors || ['#4CAF50', '#2196F3', '#FF9800'];
            
            Object.keys(chartData).forEach((key, index) => {
                const points = chartData[key];
                if (points && points.length > 0) {
                    datasets.push({
                        label: config.legend ? config.legend[index] : key,
                        data: points.map(p => {
                            const date = new Date(p.timestamp * 1000);
                            console.log('数据点:', p.timestamp, '->', date);
                            return {
                                x: date,
                                y: p.value
                            };
                        }),
                        borderColor: colors[index % colors.length],
                        backgroundColor: colors[index % colors.length] + '20',
                        fill: false,
                        tension: 0.4,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    });
                }
            });
            
            if (datasets.length > 0) {
                currentChart = new Chart(ctx, {
                    type: config.type || 'line',
                    data: {
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        title: {
                            display: true,
                            text: config.title || '性能监控',
                            fontSize: 16
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'second',
                                    displayFormats: {
                                        second: 'HH:mm:ss'
                                    }
                                },
                                title: {
                                    display: true,
                                    text: '时间'
                                }
                            },
                            y: {
                                ticks: {
                                    beginAtZero: true
                                },
                                title: {
                                    display: true,
                                    text: config.yAxis.format === 'percentage' ? '百分比' : 
                                          config.yAxis.format === 'milliseconds' ? '毫秒' : '数值'
                                }
                            }
                        },
                        animation: {
                            duration: 0
                        },
                        legend: {
                            position: 'top'
                        }
                    }
                });
            }
        }
        
        function updateInfo(data) {
            const chartData = data.data.data;
            let totalPoints = 0;
            let latestValue = '无数据';
            
            Object.keys(chartData).forEach(key => {
                const points = chartData[key];
                if (points && points.length > 0) {
                    totalPoints += points.length;
                    if (points.length > 0) {
                        latestValue = points[points.length - 1].label;
                    }
                }
            });
            
            document.getElementById('dataPointCount').textContent = totalPoints;
            document.getElementById('latestData').textContent = latestValue;
            
            // 计算更新频率
            const now = Date.now();
            const timeDiff = now - lastUpdateTime;
            if (timeDiff > 0) {
                const frequency = Math.round(1000 / timeDiff);
                document.getElementById('updateFrequency').textContent = frequency + '次/秒';
            }
        }
        
        // 自动订阅第一个图表
        window.onload = function() {
            setTimeout(() => {
                subscribeChart();
            }, 1000);
        };
        
        // 定期更新信息
        setInterval(() => {
            const now = Date.now();
            const timeDiff = now - lastUpdateTime;
            if (timeDiff > 5000) { // 5秒没有更新
                document.getElementById('updateFrequency').textContent = '暂停';
            }
        }, 1000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """主页"""
    return DEMO_HTML


@app.route("/status")
def status():
    """服务器状态"""
    return websocket_server.get_status()


@app.route("/health")
def health():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "websocket_server": websocket_server.get_status(),
    }


def start_demo_server():
    """启动演示服务器"""
    print("🚀 启动WebSocket演示服务器...")
    print("📊 访问 http://localhost:5000 查看实时图表")
    print("📈 访问 http://localhost:5000/status 查看服务器状态")
    print("💚 访问 http://localhost:5000/health 查看健康状态")
    print("=" * 50)

    # 启动性能可视化
    viz = get_performance_visualization()
    print("✅ 性能可视化模块已启动")

    # 启动Flask应用（使用eventlet）
    websocket_server.socketio.run(app, debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    start_demo_server()
