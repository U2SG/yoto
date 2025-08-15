from app.core.extensions import db
from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from sqlalchemy.dialects.mysql import JSON


class Role(db.Model):
    """
    角色模型 - 使用SOTA的数据库设计模式
    支持角色继承、软删除、审计日志、性能优化
    """

    __tablename__ = "roles"

    # 主键和基础字段
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False, index=True)
    server_id = db.Column(db.Integer, nullable=False, index=True)

    # 角色继承支持
    parent_id = db.Column(
        db.Integer, db.ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )

    # 角色类型和优先级
    role_type = db.Column(
        db.Enum("system", "custom", "inherited"), default="custom", nullable=False
    )
    priority = db.Column(
        db.Integer, default=0, nullable=False
    )  # 优先级，数字越大优先级越高

    # 元数据和配置
    role_metadata = db.Column(JSON, nullable=True)  # 存储角色额外配置
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # 审计字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_by = db.Column(db.Integer, nullable=True)  # 创建者ID
    updated_by = db.Column(db.Integer, nullable=True)  # 更新者ID

    # 软删除
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    # 关系定义
    parent = db.relationship("Role", remote_side=[id], backref="children")
    user_roles = db.relationship(
        "UserRole", back_populates="role", cascade="all, delete-orphan"
    )
    role_permissions = db.relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )

    # 索引和约束
    __table_args__ = (
        Index("idx_roles_server_active", "server_id", "is_active"),
        Index("idx_roles_parent_active", "parent_id", "is_active"),
        CheckConstraint("priority >= 0", name="chk_role_priority_positive"),
    )


class UserRole(db.Model):
    """
    用户角色关系模型 - 支持时间范围、条件角色
    """

    __tablename__ = "user_roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    role_id = db.Column(
        db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    # 时间范围支持
    valid_from = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=True)  # NULL表示永久有效

    # 条件角色支持
    conditions = db.Column(JSON, nullable=True)  # 存储角色生效条件

    # 审计字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, nullable=True)  # 分配者ID

    # 关系定义
    role = db.relationship("Role", back_populates="user_roles")

    # 索引和约束
    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        Index("idx_user_roles_valid", "user_id", "valid_from", "valid_until"),
        Index("idx_user_roles_active", "user_id", "role_id", "valid_until"),
    )


