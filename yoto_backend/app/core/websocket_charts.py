"""
WebSocket实时图表服务器
提供实时性能数据的WebSocket接口，支持多种图表类型
"""

import asyncio
from flask import request
import json
import time
import threading
from typing import Dict, List, Any, Set
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import Flask, render_template_string

# 导入性能可视化模块
from .performance_visualization import (
    get_performance_visualization,
    get_real_time_chart_data,
    subscribe_to_performance_updates,
    unsubscribe_from_performance_updates,
)


class WebSocketChartServer:
    """WebSocket图表服务器"""

    def __init__(self, app: Flask = None):
        self.app = app
        self.socketio = None
        self.connected_clients: Set[str] = set()
        self.chart_subscribers: Dict[str, Set[str]] = {}
        self.performance_viz = get_performance_visualization()

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """初始化Flask应用"""
        self.app = app
        self.socketio = SocketIO(app, cors_allowed_origins="*")
        self._setup_socket_events()

        # 订阅性能更新
        self.performance_viz.subscribe(self._on_performance_update)

    def _setup_socket_events(self):
        """设置Socket.IO事件"""
        socketio = self.socketio

        @socketio.on("connect")
        def handle_connect():
            """客户端连接"""
            client_id = request.sid
            self.connected_clients.add(client_id)
            print(f"客户端连接: {client_id}")

            # 发送连接确认
            emit(
                "connected",
                {
                    "client_id": client_id,
                    "timestamp": time.time(),
                    "message": "连接成功",
                },
            )

        @socketio.on("disconnect")
        def handle_disconnect():
            """客户端断开连接"""
            client_id = request.sid
            self.connected_clients.discard(client_id)

            # 清理订阅
            for chart_type, subscribers in self.chart_subscribers.items():
                subscribers.discard(client_id)

            print(f"客户端断开连接: {client_id}")

        @socketio.on("subscribe_chart")
        def handle_subscribe_chart(data):
            """订阅图表数据"""
            client_id = request.sid
            chart_type = data.get("chart_type")
            time_range = data.get("time_range", 300)

            if not chart_type:
                emit("error", {"message": "缺少图表类型参数"})
                return

            # 添加到订阅列表
            if chart_type not in self.chart_subscribers:
                self.chart_subscribers[chart_type] = set()
            self.chart_subscribers[chart_type].add(client_id)

            # 发送初始数据
            chart_data = get_real_time_chart_data(chart_type, time_range)
            emit(
                "chart_data",
                {
                    "chart_type": chart_type,
                    "data": chart_data,
                    "timestamp": time.time(),
                },
            )

            print(f"客户端 {client_id} 订阅图表: {chart_type}")

        @socketio.on("unsubscribe_chart")
        def handle_unsubscribe_chart(data):
            """取消订阅图表数据"""
            client_id = request.sid
            chart_type = data.get("chart_type")

            if chart_type in self.chart_subscribers:
                self.chart_subscribers[chart_type].discard(client_id)

            print(f"客户端 {client_id} 取消订阅图表: {chart_type}")

        @socketio.on("get_chart_data")
        def handle_get_chart_data(data):
            """获取图表数据"""
            chart_type = data.get("chart_type")
            time_range = data.get("time_range", 300)

            if not chart_type:
                emit("error", {"message": "缺少图表类型参数"})
                return

            chart_data = get_real_time_chart_data(chart_type, time_range)
            emit(
                "chart_data",
                {
                    "chart_type": chart_type,
                    "data": chart_data,
                    "timestamp": time.time(),
                },
            )

        @socketio.on("get_all_charts")
        def handle_get_all_charts():
            """获取所有图表数据"""
            chart_types = [
                "cache_hit_rate",
                "response_time",
                "operation_frequency",
                "memory_usage",
                "error_rate",
            ]

            all_data = {}
            for chart_type in chart_types:
                chart_data = get_real_time_chart_data(chart_type)
                all_data[chart_type] = chart_data

            emit("all_charts_data", {"data": all_data, "timestamp": time.time()})

    def _on_performance_update(self, data: Dict[str, Any]):
        """性能数据更新回调"""
        if not self.socketio:
            return

        # 为每个图表类型发送更新
        for chart_type, subscribers in self.chart_subscribers.items():
            if not subscribers:
                continue

            chart_data = get_real_time_chart_data(chart_type)

            # 发送给所有订阅该图表的客户端
            for client_id in subscribers:
                if client_id in self.connected_clients:
                    try:
                        self.socketio.emit(
                            "chart_update",
                            {
                                "chart_type": chart_type,
                                "data": chart_data,
                                "timestamp": time.time(),
                            },
                            room=client_id,
                        )
                        print(f"推送图表更新到客户端 {client_id}: {chart_type}")
                    except Exception as e:
                        print(f"推送图表更新失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return {
            "connected_clients": len(self.connected_clients),
            "chart_subscribers": {
                chart_type: len(subscribers)
                for chart_type, subscribers in self.chart_subscribers.items()
            },
            "available_charts": [
                "cache_hit_rate",
                "response_time",
                "operation_frequency",
                "memory_usage",
                "error_rate",
            ],
        }


