from . import roles_bp
from flask import request, jsonify
from flask_jwt_extended import jwt_required
from app.core.extensions import db
from .models import Role, UserRole, RolePermission
from app.core.pydantic_schemas import RoleSchema


# 示例路由，后续实现
@roles_bp.route("/roles", methods=["GET"])
def list_roles():
    """
    查询角色列表
    ---
    description: |
      查询角色列表，支持 server_id 查询参数，返回指定星球下的所有角色。不传 server_id 时返回全部角色。
    tags:
      - Roles
    parameters:
      - in: query
        name: server_id
        type: integer
        description: 星球ID，不传则返回全部角色
        example: 1
    responses:
      200:
        description: 角色列表
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              server_id:
                type: integer
    """
    server_id = request.args.get("server_id", type=int)
    query = Role.query
    if server_id:
        query = query.filter_by(server_id=server_id)
    roles = [RoleSchema.from_orm(r).dict() for r in query.all()]
    return jsonify(roles), 200


@roles_bp.route("/roles/<int:role_id>", methods=["GET"])
def get_role(role_id):
    """
    查询角色详情
    ---
    tags:
      - Roles
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
    responses:
      200:
        description: 角色详情
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            server_id:
              type: integer
      404:
        description: 角色不存在
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    return jsonify(RoleSchema.from_orm(role).dict()), 200


@roles_bp.route("/roles", methods=["POST"])
@jwt_required()
def create_role():
    """
    创建角色
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - server_id
          properties:
            name:
              type: string
              example: moderator
            server_id:
              type: integer
              example: 1
    responses:
      201:
        description: 角色创建成功
        schema:
          type: object
          properties:
            message:
              type: string
            role:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                server_id:
                  type: integer
      400:
        description: 参数错误
      401:
        description: 未授权
    """
    data = request.get_json() or {}
    name = data.get("name")
    server_id = data.get("server_id")
    if not name or not server_id:
        return jsonify({"error": "角色名称和server_id必填"}), 400
    role = Role(name=name, server_id=server_id)
    db.session.add(role)
    db.session.commit()
    return (
        jsonify({"message": "角色创建成功", "role": RoleSchema.from_orm(role).dict()}),
        201,
    )


@roles_bp.route("/roles/<int:role_id>", methods=["DELETE"])
@jwt_required()
def delete_role(role_id):
    """
    删除角色
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
    responses:
      200:
        description: 角色删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 角色不存在
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    db.session.delete(role)
    db.session.commit()
    return jsonify({"message": "角色已删除"}), 200


