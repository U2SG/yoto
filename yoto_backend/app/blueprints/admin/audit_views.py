"""
权限审计管理接口 - 使用SOTA的API设计模式
提供权限审计日志的查询、分析和导出功能。
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.core.permission_audit import AuditQuery, PermissionAuditor
from app.core.permission.permission_decorators import require_permission
from datetime import datetime, timedelta
from typing import Optional
import json

from . import audit_bp


@audit_bp.route("/admin/audit/logs", methods=["GET"])
@jwt_required()
@require_permission("audit.view_logs", group="audit", description="查看审计日志")
def get_audit_logs():
    """
    获取审计日志列表
    ---
    description: |
      使用SOTA的API设计模式，支持分页、过滤、排序。

      查询参数:
        - page: 页码（默认1）
        - per_page: 每页数量（默认20，最大100）
        - resource_type: 资源类型过滤
        - operation: 操作类型过滤
        - operator_id: 操作者ID过滤
        - start_date: 开始日期（ISO格式）
        - end_date: 结束日期（ISO格式）
        - sort_by: 排序字段（created_at, operation, resource_type）
        - sort_order: 排序方向（asc, desc）
    tags:
      - Admin Audit
    security:
      - Bearer: []
    parameters:
      - in: query
        name: page
        type: integer
        description: 页码（默认1）
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量（最大100）
        example: 20
      - in: query
        name: resource_type
        type: string
        description: 资源类型过滤
        example: role
      - in: query
        name: operation
        type: string
        description: 操作类型过滤
        example: create
      - in: query
        name: operator_id
        type: integer
        description: 操作者ID过滤
        example: 1
      - in: query
        name: start_date
        type: string
        description: 开始日期（ISO格式）
        example: 2024-01-01T00:00:00Z
      - in: query
        name: end_date
        type: string
        description: 结束日期（ISO格式）
        example: 2024-12-31T23:59:59Z
      - in: query
        name: sort_by
        type: string
        description: 排序字段
        enum: [created_at, operation, resource_type]
        example: created_at
      - in: query
        name: sort_order
        type: string
        description: 排序方向
        enum: [asc, desc]
        example: desc
    responses:
      200:
        description: 审计日志列表
        schema:
          type: object
          properties:
            logs:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  operation:
                    type: string
                  resource_type:
                    type: string
                  resource_id:
                    type: integer
                  operator_id:
                    type: integer
                  details:
                    type: object
                  created_at:
                    type: string
                    format: date-time
            pagination:
              type: object
              properties:
                page:
                  type: integer
                per_page:
                  type: integer
                total:
                  type: integer
                pages:
                  type: integer
      400:
        description: 参数错误
      401:
        description: 未授权
      403:
        description: 权限不足
    """
    # 获取查询参数
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    resource_type = request.args.get("resource_type")
    operation = request.args.get("operation")
    operator_id = request.args.get("operator_id", type=int)
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")

    # 解析日期
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的开始日期格式"}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的结束日期格式"}), 400

    # 构建查询
    from app.blueprints.roles.models import PermissionAuditLog

    query = PermissionAuditLog.query

    # 应用过滤条件
    if resource_type:
        query = query.filter(PermissionAuditLog.resource_type == resource_type)
    if operation:
        query = query.filter(PermissionAuditLog.operation == operation)
    if operator_id:
        query = query.filter(PermissionAuditLog.operator_id == operator_id)
    if start_date:
        query = query.filter(PermissionAuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(PermissionAuditLog.created_at <= end_date)

    # 应用排序
    if sort_by == "created_at":
        if sort_order == "asc":
            query = query.order_by(PermissionAuditLog.created_at.asc())
        else:
            query = query.order_by(PermissionAuditLog.created_at.desc())
    elif sort_by == "operation":
        if sort_order == "asc":
            query = query.order_by(PermissionAuditLog.operation.asc())
        else:
            query = query.order_by(PermissionAuditLog.operation.desc())
    elif sort_by == "resource_type":
        if sort_order == "asc":
            query = query.order_by(PermissionAuditLog.resource_type.asc())
        else:
            query = query.order_by(PermissionAuditLog.resource_type.desc())

    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 格式化结果
    logs = []
    for log in pagination.items:
        logs.append(
            {
                "id": log.id,
                "operation": log.operation,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "operator_id": log.operator_id,
                "operator_ip": log.operator_ip,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    return (
        jsonify(
            {
                "logs": logs,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        ),
        200,
    )


@audit_bp.route("/admin/audit/users/<int:user_id>/trail", methods=["GET"])
@jwt_required()
@require_permission(
    "audit.view_user_trail", group="audit", description="查看用户审计轨迹"
)
def get_user_audit_trail(user_id: int):
    """
    获取用户审计轨迹。

    使用SOTA的查询优化技术，支持时间范围过滤。
    """
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    # 解析日期
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的开始日期格式"}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的结束日期格式"}), 400

    # 获取审计轨迹
    logs = AuditQuery.get_user_audit_trail(user_id, start_date, end_date)

    # 格式化结果
    trail = []
    for log in logs:
        trail.append(
            {
                "id": log.id,
                "operation": log.operation,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "operator_ip": log.operator_ip,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    return (
        jsonify({"user_id": user_id, "trail": trail, "total_operations": len(trail)}),
        200,
    )


@audit_bp.route(
    "/admin/audit/resources/<resource_type>/<int:resource_id>/trail", methods=["GET"]
)
@jwt_required()
@require_permission(
    "audit.view_resource_trail", group="audit", description="查看资源审计轨迹"
)
def get_resource_audit_trail(resource_type: str, resource_id: int):
    """
    获取资源审计轨迹。
    """
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    # 解析日期
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的开始日期格式"}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的结束日期格式"}), 400

    # 获取审计轨迹
    logs = AuditQuery.get_resource_audit_trail(
        resource_type, resource_id, start_date, end_date
    )

    # 格式化结果
    trail = []
    for log in logs:
        trail.append(
            {
                "id": log.id,
                "operation": log.operation,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "operator_id": log.operator_id,
                "operator_ip": log.operator_ip,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    return (
        jsonify(
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "trail": trail,
                "total_operations": len(trail),
            }
        ),
        200,
    )


@audit_bp.route("/admin/audit/summary", methods=["GET"])
@jwt_required()
@require_permission("audit.view_summary", group="audit", description="查看审计摘要")
def get_audit_summary():
    """
    获取审计摘要统计。

    使用SOTA的聚合查询技术，支持实时统计和分析。
    """
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    # 解析日期
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的开始日期格式"}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "无效的结束日期格式"}), 400

    # 获取摘要统计
    summary = AuditQuery.get_operation_summary(start_date, end_date)

    # 格式化结果
    stats = []
    for item in summary:
        stats.append(
            {
                "operation": item.operation,
                "resource_type": item.resource_type,
                "count": item.count,
            }
        )

    return (
        jsonify(
            {
                "summary": stats,
                "total_operations": sum(item.count for item in summary),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
            }
        ),
        200,
    )


@audit_bp.route("/admin/audit/export", methods=["POST"])
@jwt_required()
@require_permission("audit.export_logs", group="audit", description="导出审计日志")
def export_audit_logs():
    """
    导出审计日志。

    使用SOTA的数据导出技术，支持多种格式和批量处理。
    """
    data = request.get_json() or {}
    export_format = data.get("format", "json")  # json, csv
    filters = data.get("filters", {})

    # 构建查询条件
    from app.blueprints.roles.models import PermissionAuditLog

    query = PermissionAuditLog.query

    # 应用过滤条件
    if filters.get("resource_type"):
        query = query.filter(
            PermissionAuditLog.resource_type == filters["resource_type"]
        )
    if filters.get("operation"):
        query = query.filter(PermissionAuditLog.operation == filters["operation"])
    if filters.get("operator_id"):
        query = query.filter(PermissionAuditLog.operator_id == filters["operator_id"])
    if filters.get("start_date"):
        try:
            start_date = datetime.fromisoformat(
                filters["start_date"].replace("Z", "+00:00")
            )
            query = query.filter(PermissionAuditLog.created_at >= start_date)
        except ValueError:
            return jsonify({"error": "无效的开始日期格式"}), 400
    if filters.get("end_date"):
        try:
            end_date = datetime.fromisoformat(
                filters["end_date"].replace("Z", "+00:00")
            )
            query = query.filter(PermissionAuditLog.created_at <= end_date)
        except ValueError:
            return jsonify({"error": "无效的结束日期格式"}), 400

    # 限制导出数量
    limit = min(filters.get("limit", 1000), 10000)
    logs = query.limit(limit).all()

    # 格式化数据
    export_data = []
    for log in logs:
        export_data.append(
            {
                "id": log.id,
                "operation": log.operation,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "operator_id": log.operator_id,
                "operator_ip": log.operator_ip,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    if export_format == "csv":
        # 这里可以实现CSV导出逻辑
        return jsonify({"error": "CSV导出功能待实现"}), 501

    return (
        jsonify(
            {
                "format": export_format,
                "total_records": len(export_data),
                "data": export_data,
                "exported_at": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )
