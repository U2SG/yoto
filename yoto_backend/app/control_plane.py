"""
权限系统统一控制平面

提供运维仪表盘功能，包括：
- 实时配置管理
- 性能监控可视化
- 系统状态查看
- 事件流监控
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
from flask import Flask, jsonify, request, render_template_string
from flask_socketio import SocketIO, emit
import redis

# 导入权限系统模块
from .core.permission.permission_resilience import get_resilience_controller
from .core.permission.hybrid_permission_cache import get_hybrid_cache
from .core.permission.permission_monitor import get_permission_monitor

logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config["SECRET_KEY"] = "yoto_control_plane_secret"
socketio = SocketIO(app, cors_allowed_origins="*")

# 权限系统组件 - 延迟初始化
resilience_controller = None
hybrid_cache = None
permission_monitor = None


def _get_resilience_controller():
    """延迟获取韧性控制器"""
    global resilience_controller
    if resilience_controller is None:
        try:
            resilience_controller = get_resilience_controller()
        except Exception as e:
            logger.warning(f"韧性控制器初始化失败: {e}")
    return resilience_controller


def _get_hybrid_cache():
    """延迟获取混合缓存"""
    global hybrid_cache
    if hybrid_cache is None:
        try:
            hybrid_cache = get_hybrid_cache()
        except Exception as e:
            logger.warning(f"混合缓存初始化失败: {e}")
    return hybrid_cache


def _get_permission_monitor():
    """延迟获取权限监控器"""
    global permission_monitor
    if permission_monitor is None:
        try:
            permission_monitor = get_permission_monitor()
        except Exception as e:
            logger.warning(f"权限监控器初始化失败: {e}")
    return permission_monitor


# Redis连接用于事件流
try:
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"Redis连接失败: {e}")
    redis_client = None
    REDIS_AVAILABLE = False

# ==================== API路由 ====================


@app.route("/")
def dashboard():
    """主仪表盘页面"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>权限系统控制平面</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .status { padding: 5px 10px; border-radius: 3px; color: white; }
            .status.healthy { background-color: #28a745; }
            .status.warning { background-color: #ffc107; }
            .status.error { background-color: #dc3545; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .chart-container { height: 300px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>权限系统控制平面</h1>
            
            <div class="grid">
                <div class="card">
                    <h3>系统状态</h3>
                    <div id="system-status"></div>
                </div>
                
                <div class="card">
                    <h3>维护模式</h3>
                    <div id="maintenance-mode">
                        <button onclick="toggleMaintenanceMode()">切换维护模式</button>
                        <span id="maintenance-status"></span>
                    </div>
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h3>性能指标</h3>
                    <canvas id="performance-chart"></canvas>
                </div>
                
                <div class="card">
                    <h3>缓存统计</h3>
                    <div id="cache-stats"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>实时事件</h3>
                <div id="events-log" style="height: 200px; overflow-y: scroll; border: 1px solid #ddd; padding: 10px;"></div>
            </div>
        </div>
        
        <script>
            const socket = io();
            
            // 连接事件
            socket.on('connect', function() {
                console.log('Connected to control plane');
            });
            
            // 接收系统状态更新
            socket.on('system_status', function(data) {
                updateSystemStatus(data);
            });
            
            // 接收性能指标更新
            socket.on('performance_metrics', function(data) {
                updatePerformanceChart(data);
            });
            
            // 接收缓存统计更新
            socket.on('cache_stats', function(data) {
                updateCacheStats(data);
            });
            
            // 接收实时事件
            socket.on('real_time_event', function(data) {
                addEventToLog(data);
            });
            
            function updateSystemStatus(data) {
                const statusDiv = document.getElementById('system-status');
                statusDiv.innerHTML = `
                    <p><strong>整体状态:</strong> <span class="status ${data.overall_status}">${data.overall_status}</span></p>
                    <p><strong>缓存状态:</strong> <span class="status ${data.cache_status}">${data.cache_status}</span></p>
                    <p><strong>性能状态:</strong> <span class="status ${data.performance_status}">${data.performance_status}</span></p>
                    <p><strong>错误状态:</strong> <span class="status ${data.error_status}">${data.error_status}</span></p>
                `;
            }
            
            function updateCacheStats(data) {
                const statsDiv = document.getElementById('cache-stats');
                statsDiv.innerHTML = `
                    <p><strong>命中率:</strong> ${data.hit_rate}%</p>
                    <p><strong>总请求:</strong> ${data.total_requests}</p>
                    <p><strong>缓存大小:</strong> ${data.cache_size}</p>
                    <p><strong>平均响应时间:</strong> ${data.avg_response_time}ms</p>
                `;
            }
            
            function addEventToLog(event) {
                const logDiv = document.getElementById('events-log');
                const timestamp = new Date().toLocaleTimeString();
                logDiv.innerHTML += `<div>[${timestamp}] ${event.type}: ${event.message}</div>`;
                logDiv.scrollTop = logDiv.scrollHeight;
            }
            
            function toggleMaintenanceMode() {
                fetch('/api/maintenance/toggle', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('maintenance-status').textContent = 
                            data.enabled ? '维护模式已启用' : '维护模式已禁用';
                    });
            }
            
            // 初始化性能图表
            const ctx = document.getElementById('performance-chart').getContext('2d');
            const performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '响应时间 (ms)',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
            
            function updatePerformanceChart(data) {
                const labels = performanceChart.data.labels;
                const values = performanceChart.data.datasets[0].data;
                
                labels.push(new Date().toLocaleTimeString());
                values.push(data.response_time);
                
                if (labels.length > 20) {
                    labels.shift();
                    values.shift();
                }
                
                performanceChart.update();
            }
        </script>
    </body>
    </html>
    """
    return html_template


@app.route("/api/status")
def get_system_status():
    """获取系统状态"""
    try:
        monitor = _get_permission_monitor()
        if monitor:
            health_status = monitor.get_health_status()
            return jsonify(
                {
                    "status": health_status.overall_status,
                    "cache_status": health_status.cache_status,
                    "performance_status": health_status.performance_status,
                    "error_status": health_status.error_status,
                    "alerts_count": len(health_status.alerts),
                    "timestamp": time.time(),
                }
            )
        else:
            # 如果监控器不可用，提供基本状态
            return jsonify(
                {
                    "status": "healthy",
                    "cache_status": "unknown",
                    "performance_status": "unknown",
                    "error_status": "unknown",
                    "alerts_count": 0,
                    "timestamp": time.time(),
                }
            )
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return (
            jsonify({"status": "error", "error": str(e), "timestamp": time.time()}),
            500,
        )


@app.route("/api/maintenance/status")
def get_maintenance_status():
    """获取维护模式状态"""
    try:
        controller = _get_resilience_controller()
        if not controller:
            return jsonify({"error": "韧性控制器不可用"}), 500
        enabled = controller.is_global_switch_enabled("maintenance_mode")
        return jsonify({"enabled": enabled})
    except Exception as e:
        logger.error(f"获取维护模式状态失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/maintenance/toggle", methods=["POST"])
def toggle_maintenance_mode():
    """切换维护模式"""
    try:
        controller = _get_resilience_controller()
        if not controller:
            return jsonify({"error": "韧性控制器不可用"}), 500

        current_status = controller.is_global_switch_enabled("maintenance_mode")
        new_status = not current_status

        success = controller.set_global_switch("maintenance_mode", new_status)

        if success:
            # 发布事件
            if REDIS_AVAILABLE:
                event_data = {
                    "type": "maintenance_mode_toggled",
                    "enabled": new_status,
                    "timestamp": time.time(),
                }
                redis_client.publish("permission:events", json.dumps(event_data))

            return jsonify({"enabled": new_status, "message": "维护模式已切换"})
        else:
            return jsonify({"error": "切换维护模式失败"}), 500
    except Exception as e:
        logger.error(f"切换维护模式失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/config/circuit_breaker/<name>", methods=["GET", "PUT"])
def circuit_breaker_config(name):
    """熔断器配置管理"""
    if request.method == "GET":
        try:
            controller = _get_resilience_controller()
            if not controller:
                return jsonify({"error": "韧性控制器不可用"}), 500
            config = controller.get_circuit_breaker_config(name)
            if config:
                return jsonify(
                    {
                        "name": config.name,
                        "failure_threshold": config.failure_threshold,
                        "recovery_timeout": config.recovery_timeout,
                        "expected_exception": config.expected_exception,
                        "monitor_interval": config.monitor_interval,
                        "state": config.state.value,
                    }
                )
            else:
                return jsonify({"error": "熔断器配置不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == "PUT":
        try:
            data = request.get_json()
            from .core.permission.permission_resilience import (
                CircuitBreakerConfig,
                CircuitBreakerState,
            )

            config = CircuitBreakerConfig(
                name=name,
                failure_threshold=data.get("failure_threshold", 5),
                recovery_timeout=data.get("recovery_timeout", 60.0),
                expected_exception=data.get("expected_exception", "Exception"),
                monitor_interval=data.get("monitor_interval", 10.0),
                state=CircuitBreakerState(data.get("state", "closed")),
            )

            success = controller.set_circuit_breaker_config(name, config)
            if success:
                # 发布事件到Redis
                if REDIS_AVAILABLE:
                    event_data = {
                        "type": "config_updated",
                        "config_type": "circuit_breaker",
                        "config_name": name,
                        "timestamp": time.time(),
                    }
                    redis_client.publish("permission:events", json.dumps(event_data))

                return jsonify({"message": "熔断器配置已更新"})
            else:
                return jsonify({"error": "更新熔断器配置失败"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/config/rate_limiter/<name>", methods=["GET", "PUT"])
def rate_limiter_config(name):
    """限流器配置管理"""
    if request.method == "GET":
        try:
            controller = _get_resilience_controller()
            if not controller:
                return jsonify({"error": "韧性控制器不可用"}), 500
            config = controller.get_rate_limit_config(name)
            if config:
                return jsonify(
                    {
                        "name": config.name,
                        "limit_type": config.limit_type.value,
                        "max_requests": config.max_requests,
                        "time_window": config.time_window,
                        "tokens_per_second": config.tokens_per_second,
                        "enabled": config.enabled,
                        "multi_dimensional": config.multi_dimensional,
                        "user_id_limit": config.user_id_limit,
                        "server_id_limit": config.server_id_limit,
                        "ip_limit": config.ip_limit,
                        "combined_limit": config.combined_limit,
                    }
                )
            else:
                return jsonify({"error": "限流器配置不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == "PUT":
        try:
            data = request.get_json()
            from .core.permission.permission_resilience import (
                RateLimitConfig,
                RateLimitType,
            )

            config = RateLimitConfig(
                name=name,
                limit_type=RateLimitType(data.get("limit_type", "token_bucket")),
                max_requests=data.get("max_requests", 100),
                time_window=data.get("time_window", 60.0),
                tokens_per_second=data.get("tokens_per_second", 10.0),
                enabled=data.get("enabled", True),
                multi_dimensional=data.get("multi_dimensional", False),
                user_id_limit=data.get("user_id_limit", 50),
                server_id_limit=data.get("server_id_limit", 200),
                ip_limit=data.get("ip_limit", 100),
                combined_limit=data.get("combined_limit", 300),
            )

            success = resilience_controller.set_rate_limit_config(name, config)
            if success:
                # 发布事件到Redis
                if REDIS_AVAILABLE:
                    event_data = {
                        "type": "config_updated",
                        "config_type": "rate_limiter",
                        "config_name": name,
                        "timestamp": time.time(),
                    }
                    redis_client.publish("permission:events", json.dumps(event_data))

                return jsonify({"message": "限流器配置已更新"})
            else:
                return jsonify({"error": "更新限流器配置失败"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/stats/performance")
def get_performance_stats():
    """获取性能统计"""
    try:
        cache = _get_hybrid_cache()
        if not cache:
            return jsonify({"error": "混合缓存不可用"}), 500
        performance_analysis = cache.get_performance_analysis()
        return jsonify(performance_analysis)
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats/cache")
def get_cache_stats():
    """获取缓存统计"""
    try:
        cache_stats = hybrid_cache.get_stats()
        return jsonify(cache_stats)
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/events/recent")
def get_recent_events():
    """获取最近事件"""
    try:
        if permission_monitor:
            events_summary = permission_monitor.get_events_summary()
            return jsonify(events_summary)
        else:
            return jsonify({"error": "权限监控器不可用"}), 503
    except Exception as e:
        logger.error(f"获取最近事件失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== WebSocket事件处理 ====================


@socketio.on("connect")
def handle_connect():
    """客户端连接处理"""
    logger.info(f"客户端已连接: {request.sid}")
    emit("connected", {"message": "已连接到权限系统控制平面"})


@socketio.on("disconnect")
def handle_disconnect():
    """客户端断开连接处理"""
    logger.info(f"客户端已断开: {request.sid}")


def broadcast_system_status():
    """广播系统状态"""
    try:
        if permission_monitor:
            status = permission_monitor.get_health_status()
            socketio.emit(
                "system_status",
                {
                    "overall_status": status.overall_status,
                    "cache_status": status.cache_status,
                    "performance_status": status.performance_status,
                    "error_status": status.error_status,
                    "alerts_count": len(status.alerts),
                    "timestamp": time.time(),
                },
            )
        else:
            # 如果监控器不可用，提供基本状态
            socketio.emit(
                "system_status",
                {
                    "overall_status": "healthy",
                    "cache_status": "unknown",
                    "performance_status": "unknown",
                    "error_status": "unknown",
                    "alerts_count": 0,
                    "timestamp": time.time(),
                },
            )
    except Exception as e:
        logger.error(f"广播系统状态失败: {e}")


def broadcast_performance_metrics():
    """广播性能指标"""
    try:
        performance_analysis = hybrid_cache.get_performance_analysis()
        socketio.emit(
            "performance_metrics",
            {
                "response_time": performance_analysis.get("avg_response_time", 0),
                "throughput": performance_analysis.get("throughput", 0),
                "error_rate": performance_analysis.get("error_rate", 0),
            },
        )
    except Exception as e:
        logger.error(f"广播性能指标失败: {e}")


def broadcast_cache_stats():
    """广播缓存统计"""
    try:
        cache_stats = hybrid_cache.get_stats()
        socketio.emit(
            "cache_stats",
            {
                "hit_rate": cache_stats.get("hit_rate", 0),
                "total_requests": cache_stats.get("total_requests", 0),
                "cache_size": cache_stats.get("cache_size", 0),
                "avg_response_time": cache_stats.get("avg_response_time", 0),
            },
        )
    except Exception as e:
        logger.error(f"广播缓存统计失败: {e}")


# ==================== 后台任务 ====================


def start_background_tasks():
    """启动后台任务"""
    import threading
    import time

    def broadcast_loop():
        """广播循环"""
        while True:
            try:
                broadcast_system_status()
                broadcast_performance_metrics()
                broadcast_cache_stats()
                time.sleep(5)  # 每5秒广播一次
            except Exception as e:
                logger.error(f"广播循环错误: {e}")
                time.sleep(10)

    def event_listener():
        """事件监听器"""
        if not REDIS_AVAILABLE:
            return

        pubsub = redis_client.pubsub()
        pubsub.subscribe("permission:events")

        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event_data = json.loads(message["data"])
                    socketio.emit("real_time_event", event_data)
                except Exception as e:
                    logger.error(f"处理事件失败: {e}")

    # 启动广播线程
    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast_thread.start()

    # 启动事件监听线程
    if REDIS_AVAILABLE:
        event_thread = threading.Thread(target=event_listener, daemon=True)
        event_thread.start()


# ==================== 启动函数 ====================


def start_control_plane(host="0.0.0.0", port=5001, debug=False):
    """启动控制平面"""
    try:
        # 启动后台任务
        start_background_tasks()

        logger.info(f"启动权限系统控制平面: http://{host}:{port}")
        socketio.run(app, host=host, port=port, debug=debug)
    except Exception as e:
        logger.error(f"启动控制平面失败: {e}")


if __name__ == "__main__":
    start_control_plane()