@roles_bp.route("/roles/<int:role_id>", methods=["PATCH"])
@jwt_required()
def update_role(role_id):
    """
    更新角色名称
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: new_role_name
    responses:
      200:
        description: 角色更新成功
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            server_id:
              type: integer
      401:
        description: 未授权
      404:
        description: 角色不存在
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    data = request.get_json() or {}
    name = data.get("name")
    if name:
        role.name = name
        db.session.commit()
    return jsonify(RoleSchema.from_orm(role).dict()), 200


# 新增RESTful路由：分配角色给用户
@roles_bp.route("/roles/<int:role_id>/users", methods=["POST"])
@jwt_required()
def assign_role_restful(role_id):
    """
    分配角色给用户（RESTful补充，推荐使用）
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: integer
              example: 1
    responses:
      201:
        description: 角色分配成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 角色不存在
      409:
        description: 角色已分配
    """
    return assign_role(role_id)


# 新增RESTful路由：移除角色
@roles_bp.route("/roles/<int:role_id>/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def remove_role_restful(role_id, user_id):
    """
    移除角色（RESTful补充，推荐使用）
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 2
    responses:
      200:
        description: 角色已移除
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 未分配该角色
    """
    # 复用原有逻辑
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    user_role = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
    if not user_role:
        return jsonify({"error": "未分配该角色"}), 404
    db.session.delete(user_role)
    db.session.commit()
    from app.core.permissions import (
        invalidate_user_permissions,
        refresh_user_permissions,
    )

    invalidate_user_permissions(user_id)
    refresh_user_permissions(user_id, role.server_id)
    return jsonify({"message": "角色已移除"}), 200


# 原有接口加注释：建议使用新RESTful接口
@roles_bp.route("/roles/<int:role_id>/assign", methods=["POST"])
@jwt_required()
def assign_role(role_id):
    """
    分配角色给用户（已废弃，建议使用POST /roles/<role_id>/users）
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: integer
              example: 1
    responses:
      200:
        description: 角色分配成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 角色不存在
      409:
        description: 角色已分配
    """
    data = request.get_json() or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id 必填"}), 400
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    exists = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
    if exists:
        return jsonify({"error": "已分配该角色"}), 409
    db.session.add(UserRole(user_id=user_id, role_id=role_id))
    db.session.commit()
    from app.core.permissions import (
        invalidate_user_permissions,
        refresh_user_permissions,
    )

    invalidate_user_permissions(user_id)
    refresh_user_permissions(user_id, role.server_id)
    return jsonify({"message": "角色分配成功"}), 201


@roles_bp.route("/roles/<int:role_id>/remove", methods=["POST"])
@jwt_required()
def remove_role(role_id):
    """
    移除角色（已废弃，建议使用DELETE /roles/<role_id>/users/<user_id>）
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: integer
              example: 1
    responses:
      200:
        description: 角色已移除
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 未分配该角色
    """
    data = request.get_json() or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id 必填"}), 400
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    user_role = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
    if not user_role:
        return jsonify({"error": "未分配该角色"}), 404
    db.session.delete(user_role)
    db.session.commit()
    from app.core.permissions import (
        invalidate_user_permissions,
        refresh_user_permissions,
    )

    invalidate_user_permissions(user_id)
    refresh_user_permissions(user_id, role.server_id)
    return jsonify({"message": "角色已移除"}), 200


@roles_bp.route("/roles/<int:role_id>/permissions", methods=["POST"])
@jwt_required()
def assign_permission(role_id):
    """
    分配权限。
    仅允许已登录用户为角色分配权限（permission参数，字符串）。
    已分配则返回 409。
    """
    data = request.get_json() or {}
    permission = data.get("permission")
    if not permission:
        return jsonify({"error": "permission 必填"}), 400
    # 检查角色是否存在
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    # 检查是否已分配
    exists = RolePermission.query.filter_by(
        role_id=role_id, permission=permission
    ).first()
    if exists:
        return jsonify({"error": "已分配该权限"}), 409
    db.session.add(RolePermission(role_id=role_id, permission=permission))
    db.session.commit()
    # 失效角色相关权限缓存
    from app.core.permissions import invalidate_role_permissions

    invalidate_role_permissions(role_id)
    return jsonify({"message": "权限分配成功"}), 201


@roles_bp.route("/roles/<int:role_id>/permissions", methods=["GET"])
def list_role_permissions(role_id):
    """
    查询指定角色拥有的所有权限。
    返回字符串列表。
    角色不存在时返回 404。
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "角色不存在"}), 404
    permissions = [
        rp.permission for rp in RolePermission.query.filter_by(role_id=role_id).all()
    ]
    return jsonify(permissions), 200


@roles_bp.route("/roles/<int:role_id>/permissions/remove", methods=["POST"])
@jwt_required()
def remove_permission(role_id):
    """
    移除角色权限（已废弃，建议使用DELETE /roles/<role_id>/permissions/<permission>）
    ---
    tags:
      - Roles
    security:
      - Bearer: []
    parameters:
      - in: path
        name: role_id
        type: integer
        required: true
        description: 角色ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - permission
          properties:
            permission:
              type: string
              example: admin.view
    responses:
      200:
        description: 权限已移除
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 未分配该权限
    """
    data = request.get_json() or {}
    permission = data.get("permission")
    if not permission:
        return jsonify({"error": "permission 必填"}), 400
    rp = RolePermission.query.filter_by(role_id=role_id, permission=permission).first()
    if not rp:
        return jsonify({"error": "未分配该权限"}), 404
    db.session.delete(rp)
    db.session.commit()
    from app.core.permissions import invalidate_role_permissions

    invalidate_role_permissions(role_id)
    return jsonify({"message": "权限已移除"}), 200


@roles_bp.route("/users/<int:user_id>/roles", methods=["GET"])
def list_user_roles(user_id):
    """
    查询指定用户拥有的所有角色。
    返回 Pydantic RoleSchema 列表。
    用户无角色时返回空列表。
    """
    role_ids = [ur.role_id for ur in UserRole.query.filter_by(user_id=user_id).all()]
    roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
    return jsonify([RoleSchema.from_orm(r).dict() for r in roles]), 200


@roles_bp.route("/users/<int:user_id>/permissions", methods=["GET"])
def list_user_permissions(user_id):
    """
    查询指定用户拥有的所有权限（聚合其所有角色的权限，去重）。
    返回字符串列表。
    用户无权限时返回空列表。
    """
    role_ids = [ur.role_id for ur in UserRole.query.filter_by(user_id=user_id).all()]
    if not role_ids:
        return jsonify([]), 200
    perms = set()
    for rp in RolePermission.query.filter(RolePermission.role_id.in_(role_ids)).all():
        perms.add(rp.permission)
    return jsonify(list(perms)), 200
