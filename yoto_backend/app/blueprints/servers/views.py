from . import servers_bp
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.core.extensions import db
from app.core.pydantic_schemas import UserSchema, ServerSchema
from .models import Server, ServerMember
from app.blueprints.auth.models import User
from app.core.permission.permission_decorators import require_permission
from app.blueprints.roles.models import Role, UserRole

# 导入新的权限工具（仅用于内部使用，不改变现有接口）
from app.core.permission.permission_factories import (
    create_crud_permissions,
    register_crud_permissions,
)

# 注册服务器相关权限（内部使用，不影响现有接口）
SERVER_PERMISSIONS = create_crud_permissions("server", group="server")


def _register_server_permissions():
    """注册服务器相关权限 - 延迟初始化"""
    try:
        from flask import current_app

        # 检查是否在Flask应用上下文中
        _ = current_app.name

        register_crud_permissions(
            "server", group="server", description="服务器管理权限"
        )
    except RuntimeError:
        # 不在Flask上下文中，跳过权限注册
        pass


# 延迟注册权限
_register_server_permissions()


@servers_bp.route("/servers", methods=["POST"])
@jwt_required()
def create_server():
    """
    创建星球
    ---
    tags:
      - Servers
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
          properties:
            name:
              type: string
              example: 我的星球
    responses:
      201:
        description: 星球创建成功
        schema:
          type: object
          properties:
            message:
              type: string
            server:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                owner_id:
                  type: integer
      400:
        description: 参数错误
      401:
        description: 未授权
    """
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "星球名称必填"}), 400
    owner_id = get_jwt_identity()
    server = Server(name=name, owner_id=owner_id)
    db.session.add(server)
    db.session.commit()
    # 自动分配默认角色
    default_role = Role(name="member", server_id=server.id, parent_id=None)
    db.session.add(default_role)
    db.session.commit()
    return (
        jsonify(
            {"message": "星球创建成功", "server": ServerSchema.from_orm(server).dict()}
        ),
        201,
    )


@servers_bp.route("/servers", methods=["GET"])
def list_servers():
    """
    获取星球列表
    ---
    description: |
      获取星球列表，支持分页参数 page, per_page。
    tags:
      - Servers
    parameters:
      - in: query
        name: page
        type: integer
        description: 页码
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量
        example: 10
    responses:
      200:
        description: 星球列表
        schema:
          type: object
          properties:
            servers:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  owner_id:
                    type: integer
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
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = Server.query.paginate(page=page, per_page=per_page, error_out=False)

    servers = [ServerSchema.from_orm(s).dict() for s in pagination.items]

    return (
        jsonify(
            {
                "servers": servers,
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                },
            }
        ),
        200,
    )


@servers_bp.route("/servers/<int:server_id>", methods=["GET"])
def get_server(server_id):
    """
    获取星球详情
    ---
    tags:
      - Servers
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
        example: 1
    responses:
      200:
        description: 星球详情
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            owner_id:
              type: integer
      404:
        description: 星球不存在
    """
    server = Server.query.get(server_id)
    if not server:
        return jsonify({"error": "星球不存在"}), 404
    return jsonify(ServerSchema.from_orm(server).dict()), 200


@servers_bp.route("/servers/<int:server_id>/members", methods=["POST"])
@jwt_required()
def join_server_restful(server_id):
    """
    加入星球（RESTful补充，推荐使用）
    ---
    tags:
      - Servers
    security:
      - Bearer: []
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
        example: 1
    responses:
      201:
        description: 成功加入星球
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
        description: 星球不存在
      409:
        description: 已经是成员
    """
    return join_server(server_id)


@servers_bp.route("/servers/<int:server_id>/join", methods=["POST"])
@jwt_required()
def join_server(server_id):
    """
    加入星球（已废弃，建议使用POST /servers/<server_id>/members）
    ---
    tags:
      - Servers
    security:
      - Bearer: []
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
        example: 1
    responses:
      200:
        description: 成功加入星球
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
        description: 星球不存在
      409:
        description: 已经是成员
    """
    user_id = get_jwt_identity()
    server = Server.query.get(server_id)
    if not server:
        return jsonify({"error": "星球不存在"}), 404
    exists = ServerMember.query.filter_by(user_id=user_id, server_id=server_id).first()
    if exists:
        return jsonify({"error": "已经是成员"}), 409
    member = ServerMember(user_id=user_id, server_id=server_id)
    db.session.add(member)
    db.session.commit()
    return jsonify({"message": "成功加入星球"}), 201


@servers_bp.route("/servers/<int:server_id>/members", methods=["GET"])
def list_server_members(server_id):
    """
    获取星球成员列表
    ---
    description: |
      获取星球成员列表，支持分页参数 page, per_page。
    tags:
      - Servers
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
        example: 1
      - in: query
        name: page
        type: integer
        description: 页码
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量
        example: 10
    responses:
      200:
        description: 成员列表
        schema:
          type: object
          properties:
            members:
              type: array
              items:
                type: object
                properties:
                  user_id:
                    type: integer
                  server_id:
                    type: integer
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
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = ServerMember.query.filter_by(server_id=server_id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    members = [
        {"user_id": m.user_id, "server_id": m.server_id} for m in pagination.items
    ]

    return (
        jsonify(
            {
                "members": members,
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                },
            }
        ),
        200,
    )


@servers_bp.route("/servers/<int:server_id>/members/<int:user_id>", methods=["DELETE"])
@require_permission("remove_member", scope="server", scope_id_arg="server_id")
@jwt_required()
def remove_server_member_restful(server_id, user_id):
    """
    移除星球成员（RESTful补充，推荐使用）
    ---
    tags:
      - Servers
    security:
      - Bearer: []
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
        example: 1
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 2
    responses:
      200:
        description: 成员已移除
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 成员不存在
    """
    member = ServerMember.query.filter_by(user_id=user_id, server_id=server_id).first()
    if not member:
        return jsonify({"error": "成员不存在"}), 404
    db.session.delete(member)
    db.session.commit()
    return jsonify({"message": "成员已移除"}), 200


@servers_bp.route("/servers/<int:server_id>/remove_member", methods=["POST"])
@require_permission("remove_member", scope="server", scope_id_arg="server_id")
@jwt_required()
def remove_server_member(server_id):
    """
    移除星球成员（已废弃，建议使用DELETE /servers/<server_id>/members/<user_id>）
    ---
    tags:
      - Servers
    security:
      - Bearer: []
    parameters:
      - in: path
        name: server_id
        type: integer
        required: true
        description: 星球ID
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
              example: 2
    responses:
      200:
        description: 成员已移除
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
        description: 成员不存在
    """
    data = request.get_json() or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id 必填"}), 400
    member = ServerMember.query.filter_by(user_id=user_id, server_id=server_id).first()
    if not member:
        return jsonify({"error": "成员不存在"}), 404
    db.session.delete(member)
    db.session.commit()
    return jsonify({"message": "成员已移除"}), 200
