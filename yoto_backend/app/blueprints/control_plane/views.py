"""
控制平面API路由

提供权限系统的运维管理接口
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
from flask import (
    Blueprint,
    jsonify,
    request,
    current_app,
    render_template,
    session,
    redirect,
    url_for,
    flash,
)
from flask_socketio import emit
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from . import control_plane_bp

# 导入权限系统模块
from app.core.permission.permissions_refactored import (
    get_permission_system,
    get_resilience_controller,
    is_maintenance_mode_enabled,
    set_maintenance_mode,
)
from app.core.permission.permission_monitor import get_permission_monitor
from app.core.permission.hybrid_permission_cache import get_hybrid_cache
from app.core.permission.permission_resilience import (
    get_circuit_breaker_state,
    get_rate_limit_status,
    set_circuit_breaker_config,
    set_rate_limit_config,
)
from app.blueprints.auth.models import User

logger = logging.getLogger(__name__)

# ==================== 登录路由 ====================


@control_plane_bp.route("/login", methods=["GET", "POST"])
def login():
    """控制平面登录页面"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("请输入用户名和密码", "error")
            return render_template("control_plane/login.html")

        # 查找用户
        user = User.query.filter_by(username=username).first()

        if (
            user
            and check_password_hash(user.password_hash, password)
            and user.is_super_admin
        ):
            # 创建JWT token
            token = create_access_token(
                identity=str(user.id),
                additional_claims={
                    "username": user.username,
                    "is_super_admin": user.is_super_admin,
                    "user_id": user.id,
                },
            )

            # 存储到session
            session["admin_token"] = token
            session["admin_user_id"] = user.id
            session["admin_username"] = user.username

            flash(f"欢迎回来，{user.username}！", "success")
            return redirect(url_for("control_plane.dashboard"))
        else:
            flash("用户名或密码错误，或者您没有管理员权限", "error")
            return render_template("control_plane/login.html")

    return render_template("control_plane/login.html")


