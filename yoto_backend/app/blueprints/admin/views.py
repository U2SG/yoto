from flask import jsonify, current_app, send_from_directory, abort, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.core.permission.permissions_refactored import get_system_stats
from app.core.permission.permission_registry import (
    register_permission,
    list_registered_permissions,
)
from app.core.permission.permission_decorators import require_permission
from flasgger import swag_from
from app.core.extensions import db
from app.blueprints.auth.models import User
from . import admin_bp
from app.core.permission.permission_monitor import (
    get_health_status,
    get_performance_report,
    clear_alerts,
)
import logging

logger = logging.getLogger(__name__)


def _register_admin_permissions():
    """注册管理员权限 - 延迟初始化"""
    try:
        # 检查是否在Flask应用上下文中
        _ = current_app.name

        # 注册权限
        register_permission("admin.view_swagger", "admin", "查看API文档")
        register_permission("admin.view_health", "admin", "查看系统健康状态")
        register_permission("admin.manage_health", "admin", "管理系统健康状态")
    except RuntimeError:
        # 不在Flask上下文中，跳过权限注册
        pass


# 延迟注册权限
_register_admin_permissions()


@admin_bp.route("/admin/permissions", methods=["GET"])
def list_permissions():
    """
    管理后台：列出所有已注册权限及其分组、描述
    ---
    tags:
      - Admin
    responses:
      200:
        description: 权限列表
        schema:
          type: object
          properties:
            permissions:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  group:
                    type: string
                  description:
                    type: string
    """
    return jsonify(list_registered_permissions()), 200


@admin_bp.route("/admin/cache/stats", methods=["GET"])
def get_cache_statistics():
    """
    管理后台：获取权限缓存统计信息
    返回L1本地缓存和L2分布式缓存的统计信息
    ---
    tags:
      - Admin
    responses:
      200:
        description: 缓存统计信息
        schema:
          type: object
          properties:
            l1_cache:
              type: object
              properties:
                hits:
                  type: integer
                misses:
                  type: integer
                size:
                  type: integer
            l2_cache:
              type: object
              properties:
                connected:
                  type: boolean
                error:
                  type: string
    """
    stats = get_system_stats()
    return jsonify(stats), 200


@admin_bp.route("/admin/apidocs")
@jwt_required()
@require_permission("admin.view_swagger")
def protected_swagger_ui():
    """
    受保护的Swagger UI页面，仅超级管理员可访问
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: Swagger UI页面
      401:
        description: 未授权
      403:
        description: 权限不足或非超级管理员
    """
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not getattr(user, "is_super_admin", False):
        abort(403)
    # 直接重定向到Flasgger的静态UI页面
    return current_app.send_static_file("flasgger_ui/index.html")


@admin_bp.route("/health/permissions", methods=["GET"])
@jwt_required()
@require_permission("admin.view_health")
def get_permissions_health():
    """
    获取权限系统健康状态

    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: 权限系统健康状态
        schema:
          type: object
          properties:
            overall_status:
              type: string
              description: 整体状态 (healthy/warning/error)
            cache_status:
              type: string
              description: 缓存状态
            performance_status:
              type: string
              description: 性能状态
            error_status:
              type: string
              description: 错误状态
            resource_status:
              type: string
              description: 资源状态
            details:
              type: object
              description: 详细信息
      401:
        description: 未授权
      403:
        description: 权限不足
    """
    try:
        health_status = get_health_status()
        return {
            "overall_status": health_status.overall_status,
            "cache_status": health_status.cache_status,
            "performance_status": health_status.performance_status,
            "error_status": health_status.error_status,
            "resource_status": health_status.resource_status,
            "details": health_status.details,
        }, 200
    except Exception as e:
        logger.error(f"获取权限系统健康状态失败: {e}")
        return {"error": "获取健康状态失败"}, 500


@admin_bp.route("/health/permissions/report", methods=["GET"])
@jwt_required()
@require_permission("admin.view_health")
def get_permissions_performance_report():
    """
    获取权限系统性能报告

    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: 权限系统性能报告
        schema:
          type: object
          properties:
            summary:
              type: object
              description: 性能摘要
            metrics:
              type: object
              description: 详细指标
            alerts:
              type: array
              description: 活跃告警
            recommendations:
              type: array
              description: 优化建议
      401:
        description: 未授权
      403:
        description: 权限不足
    """
    try:
        report = get_performance_report()
        return report, 200
    except Exception as e:
        logger.error(f"获取权限系统性能报告失败: {e}")
        return {"error": "获取性能报告失败"}, 500


@admin_bp.route("/health/permissions/alerts", methods=["DELETE"])
@jwt_required()
@require_permission("admin.manage_health")
def clear_permissions_alerts():
    """
    清除权限系统告警

    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: metric
        in: query
        type: string
        required: false
        description: 指定要清除的指标告警，不传则清除所有告警
    responses:
      200:
        description: 告警清除成功
        schema:
          type: object
          properties:
            message:
              type: string
              description: 操作结果
      401:
        description: 未授权
      403:
        description: 权限不足
    """
    try:
        metric = request.args.get("metric")
        clear_alerts(metric)

        message = f"已清除{'指定指标' if metric else '所有'}的告警"
        return {"message": message}, 200
    except Exception as e:
        logger.error(f"清除权限系统告警失败: {e}")
        return {"error": "清除告警失败"}, 500