# 全局WebSocket服务器实例
_websocket_server = None


def get_websocket_chart_server(app: Flask = None) -> WebSocketChartServer:
    """获取WebSocket图表服务器实例"""
    global _websocket_server
    if _websocket_server is None:
        _websocket_server = WebSocketChartServer(app)
    return _websocket_server


# HTML模板用于测试
CHART_DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>性能监控实时图表</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .chart-container { width: 100%; max-width: 800px; margin: 20px 0; }
        .status { background: #f0f0f0; padding: 10px; margin: 10px 0; }
        .controls { margin: 20px 0; }
        button { margin: 5px; padding: 10px; }
        select { padding: 5px; margin: 5px; }
    </style>
</head>
<body>
    <h1>性能监控实时图表</h1>
    
    <div class="status" id="status">
        连接状态: 未连接
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
    </div>
    
    <div class="chart-container">
        <canvas id="performanceChart"></canvas>
    </div>
    
    <script>
        const socket = io();
        let currentChart = null;
        let chartData = {};
        
        socket.on('connect', function() {
            document.getElementById('status').innerHTML = '连接状态: 已连接';
        });
        
        socket.on('disconnect', function() {
            document.getElementById('status').innerHTML = '连接状态: 已断开';
        });
        
        socket.on('chart_data', function(data) {
            console.log('收到图表数据:', data);
            updateChart(data);
        });
        
        socket.on('chart_update', function(data) {
            console.log('收到图表更新:', data);
            updateChart(data);
        });
        
        socket.on('all_charts_data', function(data) {
            console.log('收到所有图表数据:', data);
            chartData = data.data;
        });
        
        function subscribeChart() {
            const chartType = document.getElementById('chartType').value;
            socket.emit('subscribe_chart', {
                chart_type: chartType,
                time_range: 300
            });
        }
        
        function unsubscribeChart() {
            const chartType = document.getElementById('chartType').value;
            socket.emit('unsubscribe_chart', {
                chart_type: chartType
            });
        }
        
        function getAllCharts() {
            socket.emit('get_all_charts');
        }
        
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
                data: {
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    title: {
                        display: true,
                        text: config.title || '性能监控'
                    },
                    scales: {
                        xAxes: [{
                            type: 'time',
                            time: {
                                unit: 'second'
                            }
                        }],
                        yAxes: [{
                            ticks: {
                                beginAtZero: true
                            }
                        }]
                    },
                    animation: {
                        duration: 0
                    }
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
"""


def create_demo_app():
    """创建演示应用"""
    app = Flask(__name__)

    # 初始化WebSocket服务器
    websocket_server = get_websocket_chart_server(app)

    @app.route("/")
    def index():
        """主页"""
        return CHART_DEMO_HTML

    @app.route("/status")
    def status():
        """服务器状态"""
        return websocket_server.get_status()

    return app


if __name__ == "__main__":
    app = create_demo_app()
    print("启动WebSocket图表服务器...")
    print("访问 http://localhost:5000 查看实时图表")

    # 启动性能可视化
    viz = get_performance_visualization()

    # 启动Flask应用
    app.run(debug=True, host="0.0.0.0", port=5000)