@control_plane_bp.route("/logout")
def logout():
    """退出登录"""
    session.pop("admin_token", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    flash("已退出登录", "info")
    return redirect(url_for("control_plane.login"))


# ==================== 页面路由 ====================

from app.core.permission.permission_decorators import require_permission


@control_plane_bp.route("/")
def dashboard():
    """主仪表盘页面"""
    # 检查是否已登录
    if "admin_token" not in session:
        return redirect(url_for("control_plane.login"))

    return render_template("control_plane/dashboard.html")


# ==================== 系统状态API ====================


@control_plane_bp.route("/api/status", methods=["GET"])
def get_system_status():
    """获取系统整体状态"""
    try:
        # 获取基本系统状态
        perm_system = get_permission_system()
        status = perm_system.get_system_stats()

        # 添加维护模式状态
        maintenance_mode = is_maintenance_mode_enabled()

        # 组装响应
        response = {
            "success": True,
            "system_status": {
                "overall_health": status["health"]["overall_status"],
                "maintenance_mode": {
                    "enabled": maintenance_mode,
                    "status": "active" if maintenance_mode else "inactive",
                },
                "cache_status": status["health"]["cache_status"],
                "performance_status": status["health"]["performance_status"],
                "error_status": status["health"]["error_status"],
                "alerts_count": status["health"]["alerts_count"],
                "cache_hit_rate": status["cache"].get("hit_rate", 0),
                "cache_size": status["cache"].get("total_entries", 0),
                "invalidation_queue": status["invalidation"].get("queue_size", 0),
                "pending_operations": status["invalidation"].get(
                    "pending_operations", 0
                ),
            },
            "timestamp": time.time(),
        }

        return jsonify(response)
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@control_plane_bp.route("/api/status/detailed", methods=["GET"])
def get_detailed_status():
    """获取详细的系统状态信息"""
    try:
        permission_system = get_permission_system()

        # 获取系统统计信息
        system_stats = permission_system.get_system_stats()

        # 获取优化建议
        optimization_suggestions = permission_system.get_optimization_suggestions()

        # 获取韧性统计
        resilience_stats = get_resilience_stats()

        return jsonify(
            {
                "system_stats": system_stats,
                "optimization_suggestions": optimization_suggestions,
                "resilience_stats": resilience_stats,
                "timestamp": time.time(),
            }
        )
    except Exception as e:
        logger.error(f"获取详细状态失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 配置管理API ====================


@control_plane_bp.route("/api/config/circuit_breaker/<name>", methods=["GET", "PUT"])
def circuit_breaker_config(name):
    """熔断器配置管理"""
    try:
        if request.method == "GET":
            # 获取熔断器状态
            state = get_circuit_breaker_state(name)
            return jsonify(state)
        else:
            # 更新熔断器配置
            data = request.get_json()
            success = set_circuit_breaker_config(name, **data)
            return jsonify({"success": success})
    except Exception as e:
        logger.error(f"熔断器配置操作失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/config/rate_limiter/<name>", methods=["GET", "PUT"])
def rate_limiter_config(name):
    """限流器配置管理"""
    try:
        if request.method == "GET":
            # 获取限流器状态
            status = get_rate_limit_status(name)
            return jsonify(status)
        else:
            # 更新限流器配置
            data = request.get_json()
            success = set_rate_limit_config(name, **data)
            return jsonify({"success": success})
    except Exception as e:
        logger.error(f"限流器配置操作失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/config/cache", methods=["GET", "PUT"])
def cache_config():
    """缓存配置管理"""
    try:
        hybrid_cache = get_hybrid_cache()

        if request.method == "GET":
            # 获取缓存配置
            stats = hybrid_cache.get_stats()
            return jsonify(stats)
        else:
            # 更新缓存配置（这里可以添加缓存配置更新逻辑）
            return jsonify({"success": True, "message": "缓存配置更新功能待实现"})
    except Exception as e:
        logger.error(f"缓存配置操作失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 性能监控API ====================


@control_plane_bp.route("/api/stats/performance", methods=["GET"])
def get_performance_stats():
    """获取性能统计信息"""
    try:
        permission_system = get_permission_system()

        # 获取系统统计
        system_stats = permission_system.get_system_stats()

        # 获取缓存统计
        cache_stats = get_cache_stats()

        # 获取监控统计
        monitor_stats = get_monitor_stats()

        return jsonify(
            {
                "system_stats": system_stats,
                "cache_stats": cache_stats,
                "monitor_stats": monitor_stats,
                "timestamp": time.time(),
            }
        )
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/stats/cache", methods=["GET"])
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        hybrid_cache = get_hybrid_cache()
        stats = hybrid_cache.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/stats/monitor", methods=["GET"])
def get_monitor_stats():
    """获取监控统计信息"""
    try:
        monitor = get_permission_monitor()
        if monitor:
            stats = monitor.get_stats()
            return jsonify(stats)
        else:
            return jsonify({"error": "监控器不可用"}), 503
    except Exception as e:
        logger.error(f"获取监控统计失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 事件管理API ====================


@control_plane_bp.route("/api/events/recent", methods=["GET"])
def get_recent_events():
    """获取最近的事件"""
    try:
        monitor = get_permission_monitor()
        if monitor:
            events = monitor.get_events_summary()
            return jsonify(events)
        else:
            return jsonify({"events": [], "message": "监控器不可用"})
    except Exception as e:
        logger.error(f"获取最近事件失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/events/clear", methods=["POST"])
def clear_events():
    """清除事件历史"""
    try:
        monitor = get_permission_monitor()
        if monitor:
            monitor.clear_alerts()
            return jsonify({"success": True, "message": "事件已清除"})
        else:
            return jsonify({"error": "监控器不可用"}), 503
    except Exception as e:
        logger.error(f"清除事件失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 维护操作API ====================


@control_plane_bp.route("/api/maintenance/warmup", methods=["POST"])
def trigger_warmup():
    """触发系统预热"""
    try:
        permission_system = get_permission_system()
        result = permission_system.warm_up()
        return jsonify(result)
    except Exception as e:
        logger.error(f"触发预热失败: {e}")
        return jsonify({"error": str(e)}), 500


@control_plane_bp.route("/api/maintenance/refresh", methods=["POST"])
def trigger_refresh():
    """触发缓存刷新"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if user_id:
            permission_system = get_permission_system()
            result = permission_system.refresh_user_permissions(user_id, force=True)
            return jsonify(result)
        else:
            return jsonify({"error": "需要提供user_id参数"}), 400
    except Exception as e:
        logger.error(f"触发刷新失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 维护模式API ====================


@control_plane_bp.route("/api/maintenance/mode", methods=["GET"])
def get_maintenance_mode():
    """获取维护模式状态"""
    try:
        enabled = is_maintenance_mode_enabled()
        return jsonify(
            {
                "success": True,
                "maintenance_mode": enabled,
                "status": "active" if enabled else "inactive",
                "timestamp": time.time(),
            }
        )
    except Exception as e:
        logger.error(f"获取维护模式状态失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@control_plane_bp.route("/api/maintenance/mode", methods=["PUT"])
@jwt_required()
def update_maintenance_mode():
    """更新维护模式状态"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "enabled" not in data:
            return jsonify({"success": False, "error": "缺少参数: enabled"}), 400

        enabled = bool(data.get("enabled"))
        reason = data.get("reason", "无")

        # 获取操作者信息
        user_id = get_jwt_identity()
        username = request.get_jwt_identity().get("username", "未知用户")

        # 设置维护模式
        success = set_maintenance_mode(enabled)

        if success:
            status = "开启" if enabled else "关闭"
            logger.warning(f"维护模式已{status}, 操作者: {username}, 原因: {reason}")

            # 广播通知
            emit(
                "maintenance_mode_change",
                {
                    "enabled": enabled,
                    "status": "active" if enabled else "inactive",
                    "changed_by": username,
                    "reason": reason,
                    "timestamp": time.time(),
                },
                namespace="/events",
                broadcast=True,
            )

            return jsonify(
                {
                    "success": True,
                    "maintenance_mode": enabled,
                    "status": "active" if enabled else "inactive",
                    "message": f"维护模式已{status}",
                }
            )
        else:
            return jsonify({"success": False, "error": "设置维护模式失败"}), 500
    except Exception as e:
        logger.error(f"更新维护模式状态失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 辅助函数 ====================


def get_resilience_stats() -> Dict[str, Any]:
    """获取韧性系统统计"""
    try:
        controller = get_resilience_controller()
        if controller:
            return {
                "status": "healthy",
                "controller_available": True,
                "configs": controller.get_all_configs(),
            }
        else:
            return {
                "status": "error",
                "controller_available": False,
                "error": "韧性控制器不可用",
            }
    except Exception as e:
        return {"status": "error", "controller_available": False, "error": str(e)}


# 导入时间模块
import time
