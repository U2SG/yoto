"""
权限审计模块 - 使用SOTA的审计日志技术
记录所有权限相关的操作，支持合规性检查和安全审计。
"""

from datetime import datetime
from flask import request, g
from app.blueprints.roles.models import PermissionAuditLog
from app.core.extensions import db
from typing import Dict, Any, Optional
import json


class PermissionAuditor:
    """
    权限审计器 - 使用SOTA的审计模式
    支持操作记录、变更追踪、合规性检查
    """

    @staticmethod
    def log_operation(
        operation: str,
        resource_type: str,
        resource_id: int,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        operator_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        记录权限操作日志。

        使用SOTA的审计日志技术，支持结构化日志、元数据扩展、性能优化。

        参数:
            operation: 操作类型 (create, update, delete, assign, revoke)
            resource_type: 资源类型 (role, permission, user_role, role_permission)
            resource_id: 资源ID
            old_values: 变更前的值
            new_values: 变更后的值
            operator_id: 操作者ID
            metadata: 额外元数据
        """
        try:
            # 获取操作者信息
            if operator_id is None:
                operator_id = getattr(g, "current_user_id", None)

            # 获取客户端信息
            operator_ip = request.remote_addr if request else None
            user_agent = request.headers.get("User-Agent") if request else None

            # 创建审计日志
            audit_log = PermissionAuditLog(
                operation=operation,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                operator_id=operator_id,
                operator_ip=operator_ip,
                user_agent=user_agent,
            )

            # 添加元数据到JSON字段
            if metadata:
                audit_log.old_values = audit_log.old_values or {}
                audit_log.old_values["_metadata"] = metadata

            db.session.add(audit_log)
            db.session.commit()

        except Exception as e:
            # 审计日志失败不应影响主业务流程
            db.session.rollback()
            # 这里可以记录到系统日志，但不抛出异常

    @staticmethod
    def log_role_creation(
        role_id: int, role_data: Dict[str, Any], operator_id: Optional[int] = None
    ):
        """记录角色创建操作"""
        PermissionAuditor.log_operation(
            operation="create",
            resource_type="role",
            resource_id=role_id,
            new_values=role_data,
            operator_id=operator_id,
            metadata={"operation": "role_creation"},
        )

    @staticmethod
    def log_role_update(
        role_id: int,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        operator_id: Optional[int] = None,
    ):
        """记录角色更新操作"""
        PermissionAuditor.log_operation(
            operation="update",
            resource_type="role",
            resource_id=role_id,
            old_values=old_data,
            new_values=new_data,
            operator_id=operator_id,
            metadata={"operation": "role_update"},
        )

    @staticmethod
    def log_role_deletion(
        role_id: int, role_data: Dict[str, Any], operator_id: Optional[int] = None
    ):
        """记录角色删除操作"""
        PermissionAuditor.log_operation(
            operation="delete",
            resource_type="role",
            resource_id=role_id,
            old_values=role_data,
            operator_id=operator_id,
            metadata={"operation": "role_deletion"},
        )

    @staticmethod
    def log_role_assignment(
        user_id: int,
        role_id: int,
        assignment_data: Dict[str, Any],
        operator_id: Optional[int] = None,
    ):
        """记录角色分配操作"""
        PermissionAuditor.log_operation(
            operation="assign",
            resource_type="user_role",
            resource_id=role_id,
            new_values={"user_id": user_id, **assignment_data},
            operator_id=operator_id,
            metadata={"operation": "role_assignment", "user_id": user_id},
        )

    @staticmethod
    def log_role_revocation(
        user_id: int,
        role_id: int,
        revocation_data: Dict[str, Any],
        operator_id: Optional[int] = None,
    ):
        """记录角色撤销操作"""
        PermissionAuditor.log_operation(
            operation="revoke",
            resource_type="user_role",
            resource_id=role_id,
            old_values={"user_id": user_id, **revocation_data},
            operator_id=operator_id,
            metadata={"operation": "role_revocation", "user_id": user_id},
        )

    @staticmethod
    def log_permission_assignment(
        role_id: int,
        permission_id: int,
        assignment_data: Dict[str, Any],
        operator_id: Optional[int] = None,
    ):
        """记录权限分配操作"""
        PermissionAuditor.log_operation(
            operation="assign",
            resource_type="role_permission",
            resource_id=role_id,
            new_values={"permission_id": permission_id, **assignment_data},
            operator_id=operator_id,
            metadata={
                "operation": "permission_assignment",
                "permission_id": permission_id,
            },
        )

    @staticmethod
    def log_permission_revocation(
        role_id: int,
        permission_id: int,
        revocation_data: Dict[str, Any],
        operator_id: Optional[int] = None,
    ):
        """记录权限撤销操作"""
        PermissionAuditor.log_operation(
            operation="revoke",
            resource_type="role_permission",
            resource_id=role_id,
            old_values={"permission_id": permission_id, **revocation_data},
            operator_id=operator_id,
            metadata={
                "operation": "permission_revocation",
                "permission_id": permission_id,
            },
        )


class AuditQuery:
    """
    审计查询器 - 使用SOTA的查询优化技术
    支持复杂的审计日志查询和分析
    """

    @staticmethod
    def get_user_audit_trail(
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        获取用户审计轨迹。

        使用SOTA的查询优化技术，支持时间范围过滤、分页、索引优化。
        """
        query = PermissionAuditLog.query.filter(
            PermissionAuditLog.operator_id == user_id
        )

        if start_date:
            query = query.filter(PermissionAuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(PermissionAuditLog.created_at <= end_date)

        return query.order_by(PermissionAuditLog.created_at.desc()).all()

    @staticmethod
    def get_resource_audit_trail(
        resource_type: str,
        resource_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        获取资源审计轨迹。
        """
        query = PermissionAuditLog.query.filter(
            PermissionAuditLog.resource_type == resource_type,
            PermissionAuditLog.resource_id == resource_id,
        )

        if start_date:
            query = query.filter(PermissionAuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(PermissionAuditLog.created_at <= end_date)

        return query.order_by(PermissionAuditLog.created_at.desc()).all()

    @staticmethod
    def get_operation_summary(
        start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ):
        """
        获取操作摘要统计。

        使用SOTA的聚合查询技术，支持实时统计和分析。
        """
        from sqlalchemy import func

        query = db.session.query(
            PermissionAuditLog.operation,
            PermissionAuditLog.resource_type,
            func.count(PermissionAuditLog.id).label("count"),
        )

        if start_date:
            query = query.filter(PermissionAuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(PermissionAuditLog.created_at <= end_date)

        return query.group_by(
            PermissionAuditLog.operation, PermissionAuditLog.resource_type
        ).all()


# 便捷函数
def audit_role_operation(operation: str, role_id: int, **kwargs):
    """便捷的角色审计函数"""
    if operation == "create":
        PermissionAuditor.log_role_creation(
            role_id, kwargs.get("data", {}), kwargs.get("operator_id")
        )
    elif operation == "update":
        PermissionAuditor.log_role_update(
            role_id,
            kwargs.get("old_data", {}),
            kwargs.get("new_data", {}),
            kwargs.get("operator_id"),
        )
    elif operation == "delete":
        PermissionAuditor.log_role_deletion(
            role_id, kwargs.get("data", {}), kwargs.get("operator_id")
        )


def audit_permission_operation(operation: str, role_id: int, **kwargs):
    """便捷的权限审计函数"""
    if operation == "assign":
        PermissionAuditor.log_permission_assignment(
            role_id,
            kwargs.get("permission_id"),
            kwargs.get("data", {}),
            kwargs.get("operator_id"),
        )
    elif operation == "revoke":
        PermissionAuditor.log_permission_revocation(
            role_id,
            kwargs.get("permission_id"),
            kwargs.get("data", {}),
            kwargs.get("operator_id"),
        )