class RolePermission(db.Model):
    """
    角色权限关系模型 - 支持权限表达式、条件权限
    """

    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_id = db.Column(
        db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    # 权限表达式支持
    expression = db.Column(db.Text, nullable=True)  # 存储复杂权限表达式
    conditions = db.Column(JSON, nullable=True)  # 存储权限生效条件

    # 权限范围
    scope_type = db.Column(
        db.Enum("global", "server", "channel", "resource"),
        default="global",
        nullable=False,
    )
    scope_id = db.Column(db.Integer, nullable=True)  # 作用域ID

    # 审计字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, nullable=True)

    # 关系定义
    role = db.relationship("Role", back_populates="role_permissions")
    permission = db.relationship("Permission", back_populates="role_permissions")

    # 索引和约束
    __table_args__ = (
        db.UniqueConstraint(
            "role_id",
            "permission_id",
            "scope_type",
            "scope_id",
            name="uq_role_permission_scope",
        ),
        Index("idx_role_permissions_scope", "role_id", "scope_type", "scope_id"),
    )


class Permission(db.Model):
    """
    权限模型 - 支持权限分组、版本控制、依赖关系
    """

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # 权限分组和分类
    group = db.Column(db.String(64), nullable=True, index=True)
    category = db.Column(db.String(64), nullable=True, index=True)
    description = db.Column(db.String(255), nullable=True)

    # 权限类型和级别
    permission_type = db.Column(
        db.Enum("read", "write", "delete", "admin", "custom"),
        default="read",
        nullable=False,
    )
    level = db.Column(db.Integer, default=1, nullable=False)  # 权限级别

    # 权限依赖和冲突
    dependencies = db.Column(JSON, nullable=True)  # 依赖的其他权限
    conflicts = db.Column(JSON, nullable=True)  # 冲突的权限

    # 版本控制
    version = db.Column(db.String(16), default="1.0", nullable=False)
    is_deprecated = db.Column(db.Boolean, default=False, nullable=False)

    # 元数据
    permission_metadata = db.Column(JSON, nullable=True)  # 存储权限额外信息

    # 审计字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系定义
    role_permissions = db.relationship("RolePermission", back_populates="permission")

    # 索引和约束
    __table_args__ = (
        Index("idx_permissions_group_category", "group", "category"),
        Index("idx_permissions_type_level", "permission_type", "level"),
        CheckConstraint("level >= 1", name="chk_permission_level_positive"),
    )


class PermissionAuditLog(db.Model):
    """
    权限审计日志 - 记录所有权限变更操作
    """

    __tablename__ = "permission_audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 操作信息
    operation = db.Column(
        db.Enum("create", "update", "delete", "assign", "revoke"), nullable=False
    )
    resource_type = db.Column(
        db.Enum("role", "permission", "user_role", "role_permission"), nullable=False
    )
    resource_id = db.Column(db.Integer, nullable=False)

    # 变更详情
    old_values = db.Column(JSON, nullable=True)  # 变更前的值
    new_values = db.Column(JSON, nullable=True)  # 变更后的值

    # 操作者信息
    operator_id = db.Column(db.Integer, nullable=False)
    operator_ip = db.Column(db.String(45), nullable=True)  # 支持IPv6
    user_agent = db.Column(db.String(500), nullable=True)

    # 时间戳
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # 索引
    __table_args__ = (
        Index("idx_audit_log_resource", "resource_type", "resource_id"),
        Index("idx_audit_log_operator", "operator_id", "created_at"),
        Index("idx_audit_log_operation", "operation", "created_at"),
    )


# 在文件末尾添加权限组相关的模型


class PermissionGroup(db.Model):
    """权限组模型"""

    __tablename__ = "permission_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    # 关系
    permissions = db.relationship(
        "Permission",
        secondary="group_to_permission_mappings",
        backref=db.backref("groups", lazy="dynamic"),
    )
    roles = db.relationship(
        "Role",
        secondary="role_to_group_mappings",
        backref=db.backref("permission_groups", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<PermissionGroup {self.name}>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "permissions_count": len(self.permissions),
            "roles_count": len(self.roles),
        }


class GroupToPermissionMapping(db.Model):
    """权限组到权限的映射模型"""

    __tablename__ = "group_to_permission_mappings"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("permission_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    # 关系
    group = db.relationship(
        "PermissionGroup", backref=db.backref("permission_mappings", lazy="dynamic")
    )
    permission = db.relationship(
        "Permission", backref=db.backref("group_mappings", lazy="dynamic")
    )

    __table_args__ = (
        db.UniqueConstraint("group_id", "permission_id", name="uq_group_permission"),
    )

    def __repr__(self):
        return f"<GroupToPermissionMapping {self.group_id}:{self.permission_id}>"


class RoleToGroupMapping(db.Model):
    """角色到权限组的映射模型"""

    __tablename__ = "role_to_group_mappings"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(
        db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("permission_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type = db.Column(db.String(50), nullable=True)
    scope_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    # 关系
    role = db.relationship("Role", backref=db.backref("group_mappings", lazy="dynamic"))
    group = db.relationship(
        "PermissionGroup", backref=db.backref("role_mappings", lazy="dynamic")
    )

    __table_args__ = (
        db.UniqueConstraint(
            "role_id", "group_id", "scope_type", "scope_id", name="uq_role_group_scope"
        ),
    )

    def __repr__(self):
        return f"<RoleToGroupMapping {self.role_id}:{self.group_id}>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "role_id": self.role_id,
            "group_id": self.group_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
