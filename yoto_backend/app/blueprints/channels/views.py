from . import channels_bp
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.core.extensions import db
from .models import (
    Channel,
    Category,
    ChannelMember,
    Message,
    MessageReaction,
    SearchHistory,
)
from app.core.permission.permission_decorators import require_permission
from app.core.permission.permission_registry import register_permission

# 导入新的权限工具（仅用于内部使用，不改变现有接口）
from app.core.permission.permission_factories import (
    create_crud_permissions,
    register_crud_permissions,
)


MESSAGE_TEMPLATE = {
    "type": "text",
    "content": "",
    "timestamp": None,
    "sender": None,
    "channel_id": None,
}

# 注册频道和消息相关权限（内部使用，不影响现有接口）
CHANNEL_PERMISSIONS = create_crud_permissions("channel", group="channel")


def _register_channel_permissions():
    """注册频道相关权限 - 延迟初始化"""
    try:
        from flask import current_app

        # 检查是否在Flask应用上下文中
        _ = current_app.name

        register_crud_permissions(
            "channel", group="channel", description="频道管理权限"
        )
        register_crud_permissions(
            "message", group="message", description="消息操作权限"
        )
    except RuntimeError:
        # 不在Flask上下文中，跳过权限注册
        pass


# 延迟注册权限
_register_channel_permissions()

MESSAGE_PERMISSIONS = create_crud_permissions("message", group="message")


def _register_message_permissions():
    """注册消息相关权限 - 延迟初始化"""
    try:
        from flask import current_app

        # 检查是否在Flask应用上下文中
        _ = current_app.name

        # 注册消息相关权限
        register_permission("message.send", group="message", description="发送消息")
        register_permission("message.edit", group="message", description="编辑消息")
        register_permission("message.delete", group="message", description="删除消息")
        register_permission("message.pin", group="message", description="置顶消息")
        register_permission(
            "message.unpin", group="message", description="取消置顶消息"
        )
        register_permission("message.forward", group="message", description="转发消息")
        register_permission(
            "message.react", group="message", description="添加表情反应"
        )
        register_permission("message.search", group="message", description="搜索消息")
        register_permission(
            "message.view_history", group="message", description="查看搜索历史"
        )
        register_permission(
            "message.manage_history", group="message", description="管理搜索历史"
        )
    except RuntimeError:
        # 不在Flask上下文中，跳过权限注册
        pass


# 延迟注册权限
_register_message_permissions()


@channels_bp.route("/channels", methods=["POST"])
@jwt_required()
def create_channel():
    """
    创建频道
    仅允许已登录用户创建频道，需指定 name、server_id 字段，可选 type、category_id、description、icon
    ---
    tags:
      - Channels
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
              example: 一般聊天
            server_id:
              type: integer
              example: 1
            type:
              type: string
              enum: [text, voice, video, announcement]
              example: text
            category_id:
              type: integer
              example: 1
            description:
              type: string
              example: 频道描述
            icon:
              type: string
              example: https://example.com/icon.png
    responses:
      201:
        description: 频道创建成功
        schema:
          type: object
          properties:
            message:
              type: string
            channel_id:
              type: integer
            name:
              type: string
            type:
              type: string
            category_id:
              type: integer
            description:
              type: string
            icon:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
    """
    data = request.get_json() or {}
    name = data.get("name")
    server_id = data.get("server_id")
    ch_type = data.get("type", "text")
    category_id = data.get("category_id")
    description = data.get("description")
    icon = data.get("icon")
    if not name or not server_id:
        return jsonify({"error": "频道名称和server_id必填"}), 400
    if ch_type not in ("text", "voice", "video", "announcement"):
        return jsonify({"error": "频道类型不合法"}), 400
    channel = Channel(
        name=name,
        server_id=server_id,
        type=ch_type,
        category_id=category_id,
        description=description,
        icon=icon,
    )
    db.session.add(channel)
    db.session.commit()
    return (
        jsonify(
            {
                "message": "频道创建成功",
                "channel_id": channel.id,
                "name": channel.name,
                "type": channel.type,
                "category_id": channel.category_id,
                "description": channel.description,
                "icon": channel.icon,
            }
        ),
        201,
    )


@channels_bp.route("/channels", methods=["GET"])
def list_channels():
    """
    查询频道列表
    ---
    description: |
      查询频道列表，支持 server_id 查询参数，返回指定星球下的所有频道。不传 server_id 时返回全部频道。
    tags:
      - Channels
    parameters:
      - in: query
        name: server_id
        type: integer
        description: 星球ID，不传则返回全部频道
        example: 1
    responses:
      200:
        description: 频道列表
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
    query = Channel.query
    if server_id:
        query = query.filter_by(server_id=server_id)
    channels = [
        {"id": c.id, "name": c.name, "server_id": c.server_id} for c in query.all()
    ]
    return jsonify(channels), 200


@channels_bp.route("/channels/<int:channel_id>", methods=["GET"])
def get_channel(channel_id):
    """
    查询频道详情
    ---
    tags:
      - Channels
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 频道详情
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
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    return (
        jsonify(
            {"id": channel.id, "name": channel.name, "server_id": channel.server_id}
        ),
        200,
    )


@channels_bp.route("/channels/<int:channel_id>", methods=["PATCH"])
@jwt_required()
def update_channel(channel_id):
    """
    更新频道信息
    仅允许已登录用户更新频道信息，支持名称、类型、分类、描述、icon
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: 新频道名称
            type:
              type: string
              enum: [text, voice, video, announcement]
              example: text
            category_id:
              type: integer
              example: 1
            description:
              type: string
              example: 新描述
            icon:
              type: string
              example: https://example.com/icon.png
    responses:
      200:
        description: 频道更新成功
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            server_id:
              type: integer
            type:
              type: string
            category_id:
              type: integer
            description:
              type: string
            icon:
              type: string
      401:
        description: 未授权
      404:
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    data = request.get_json() or {}
    name = data.get("name")
    ch_type = data.get("type")
    category_id = data.get("category_id")
    description = data.get("description")
    icon = data.get("icon")
    if name:
        channel.name = name
    if ch_type:
        if ch_type not in ("text", "voice", "video", "announcement"):
            return jsonify({"error": "频道类型不合法"}), 400
        channel.type = ch_type
    if category_id is not None:
        channel.category_id = category_id
    if description is not None:
        channel.description = description
    if icon is not None:
        channel.icon = icon
        db.session.commit()
    return (
        jsonify(
            {
                "id": channel.id,
                "name": channel.name,
                "server_id": channel.server_id,
                "type": channel.type,
                "category_id": channel.category_id,
                "description": channel.description,
                "icon": channel.icon,
            }
        ),
        200,
    )


@channels_bp.route("/channels/<int:channel_id>", methods=["DELETE"])
@jwt_required()
def delete_channel(channel_id):
    """
    删除频道
    仅允许已登录用户删除频道
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 频道删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    db.session.delete(channel)
    db.session.commit()
    return jsonify({"message": "频道已删除"}), 200


@channels_bp.route("/channels/all", methods=["DELETE"])
@jwt_required()
def delete_all_channels():
    """
    删除所有频道（危险操作，仅用于管理/测试场景）
    仅允许已登录用户删除频道
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    responses:
      200:
        description: 所有频道删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
    """
    Channel.query.delete()
    db.session.commit()
    return jsonify({"message": "所有频道已删除"}), 200


@channels_bp.route("/categories", methods=["POST"])
@jwt_required()
def create_category():
    """
    创建频道分类
    ---
    tags:
      - Categories
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
              example: 默认分组
            server_id:
              type: integer
              example: 1
            description:
              type: string
              example: 频道分组描述
    responses:
      201:
        description: 分类创建成功
        schema:
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
    description = data.get("description")
    if not name or not server_id:
        return jsonify({"error": "分类名称和server_id必填"}), 400
    category = Category(name=name, server_id=server_id, description=description)
    db.session.add(category)
    db.session.commit()
    return (
        jsonify(
            {"id": category.id, "name": category.name, "server_id": category.server_id}
        ),
        201,
    )


@channels_bp.route("/categories", methods=["GET"])
def list_categories():
    """
    查询频道分类列表
    ---
    tags:
      - Categories
    parameters:
      - in: query
        name: server_id
        type: integer
        description: 星球ID，不传则返回全部分类
        example: 1
    responses:
      200:
        description: 分类列表
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
              description:
                type: string
    """
    server_id = request.args.get("server_id", type=int)
    query = Category.query
    if server_id:
        query = query.filter_by(server_id=server_id)
    categories = [
        {
            "id": c.id,
            "name": c.name,
            "server_id": c.server_id,
            "description": c.description,
        }
        for c in query.all()
    ]
    return jsonify(categories), 200


@channels_bp.route("/categories/<int:category_id>", methods=["GET"])
def get_category(category_id):
    """
    查询分类详情
    ---
    tags:
      - Categories
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: 分类ID
        example: 1
    responses:
      200:
        description: 分类详情
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            server_id:
              type: integer
            description:
              type: string
      404:
        description: 分类不存在
    """
    category = Category.query.get(category_id)
    if not category:
        return jsonify({"error": "分类不存在"}), 404
    return (
        jsonify(
            {
                "id": category.id,
                "name": category.name,
                "server_id": category.server_id,
                "description": category.description,
            }
        ),
        200,
    )


@channels_bp.route("/categories/<int:category_id>", methods=["PATCH"])
@jwt_required()
def update_category(category_id):
    """
    更新分类信息
    ---
    tags:
      - Categories
    security:
      - Bearer: []
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: 分类ID
        example: 1
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: 新分类名
            description:
              type: string
              example: 新描述
    responses:
      200:
        description: 分类更新成功
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            server_id:
              type: integer
            description:
              type: string
      401:
        description: 未授权
      404:
        description: 分类不存在
    """
    category = Category.query.get(category_id)
    if not category:
        return jsonify({"error": "分类不存在"}), 404
    data = request.get_json() or {}
    name = data.get("name")
    description = data.get("description")
    if name:
        category.name = name
    if description is not None:
        category.description = description
    db.session.commit()
    return (
        jsonify(
            {
                "id": category.id,
                "name": category.name,
                "server_id": category.server_id,
                "description": category.description,
            }
        ),
        200,
    )


@channels_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    """
    删除分类
    ---
    tags:
      - Categories
    security:
      - Bearer: []
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: 分类ID
        example: 1
    responses:
      200:
        description: 分类删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 分类不存在
    """
    category = Category.query.get(category_id)
    if not category:
        return jsonify({"error": "分类不存在"}), 404
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "分类已删除"}), 200


@channels_bp.route("/categories/<int:category_id>/channels", methods=["GET"])
def list_channels_by_category(category_id):
    """
    查询分类下的频道列表
    ---
    tags:
      - Channels
    parameters:
      - in: path
        name: category_id
        type: integer
        required: true
        description: 分类ID
        example: 1
    responses:
      200:
        description: 频道列表
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
              type:
                type: string
              category_id:
                type: integer
              description:
                type: string
              icon:
                type: string
      404:
        description: 分类不存在
    """
    from .models import Category, Channel

    category = Category.query.get(category_id)
    if not category:
        return jsonify({"error": "分类不存在"}), 404
    channels = Channel.query.filter_by(category_id=category_id).all()
    result = [
        {
            "id": c.id,
            "name": c.name,
            "server_id": c.server_id,
            "type": c.type,
            "category_id": c.category_id,
            "description": c.description,
            "icon": c.icon,
        }
        for c in channels
    ]
    return jsonify(result), 200


@channels_bp.route("/channels/<int:channel_id>/type", methods=["GET"])
def get_channel_type(channel_id):
    """
    查询频道类型
    ---
    tags:
      - Channels
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 频道类型
        schema:
          type: object
          properties:
            type:
              type: string
      404:
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    return jsonify({"type": channel.type}), 200


@channels_bp.route("/channels/<int:channel_id>/permissions", methods=["GET"])
@jwt_required()
def get_channel_permissions(channel_id):
    """
    查询当前用户对频道的权限（占位实现）
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 权限信息
        schema:
          type: object
          properties:
            can_view:
              type: boolean
            can_send:
              type: boolean
            can_manage:
              type: boolean
      401:
        description: 未授权
      404:
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    # 占位实现，后续可与权限系统集成
    # 默认全部True
    return jsonify({"can_view": True, "can_send": True, "can_manage": False}), 200


@channels_bp.route("/channels/<int:channel_id>/members", methods=["POST"])
@jwt_required()
def join_channel_member(channel_id):
    """
    加入频道（将当前用户加入频道成员表）
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      201:
        description: 加入频道成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 已在频道内
      401:
        description: 未授权
      404:
        description: 频道不存在
    """
    from flask_jwt_extended import get_jwt_identity

    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    user_id = get_jwt_identity()
    exists = ChannelMember.query.filter_by(
        channel_id=channel_id, user_id=user_id
    ).first()
    if exists:
        return jsonify({"error": "已在频道内"}), 400
    member = ChannelMember(channel_id=channel_id, user_id=user_id)
    db.session.add(member)
    db.session.commit()
    return jsonify({"message": "加入频道成功"}), 201


@channels_bp.route(
    "/channels/<int:channel_id>/members/<int:user_id>", methods=["DELETE"]
)
@jwt_required()
def remove_channel_member(channel_id, user_id):
    """
    移除频道成员
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 2
    responses:
      200:
        description: 成员移除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 频道或成员不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    member = ChannelMember.query.filter_by(
        channel_id=channel_id, user_id=user_id
    ).first()
    if not member:
        return jsonify({"error": "成员不存在"}), 404
    db.session.delete(member)
    db.session.commit()
    return jsonify({"message": "成员移除成功"}), 200


@channels_bp.route("/channels/<int:channel_id>/members", methods=["GET"])
def list_channel_members(channel_id):
    """
    查询频道成员列表（只返回实际在频道内的成员）
    ---
    tags:
      - Channels
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 成员列表
        schema:
          type: array
          items:
            type: object
            properties:
              user_id:
                type: integer
              username:
                type: string
      404:
        description: 频道不存在
    """
    from app.blueprints.auth.models import User

    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    members = ChannelMember.query.filter_by(channel_id=channel_id).all()
    user_ids = [m.user_id for m in members]
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    result = [{"user_id": u.id, "username": u.username} for u in users]
    return jsonify(result), 200


@channels_bp.route("/channels/<int:channel_id>/members/<int:user_id>", methods=["GET"])
def get_channel_member_info(channel_id, user_id):
    """
    查询频道成员的角色与禁言状态
    ---
    tags:
      - Channels
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 2
    responses:
      200:
        description: 成员信息
        schema:
          type: object
          properties:
            user_id:
              type: integer
            role:
              type: string
            is_muted:
              type: boolean
      404:
        description: 频道或成员不存在
    """
    member = ChannelMember.query.filter_by(
        channel_id=channel_id, user_id=user_id
    ).first()
    if not member:
        return jsonify({"error": "成员不存在"}), 404
    return (
        jsonify(
            {
                "user_id": member.user_id,
                "role": member.role,
                "is_muted": member.is_muted,
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/members/<int:user_id>", methods=["PATCH"]
)
@jwt_required()
def update_channel_member_info(channel_id, user_id):
    """
    设置频道成员的角色与禁言状态
    ---
    tags:
      - Channels
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 2
      - in: body
        name: body
        schema:
          type: object
          properties:
            role:
              type: string
              enum: [member, admin]
              example: member
            is_muted:
              type: boolean
              example: false
    responses:
      200:
        description: 成员信息更新成功
        schema:
          type: object
          properties:
            user_id:
              type: integer
            role:
              type: string
            is_muted:
              type: boolean
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 频道或成员不存在
    """
    member = ChannelMember.query.filter_by(
        channel_id=channel_id, user_id=user_id
    ).first()
    if not member:
        return jsonify({"error": "成员不存在"}), 404
    data = request.get_json() or {}
    role = data.get("role")
    is_muted = data.get("is_muted")
    if role:
        if role not in ("member", "admin"):
            return jsonify({"error": "角色不合法"}), 400
        member.role = role
    if is_muted is not None:
        member.is_muted = bool(is_muted)
    db.session.commit()
    return (
        jsonify(
            {
                "user_id": member.user_id,
                "role": member.role,
                "is_muted": member.is_muted,
            }
        ),
        200,
    )


@channels_bp.route("/channels/<int:channel_id>/messages", methods=["POST"])
@jwt_required()
@require_permission("message.send", scope="channel", scope_id_arg="channel_id")
def send_message(channel_id):
    """
    发送消息（存储消息）
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - content
          properties:
            type:
              type: string
              enum: [text, image, file]
              example: text
            content:
              type: string
              example: 你好，世界！
            reply_to:
              type: integer
              description: 回复的消息ID（可选）
              example: 123
    responses:
      201:
        description: 消息发送成功
        schema:
          type: object
          properties:
            id:
              type: integer
            channel_id:
              type: integer
            user_id:
              type: integer
            type:
              type: string
            content:
              type: string
            created_at:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 频道不存在
    """
    from flask_jwt_extended import get_jwt_identity

    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    data = request.get_json() or {}
    msg_type = data.get("type", "text")
    content = data.get("content")
    reply_to_id = data.get("reply_to")
    if not content or msg_type not in ("text", "image", "file"):
        return jsonify({"error": "消息内容或类型不合法"}), 400
    user_id = get_jwt_identity()

    # 验证回复的消息是否存在且在同一频道
    if reply_to_id:
        reply_message = Message.query.get(reply_to_id)
        if not reply_message or reply_message.channel_id != channel_id:
            return jsonify({"error": "回复的消息不存在或不在同一频道"}), 400

    # 解析@提及
    mentions = []
    if msg_type == "text" and content:
        import re

        # 匹配@用户名格式，支持中文、英文、数字
        mention_pattern = r"@([a-zA-Z0-9\u4e00-\u9fa5_]+)"
        mentioned_usernames = re.findall(mention_pattern, content)

        if mentioned_usernames:
            from app.blueprints.auth.models import User

            # 查询被@的用户
            mentioned_users = User.query.filter(
                User.username.in_(mentioned_usernames)
            ).all()
            mentions = [user.id for user in mentioned_users]

    msg = Message(
        channel_id=channel_id,
        user_id=user_id,
        type=msg_type,
        content=content,
        mentions=mentions if mentions else None,
        reply_to_id=reply_to_id,
    )
    db.session.add(msg)
    db.session.commit()

    return (
        jsonify(
            {
                "id": msg.id,
                "channel_id": msg.channel_id,
                "user_id": msg.user_id,
                "type": msg.type,
                "content": msg.content,
                "mentions": mentions,
                "reply_to_id": reply_to_id,
                "created_at": msg.created_at.isoformat(),
            }
        ),
        201,
    )


@channels_bp.route("/channels/<int:channel_id>/messages", methods=["GET"])
def list_messages(channel_id):
    """
    查询频道消息历史（支持分页）
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
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
        example: 20
    responses:
      200:
        description: 消息列表
        schema:
          type: object
          properties:
            messages:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  user_id:
                    type: integer
                  type:
                    type: string
                  content:
                    type: string
                  created_at:
                    type: string
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
      404:
        description: 频道不存在
    """
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = (
        Message.query.filter_by(channel_id=channel_id, is_deleted=False)
        .order_by(Message.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    messages = []
    for m in pagination.items:
        message_data = {
            "id": m.id,
            "channel_id": m.channel_id,
            "user_id": m.user_id,
            "type": m.type,
            "content": m.content,
            "mentions": m.mentions or [],
            "reply_to_id": m.reply_to_id,
            "created_at": m.created_at.isoformat(),
            "is_edited": m.is_edited,
            "updated_at": m.updated_at.isoformat() if m.is_edited else None,
            "is_forwarded": m.is_forwarded,
            "original_message_id": m.original_message_id,
            "original_channel_id": m.original_channel_id,
            "original_user_id": m.original_user_id,
            "forward_comment": m.forward_comment,
            "is_pinned": m.is_pinned,
            "pinned_at": m.pinned_at.isoformat() if m.pinned_at else None,
            "pinned_by": m.pinned_by,
        }

        # 如果有回复的消息，添加被回复消息的摘要
        if m.reply_to_id:
            reply_message = Message.query.get(m.reply_to_id)
            if reply_message and not reply_message.is_deleted:
                from app.blueprints.auth.models import User

                reply_user = User.query.get(reply_message.user_id)
                message_data["reply_to"] = {
                    "id": reply_message.id,
                    "user_id": reply_message.user_id,
                    "username": reply_user.username if reply_user else "Unknown",
                    "content": (
                        reply_message.content[:100] + "..."
                        if len(reply_message.content) > 100
                        else reply_message.content
                    ),
                    "type": reply_message.type,
                }

        # 添加表情反应统计信息
        reactions = MessageReaction.query.filter_by(message_id=m.id).all()
        reaction_stats = {}
        for reaction in reactions:
            if reaction.reaction not in reaction_stats:
                reaction_stats[reaction.reaction] = {
                    "reaction": reaction.reaction,
                    "count": 0,
                }
            reaction_stats[reaction.reaction]["count"] += 1

        message_data["reactions"] = list(reaction_stats.values())

        messages.append(message_data)
    return (
        jsonify(
            {
                "messages": messages,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>", methods=["PATCH"]
)
@jwt_required()
@require_permission("message.edit", scope="channel", scope_id_arg="channel_id")
def edit_message(channel_id, message_id):
    """
    编辑消息
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
              example: 编辑后的消息内容
    responses:
      200:
        description: 消息编辑成功
        schema:
          type: object
          properties:
            id:
              type: integer
            content:
              type: string
            is_edited:
              type: boolean
            updated_at:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      403:
        description: 无权限编辑
      404:
        description: 消息不存在
    """
    user_id = get_jwt_identity()
    message = Message.query.filter_by(id=message_id, channel_id=channel_id).first()
    if not message:
        return jsonify({"error": "消息不存在"}), 404

    # 检查权限：只能编辑自己的消息
    if message.user_id != int(user_id):
        return jsonify({"error": "无权限编辑此消息"}), 403

    data = request.get_json() or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "消息内容不能为空"}), 400

    message.content = content
    message.is_edited = True
    db.session.commit()

    return (
        jsonify(
            {
                "id": message.id,
                "content": message.content,
                "is_edited": message.is_edited,
                "updated_at": message.updated_at.isoformat(),
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>", methods=["DELETE"]
)
@jwt_required()
@require_permission("message.delete", scope="channel", scope_id_arg="channel_id")
def delete_message(channel_id, message_id):
    """
    删除消息
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 1
    responses:
      200:
        description: 消息删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      403:
        description: 无权限删除
      404:
        description: 消息不存在
    """
    user_id = get_jwt_identity()
    message = Message.query.filter_by(id=message_id, channel_id=channel_id).first()
    if not message:
        return jsonify({"error": "消息不存在"}), 404

    # 检查权限：只能删除自己的消息
    if message.user_id != int(user_id):
        return jsonify({"error": "无权限删除此消息"}), 403

    message.is_deleted = True
    db.session.commit()

    return jsonify({"message": "消息删除成功"}), 200


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>", methods=["GET"]
)
def get_message(channel_id, message_id):
    """
    获取单条消息详情
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 1
    responses:
      200:
        description: 消息详情
        schema:
          type: object
          properties:
            id:
              type: integer
            channel_id:
              type: integer
            user_id:
              type: integer
            type:
              type: string
            content:
              type: string
            created_at:
              type: string
            is_edited:
              type: boolean
            updated_at:
              type: string
      404:
        description: 消息不存在
    """
    message = Message.query.filter_by(
        id=message_id, channel_id=channel_id, is_deleted=False
    ).first()
    if not message:
        return jsonify({"error": "消息不存在"}), 404

    return (
        jsonify(
            {
                "id": message.id,
                "channel_id": message.channel_id,
                "user_id": message.user_id,
                "type": message.type,
                "content": message.content,
                "mentions": message.mentions or [],
                "created_at": message.created_at.isoformat(),
                "is_edited": message.is_edited,
                "updated_at": (
                    message.updated_at.isoformat() if message.is_edited else None
                ),
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/replies", methods=["GET"]
)
def get_message_replies(channel_id, message_id):
    """
    获取指定消息的回复列表
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 123
      - in: query
        name: page
        type: integer
        description: 页码（默认1）
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量（默认20，最大100）
        example: 20
    responses:
      200:
        description: 回复列表
        schema:
          type: object
          properties:
            replies:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  user_id:
                    type: integer
                  username:
                    type: string
                  type:
                    type: string
                  content:
                    type: string
                  created_at:
                    type: string
                  is_edited:
                    type: boolean
                  updated_at:
                    type: string
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
      404:
        description: 频道或消息不存在
    """
    # 验证频道和消息是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    original_message = Message.query.get(message_id)
    if not original_message or original_message.channel_id != channel_id:
        return jsonify({"error": "消息不存在或不在指定频道"}), 404

    # 分页参数
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)  # 限制最大100

    # 查询回复消息
    query = Message.query.filter(
        Message.reply_to_id == message_id, Message.is_deleted == False
    ).order_by(
        Message.created_at.asc()
    )  # 按时间正序排列

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建返回数据
    replies = []
    for reply in pagination.items:
        from app.blueprints.auth.models import User

        user = User.query.get(reply.user_id)

        reply_data = {
            "id": reply.id,
            "channel_id": reply.channel_id,
            "user_id": reply.user_id,
            "username": user.username if user else "Unknown",
            "type": reply.type,
            "content": reply.content,
            "created_at": reply.created_at.isoformat(),
            "is_edited": reply.is_edited,
            "updated_at": reply.updated_at.isoformat() if reply.is_edited else None,
        }
        replies.append(reply_data)

    return (
        jsonify(
            {
                "replies": replies,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/reactions", methods=["POST"]
)
@jwt_required()
@require_permission("message.react", scope="channel", scope_id_arg="channel_id")
def add_message_reaction(channel_id, message_id):
    """
    为消息添加表情反应
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 123
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - reaction
          properties:
            reaction:
              type: string
              description: 表情符号
              example: "👍"
    responses:
      201:
        description: 表情反应添加成功
        schema:
          type: object
          properties:
            message:
              type: string
            reaction:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 频道或消息不存在
      409:
        description: 表情反应已存在
    """
    from flask_jwt_extended import get_jwt_identity

    # 验证频道和消息是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    message = Message.query.get(message_id)
    if not message or message.channel_id != channel_id:
        return jsonify({"error": "消息不存在或不在指定频道"}), 404

    data = request.get_json() or {}
    reaction = data.get("reaction")

    if not reaction:
        return jsonify({"error": "表情符号必填"}), 400

    # 验证表情符号长度
    if len(reaction) > 10:
        return jsonify({"error": "表情符号过长"}), 400

    user_id = get_jwt_identity()

    # 检查是否已存在相同的表情反应
    existing_reaction = MessageReaction.query.filter_by(
        message_id=message_id, user_id=int(user_id), reaction=reaction
    ).first()

    if existing_reaction:
        return jsonify({"error": "表情反应已存在"}), 409

    # 添加表情反应
    new_reaction = MessageReaction(
        message_id=message_id, user_id=int(user_id), reaction=reaction
    )
    db.session.add(new_reaction)
    db.session.commit()

    return jsonify({"message": "表情反应添加成功", "reaction": reaction}), 201


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/reactions", methods=["DELETE"]
)
@jwt_required()
@require_permission("message.react", scope="channel", scope_id_arg="channel_id")
def remove_message_reaction(channel_id, message_id):
    """
    移除消息的表情反应
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 123
      - in: query
        name: reaction
        type: string
        required: true
        description: 表情符号
        example: "👍"
    responses:
      200:
        description: 表情反应移除成功
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
        description: 频道、消息或表情反应不存在
    """
    from flask_jwt_extended import get_jwt_identity

    # 验证频道和消息是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    message = Message.query.get(message_id)
    if not message or message.channel_id != channel_id:
        return jsonify({"error": "消息不存在或不在指定频道"}), 404

    reaction = request.args.get("reaction")
    if not reaction:
        return jsonify({"error": "表情符号必填"}), 400

    user_id = get_jwt_identity()

    # 查找并删除表情反应
    existing_reaction = MessageReaction.query.filter_by(
        message_id=message_id, user_id=int(user_id), reaction=reaction
    ).first()

    if not existing_reaction:
        return jsonify({"error": "表情反应不存在"}), 404

    db.session.delete(existing_reaction)
    db.session.commit()

    return jsonify({"message": "表情反应移除成功"}), 200


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/reactions", methods=["GET"]
)
def get_message_reactions(channel_id, message_id):
    """
    获取消息的表情反应列表
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 消息ID
        example: 123
    responses:
      200:
        description: 表情反应列表
        schema:
          type: object
          properties:
            reactions:
              type: array
              items:
                type: object
                properties:
                  reaction:
                    type: string
                  count:
                    type: integer
                  users:
                    type: array
                    items:
                      type: object
                      properties:
                        user_id:
                          type: integer
                        username:
                          type: string
      404:
        description: 频道或消息不存在
    """
    # 验证频道和消息是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    message = Message.query.get(message_id)
    if not message or message.channel_id != channel_id:
        return jsonify({"error": "消息不存在或不在指定频道"}), 404

    # 获取所有表情反应
    reactions = MessageReaction.query.filter_by(message_id=message_id).all()

    # 按表情符号分组统计
    reaction_stats = {}
    for reaction in reactions:
        if reaction.reaction not in reaction_stats:
            reaction_stats[reaction.reaction] = {
                "reaction": reaction.reaction,
                "count": 0,
                "users": [],
            }

        reaction_stats[reaction.reaction]["count"] += 1

        # 获取用户信息
        from app.blueprints.auth.models import User

        user = User.query.get(reaction.user_id)
        reaction_stats[reaction.reaction]["users"].append(
            {
                "user_id": reaction.user_id,
                "username": user.username if user else "Unknown",
            }
        )

    return jsonify({"reactions": list(reaction_stats.values())}), 200


@channels_bp.route("/channels/<int:channel_id>/messages/search", methods=["GET"])
@jwt_required()
@require_permission("message.search", scope="channel", scope_id_arg="channel_id")
def search_messages(channel_id):
    """
    搜索频道消息
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: query
        name: q
        type: string
        required: true
        description: 搜索关键词
        example: "hello"
      - in: query
        name: user_id
        type: integer
        description: 按用户ID过滤
        example: 1
      - in: query
        name: message_type
        type: string
        enum: [text, image, file]
        description: 按消息类型过滤
        example: text
      - in: query
        name: start_date
        type: string
        format: date
        description: 开始日期（YYYY-MM-DD）
        example: "2024-01-01"
      - in: query
        name: end_date
        type: string
        format: date
        description: 结束日期（YYYY-MM-DD）
        example: "2024-12-31"
      - in: query
        name: page
        type: integer
        description: 页码（默认1）
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量（默认20，最大100）
        example: 20
      - in: query
        name: sort
        type: string
        enum: [relevance, date_asc, date_desc]
        description: 排序方式（默认relevance）
        example: relevance
    responses:
      200:
        description: 搜索结果
        schema:
          type: object
          properties:
            messages:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  user_id:
                    type: integer
                  username:
                    type: string
                  type:
                    type: string
                  content:
                    type: string
                  highlighted_content:
                    type: string
                  created_at:
                    type: string
                  is_edited:
                    type: boolean
                  updated_at:
                    type: string
                  mentions:
                    type: array
                  reply_to_id:
                    type: integer
                  reactions:
                    type: array
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
            query:
              type: string
      400:
        description: 参数错误
      404:
        description: 频道不存在
    """
    # 验证频道是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    # 获取搜索参数
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "搜索关键词必填"}), 400

    user_id = request.args.get("user_id", type=int)
    message_type = request.args.get("message_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    sort = request.args.get("sort", "relevance")

    # 验证消息类型
    if message_type and message_type not in ("text", "image", "file"):
        return jsonify({"error": "无效的消息类型"}), 400

    # 验证排序方式
    if sort not in ("relevance", "date_asc", "date_desc"):
        sort = "relevance"

    # 构建查询条件
    from sqlalchemy import and_, or_, func
    from datetime import datetime

    # 基础查询：频道内未删除的消息
    base_query = Message.query.filter(
        Message.channel_id == channel_id, Message.is_deleted == False
    )

    # 关键词搜索（在内容中搜索）
    if query:
        base_query = base_query.filter(Message.content.ilike(f"%{query}%"))

    # 用户过滤
    if user_id:
        base_query = base_query.filter(Message.user_id == user_id)

    # 消息类型过滤
    if message_type:
        base_query = base_query.filter(Message.type == message_type)

    # 时间范围过滤
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            base_query = base_query.filter(Message.created_at >= start_datetime)
        except ValueError:
            return jsonify({"error": "开始日期格式错误，应为YYYY-MM-DD"}), 400

    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            # 结束日期包含当天
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Message.created_at <= end_datetime)
        except ValueError:
            return jsonify({"error": "结束日期格式错误，应为YYYY-MM-DD"}), 400

    # 排序
    if sort == "date_asc":
        base_query = base_query.order_by(Message.created_at.asc())
    elif sort == "date_desc":
        base_query = base_query.order_by(Message.created_at.desc())
    else:  # relevance - 按创建时间倒序（最新优先）
        base_query = base_query.order_by(Message.created_at.desc())

    # 分页查询
    pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建返回数据
    messages = []
    for msg in pagination.items:
        # 获取用户信息
        from app.blueprints.auth.models import User

        user = User.query.get(msg.user_id)

        # 高亮显示匹配的关键词
        highlighted_content = msg.content
        if query:
            # 简单的关键词高亮（用**包围）
            import re

            pattern = re.compile(re.escape(query), re.IGNORECASE)
            highlighted_content = pattern.sub(f"**{query}**", msg.content)

        # 获取表情反应统计
        reactions = MessageReaction.query.filter_by(message_id=msg.id).all()
        reaction_stats = {}
        for reaction in reactions:
            if reaction.reaction not in reaction_stats:
                reaction_stats[reaction.reaction] = {
                    "reaction": reaction.reaction,
                    "count": 0,
                }
            reaction_stats[reaction.reaction]["count"] += 1

        message_data = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": msg.user_id,
            "username": user.username if user else "Unknown",
            "type": msg.type,
            "content": msg.content,
            "highlighted_content": highlighted_content,
            "created_at": msg.created_at.isoformat(),
            "is_edited": msg.is_edited,
            "updated_at": msg.updated_at.isoformat() if msg.is_edited else None,
            "mentions": msg.mentions or [],
            "reply_to_id": msg.reply_to_id,
            "reactions": list(reaction_stats.values()),
            "is_forwarded": msg.is_forwarded,
            "original_message_id": msg.original_message_id,
            "original_channel_id": msg.original_channel_id,
            "original_user_id": msg.original_user_id,
            "forward_comment": msg.forward_comment,
        }

        # 如果有回复的消息，添加被回复消息的摘要
        if msg.reply_to_id:
            reply_message = Message.query.get(msg.reply_to_id)
            if reply_message and not reply_message.is_deleted:
                reply_user = User.query.get(reply_message.user_id)
                message_data["reply_to"] = {
                    "id": reply_message.id,
                    "user_id": reply_message.user_id,
                    "username": reply_user.username if reply_user else "Unknown",
                    "content": (
                        reply_message.content[:100] + "..."
                        if len(reply_message.content) > 100
                        else reply_message.content
                    ),
                    "type": reply_message.type,
                }

        messages.append(message_data)

    # 记录搜索历史
    from flask_jwt_extended import get_jwt_identity

    current_user_id = get_jwt_identity()

    # 构建过滤条件
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if message_type:
        filters["message_type"] = message_type
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date
    if sort != "relevance":
        filters["sort"] = sort

    # 创建搜索历史记录
    search_history = SearchHistory(
        user_id=int(current_user_id),
        query=query,
        search_type="channel",
        channel_id=channel_id,
        filters=filters if filters else None,
        result_count=pagination.total,
    )
    db.session.add(search_history)
    db.session.commit()

    return (
        jsonify(
            {
                "messages": messages,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "query": query,
            }
        ),
        200,
    )


@channels_bp.route("/messages/search", methods=["GET"])
@jwt_required()
@require_permission("message.search")
def search_all_messages():
    """
    全局消息搜索（跨频道）
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: query
        name: q
        type: string
        required: true
        description: 搜索关键词
        example: "hello"
      - in: query
        name: channel_id
        type: integer
        description: 按频道ID过滤
        example: 1
      - in: query
        name: server_id
        type: integer
        description: 按服务器ID过滤
        example: 1
      - in: query
        name: user_id
        type: integer
        description: 按用户ID过滤
        example: 1
      - in: query
        name: message_type
        type: string
        enum: [text, image, file]
        description: 按消息类型过滤
        example: text
      - in: query
        name: start_date
        type: string
        format: date
        description: 开始日期（YYYY-MM-DD）
        example: "2024-01-01"
      - in: query
        name: end_date
        type: string
        format: date
        description: 结束日期（YYYY-MM-DD）
        example: "2024-12-31"
      - in: query
        name: page
        type: integer
        description: 页码（默认1）
        example: 1
      - in: query
        name: per_page
        type: integer
        description: 每页数量（默认20，最大100）
        example: 20
      - in: query
        name: sort
        type: string
        enum: [relevance, date_asc, date_desc]
        description: 排序方式（默认relevance）
        example: relevance
    responses:
      200:
        description: 搜索结果
        schema:
          type: object
          properties:
            messages:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  channel_name:
                    type: string
                  server_id:
                    type: integer
                  server_name:
                    type: string
                  user_id:
                    type: integer
                  username:
                    type: string
                  type:
                    type: string
                  content:
                    type: string
                  highlighted_content:
                    type: string
                  created_at:
                    type: string
                  is_edited:
                    type: boolean
                  updated_at:
                    type: string
                  mentions:
                    type: array
                  reply_to_id:
                    type: integer
                  reactions:
                    type: array
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
            query:
              type: string
      400:
        description: 参数错误
      401:
        description: 未授权
    """
    from flask_jwt_extended import get_jwt_identity
    from app.blueprints.servers.models import Server, ServerMember

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 获取搜索参数
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "搜索关键词必填"}), 400

    channel_id = request.args.get("channel_id", type=int)
    server_id = request.args.get("server_id", type=int)
    user_id = request.args.get("user_id", type=int)
    message_type = request.args.get("message_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    sort = request.args.get("sort", "relevance")

    # 验证消息类型
    if message_type and message_type not in ("text", "image", "file"):
        return jsonify({"error": "无效的消息类型"}), 400

    # 验证排序方式
    if sort not in ("relevance", "date_asc", "date_desc"):
        sort = "relevance"

    # 构建查询条件
    from sqlalchemy import and_, or_, func
    from datetime import datetime

    # 基础查询：未删除的消息
    base_query = Message.query.filter(Message.is_deleted == False)

    # 关键词搜索（在内容中搜索）
    if query:
        base_query = base_query.filter(Message.content.ilike(f"%{query}%"))

    # 频道过滤
    if channel_id:
        base_query = base_query.filter(Message.channel_id == channel_id)

    # 服务器过滤（通过频道关联）
    if server_id:
        base_query = base_query.join(Channel).filter(Channel.server_id == server_id)

    # 用户过滤
    if user_id:
        base_query = base_query.filter(Message.user_id == user_id)

    # 消息类型过滤
    if message_type:
        base_query = base_query.filter(Message.type == message_type)

    # 时间范围过滤
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            base_query = base_query.filter(Message.created_at >= start_datetime)
        except ValueError:
            return jsonify({"error": "开始日期格式错误，应为YYYY-MM-DD"}), 400

    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            # 结束日期包含当天
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Message.created_at <= end_datetime)
        except ValueError:
            return jsonify({"error": "结束日期格式错误，应为YYYY-MM-DD"}), 400

    # 权限过滤：只能搜索用户有权限访问的频道
    # 获取用户所在的服务器
    user_servers = ServerMember.query.filter_by(user_id=int(current_user_id)).all()
    server_ids = [member.server_id for member in user_servers]

    if server_ids:
        base_query = base_query.join(Channel).filter(Channel.server_id.in_(server_ids))
    else:
        # 用户没有加入任何服务器，返回空结果
        return (
            jsonify(
                {
                    "messages": [],
                    "page": page,
                    "per_page": per_page,
                    "total": 0,
                    "query": query,
                }
            ),
            200,
        )

    # 排序
    if sort == "date_asc":
        base_query = base_query.order_by(Message.created_at.asc())
    elif sort == "date_desc":
        base_query = base_query.order_by(Message.created_at.desc())
    else:  # relevance - 按创建时间倒序（最新优先）
        base_query = base_query.order_by(Message.created_at.desc())

    # 分页查询
    pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建返回数据
    messages = []
    for msg in pagination.items:
        # 获取用户信息
        from app.blueprints.auth.models import User

        user = User.query.get(msg.user_id)

        # 获取频道信息
        channel = Channel.query.get(msg.channel_id)

        # 获取服务器信息
        server = Server.query.get(channel.server_id) if channel else None

        # 高亮显示匹配的关键词
        highlighted_content = msg.content
        if query:
            # 简单的关键词高亮（用**包围）
            import re

            pattern = re.compile(re.escape(query), re.IGNORECASE)
            highlighted_content = pattern.sub(f"**{query}**", msg.content)

        # 获取表情反应统计
        reactions = MessageReaction.query.filter_by(message_id=msg.id).all()
        reaction_stats = {}
        for reaction in reactions:
            if reaction.reaction not in reaction_stats:
                reaction_stats[reaction.reaction] = {
                    "reaction": reaction.reaction,
                    "count": 0,
                }
            reaction_stats[reaction.reaction]["count"] += 1

        message_data = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "channel_name": channel.name if channel else "Unknown",
            "server_id": channel.server_id if channel else None,
            "server_name": server.name if server else "Unknown",
            "user_id": msg.user_id,
            "username": user.username if user else "Unknown",
            "type": msg.type,
            "content": msg.content,
            "highlighted_content": highlighted_content,
            "created_at": msg.created_at.isoformat(),
            "is_edited": msg.is_edited,
            "updated_at": msg.updated_at.isoformat() if msg.is_edited else None,
            "mentions": msg.mentions or [],
            "reply_to_id": msg.reply_to_id,
            "reactions": list(reaction_stats.values()),
        }

        # 如果有回复的消息，添加被回复消息的摘要
        if msg.reply_to_id:
            reply_message = Message.query.get(msg.reply_to_id)
            if reply_message and not reply_message.is_deleted:
                reply_user = User.query.get(reply_message.user_id)
                message_data["reply_to"] = {
                    "id": reply_message.id,
                    "user_id": reply_message.user_id,
                    "username": reply_user.username if reply_user else "Unknown",
                    "content": (
                        reply_message.content[:100] + "..."
                        if len(reply_message.content) > 100
                        else reply_message.content
                    ),
                    "type": reply_message.type,
                }

        messages.append(message_data)

    # 记录搜索历史
    from flask_jwt_extended import get_jwt_identity

    current_user_id = get_jwt_identity()

    # 构建过滤条件
    filters = {}
    if channel_id:
        filters["channel_id"] = channel_id
    if server_id:
        filters["server_id"] = server_id
    if user_id:
        filters["user_id"] = user_id
    if message_type:
        filters["message_type"] = message_type
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date
    if sort != "relevance":
        filters["sort"] = sort

    # 创建搜索历史记录
    search_history = SearchHistory(
        user_id=int(current_user_id),
        query=query,
        search_type="global",
        channel_id=None,  # 全局搜索没有特定频道
        filters=filters if filters else None,
        result_count=pagination.total,
    )
    db.session.add(search_history)
    db.session.commit()

    return (
        jsonify(
            {
                "messages": messages,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "query": query,
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/forward", methods=["POST"]
)
@jwt_required()
@require_permission("message.forward", scope="channel", scope_id_arg="channel_id")
def forward_message(channel_id, message_id):
    """
    转发消息到其他频道
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 源频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 要转发的消息ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - target_channels
          properties:
            target_channels:
              type: array
              items:
                type: integer
              description: 目标频道ID列表
              example: [2, 3]
            comment:
              type: string
              description: 转发时的评论
              example: "这条消息很重要"
    responses:
      200:
        description: 转发成功
        schema:
          type: object
          properties:
            message:
              type: string
            forwarded_messages:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  original_message_id:
                    type: integer
                  original_channel_id:
                    type: integer
                  original_user_id:
                    type: integer
                  forward_comment:
                    type: string
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 消息或频道不存在
      403:
        description: 权限不足
    """
    from flask_jwt_extended import get_jwt_identity
    from app.blueprints.auth.models import User

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 验证源消息是否存在
    source_message = Message.query.get(message_id)
    if not source_message or source_message.is_deleted:
        return jsonify({"error": "消息不存在或已删除"}), 404

    # 验证源频道是否存在
    source_channel = Channel.query.get(channel_id)
    if not source_channel:
        return jsonify({"error": "源频道不存在"}), 404

    # 验证消息是否在指定频道中
    if source_message.channel_id != channel_id:
        return jsonify({"error": "消息不在指定频道中"}), 404

    # 获取请求数据
    data = request.get_json() or {}
    target_channels = data.get("target_channels", [])
    comment = data.get("comment", "").strip()
    if not comment:
        comment = None

    if not target_channels:
        return jsonify({"error": "目标频道列表不能为空"}), 400

    if not isinstance(target_channels, list):
        return jsonify({"error": "目标频道必须是数组格式"}), 400

    # 验证目标频道是否存在且用户有权限
    valid_target_channels = []
    for target_channel_id in target_channels:
        target_channel = Channel.query.get(target_channel_id)
        if not target_channel:
            continue

        # 检查用户是否有权限转发到目标频道
        # 这里简化处理：检查用户是否在目标频道所在的服务器中
        from app.blueprints.servers.models import ServerMember

        server_member = ServerMember.query.filter_by(
            user_id=int(current_user_id), server_id=target_channel.server_id
        ).first()

        if server_member:
            valid_target_channels.append(target_channel_id)

    if not valid_target_channels:
        return jsonify({"error": "没有有效的目标频道或权限不足"}), 403

    # 转发消息到目标频道
    forwarded_messages = []
    for target_channel_id in valid_target_channels:
        # 创建转发消息
        forwarded_message = Message(
            channel_id=target_channel_id,
            user_id=int(current_user_id),
            type=source_message.type,
            content=source_message.content,
            is_forwarded=True,
            original_message_id=source_message.id,
            original_channel_id=source_message.channel_id,
            original_user_id=source_message.user_id,
            forward_comment=comment,
        )

        db.session.add(forwarded_message)
        forwarded_messages.append(forwarded_message)

    db.session.commit()

    # 构建返回数据
    result_messages = []
    for msg in forwarded_messages:
        # 获取原消息发送者信息
        original_user = User.query.get(msg.original_user_id)
        original_channel = Channel.query.get(msg.original_channel_id)

        message_data = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": msg.user_id,
            "type": msg.type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "is_forwarded": msg.is_forwarded,
            "original_message_id": msg.original_message_id,
            "original_channel_id": msg.original_channel_id,
            "original_user_id": msg.original_user_id,
            "original_username": original_user.username if original_user else "Unknown",
            "original_channel_name": (
                original_channel.name if original_channel else "Unknown"
            ),
            "forward_comment": msg.forward_comment,
        }
        result_messages.append(message_data)

    return (
        jsonify(
            {
                "message": f"成功转发到 {len(valid_target_channels)} 个频道",
                "forwarded_messages": result_messages,
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/pin", methods=["POST"]
)
@jwt_required()
@require_permission("message.pin", scope="channel", scope_id_arg="channel_id")
def pin_message(channel_id, message_id):
    """
    置顶消息
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 要置顶的消息ID
        example: 1
    responses:
      200:
        description: 置顶成功
        schema:
          type: object
          properties:
            message:
              type: string
            pinned_message:
              type: object
              properties:
                id:
                  type: integer
                channel_id:
                  type: integer
                user_id:
                  type: integer
                content:
                  type: string
                is_pinned:
                  type: boolean
                pinned_at:
                  type: string
                pinned_by:
                  type: integer
      400:
        description: 参数错误
      401:
        description: 未授权
      404:
        description: 消息或频道不存在
      403:
        description: 权限不足
    """
    from flask_jwt_extended import get_jwt_identity

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 验证消息是否存在
    message = Message.query.get(message_id)
    if not message or message.is_deleted:
        return jsonify({"error": "消息不存在或已删除"}), 404

    # 验证频道是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    # 验证消息是否在指定频道中
    if message.channel_id != channel_id:
        return jsonify({"error": "消息不在指定频道中"}), 404

    # 检查消息是否已经置顶
    if message.is_pinned:
        return jsonify({"error": "消息已经是置顶状态"}), 400

    # 置顶消息
    message.is_pinned = True
    message.pinned_at = db.func.now()
    message.pinned_by = int(current_user_id)

    db.session.commit()

    return (
        jsonify(
            {
                "message": "消息置顶成功",
                "pinned_message": {
                    "id": message.id,
                    "channel_id": message.channel_id,
                    "user_id": message.user_id,
                    "content": message.content,
                    "is_pinned": message.is_pinned,
                    "pinned_at": (
                        message.pinned_at.isoformat() if message.pinned_at else None
                    ),
                    "pinned_by": message.pinned_by,
                },
            }
        ),
        200,
    )


@channels_bp.route(
    "/channels/<int:channel_id>/messages/<int:message_id>/unpin", methods=["POST"]
)
@jwt_required()
@require_permission("message.unpin", scope="channel", scope_id_arg="channel_id")
def unpin_message(channel_id, message_id):
    """
    取消置顶消息
    ---
    tags:
      - Messages
    security:
      - Bearer: []
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
      - in: path
        name: message_id
        type: integer
        required: true
        description: 要取消置顶的消息ID
        example: 1
    responses:
      200:
        description: 取消置顶成功
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
        description: 消息或频道不存在
      403:
        description: 权限不足
    """
    from flask_jwt_extended import get_jwt_identity

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 验证消息是否存在
    message = Message.query.get(message_id)
    if not message or message.is_deleted:
        return jsonify({"error": "消息不存在或已删除"}), 404

    # 验证频道是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    # 验证消息是否在指定频道中
    if message.channel_id != channel_id:
        return jsonify({"error": "消息不在指定频道中"}), 404

    # 检查消息是否已经取消置顶
    if not message.is_pinned:
        return jsonify({"error": "消息不是置顶状态"}), 400

    # 取消置顶消息
    message.is_pinned = False
    message.pinned_at = None
    message.pinned_by = None

    db.session.commit()

    return jsonify({"message": "消息取消置顶成功"}), 200


@channels_bp.route("/channels/<int:channel_id>/messages/pinned", methods=["GET"])
def get_pinned_messages(channel_id):
    """
    获取频道的置顶消息列表
    ---
    tags:
      - Messages
    parameters:
      - in: path
        name: channel_id
        type: integer
        required: true
        description: 频道ID
        example: 1
    responses:
      200:
        description: 置顶消息列表
        schema:
          type: object
          properties:
            pinned_messages:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  channel_id:
                    type: integer
                  user_id:
                    type: integer
                  username:
                    type: string
                  type:
                    type: string
                  content:
                    type: string
                  created_at:
                    type: string
                  is_pinned:
                    type: boolean
                  pinned_at:
                    type: string
                  pinned_by:
                    type: integer
                  pinned_by_username:
                    type: string
      404:
        description: 频道不存在
    """
    # 验证频道是否存在
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({"error": "频道不存在"}), 404

    # 获取置顶消息列表
    pinned_messages = (
        Message.query.filter_by(channel_id=channel_id, is_pinned=True, is_deleted=False)
        .order_by(Message.pinned_at.desc())
        .all()
    )

    # 构建返回数据
    from app.blueprints.auth.models import User

    result_messages = []
    for msg in pinned_messages:
        # 获取发送者信息
        user = User.query.get(msg.user_id)
        pinned_by_user = User.query.get(msg.pinned_by) if msg.pinned_by else None

        message_data = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": msg.user_id,
            "username": user.username if user else "Unknown",
            "type": msg.type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "is_pinned": msg.is_pinned,
            "pinned_at": msg.pinned_at.isoformat() if msg.pinned_at else None,
            "pinned_by": msg.pinned_by,
            "pinned_by_username": (
                pinned_by_user.username if pinned_by_user else "Unknown"
            ),
        }
        result_messages.append(message_data)

    return (
        jsonify({"pinned_messages": result_messages, "count": len(result_messages)}),
        200,
    )


@channels_bp.route("/search/history", methods=["GET"])
@jwt_required()
@require_permission("message.view_history")
def get_search_history():
    """
    获取用户的搜索历史记录
    ---
    tags:
      - Search
    security:
      - Bearer: []
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
        example: 20
      - in: query
        name: search_type
        type: string
        enum: [channel, global]
        description: 搜索类型过滤
        example: global
    responses:
      200:
        description: 搜索历史列表
        schema:
          type: object
          properties:
            search_history:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  query:
                    type: string
                  search_type:
                    type: string
                  channel_id:
                    type: integer
                  filters:
                    type: object
                  result_count:
                    type: integer
                  created_at:
                    type: string
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
      401:
        description: 未授权
    """
    from flask_jwt_extended import get_jwt_identity

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 获取查询参数
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search_type = request.args.get("search_type")

    # 构建查询
    query = SearchHistory.query.filter_by(user_id=int(current_user_id))

    # 按搜索类型过滤
    if search_type and search_type in ("channel", "global"):
        query = query.filter_by(search_type=search_type)

    # 按时间倒序排列并分页
    pagination = query.order_by(SearchHistory.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 构建返回数据
    history_list = []
    for record in pagination.items:
        history_data = {
            "id": record.id,
            "query": record.query,
            "search_type": record.search_type,
            "channel_id": record.channel_id,
            "filters": record.filters,
            "result_count": record.result_count,
            "created_at": record.created_at.isoformat(),
        }
        history_list.append(history_data)

    return (
        jsonify(
            {
                "search_history": history_list,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
            }
        ),
        200,
    )


@channels_bp.route("/search/history/<int:history_id>", methods=["DELETE"])
@jwt_required()
@require_permission("message.manage_history")
def delete_search_history(history_id):
    """
    删除指定的搜索历史记录
    ---
    tags:
      - Search
    security:
      - Bearer: []
    parameters:
      - in: path
        name: history_id
        type: integer
        required: true
        description: 搜索历史记录ID
        example: 1
    responses:
      200:
        description: 删除成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 记录不存在
      403:
        description: 权限不足
    """
    from flask_jwt_extended import get_jwt_identity

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 查找搜索历史记录
    history = SearchHistory.query.get(history_id)
    if not history:
        return jsonify({"error": "搜索历史记录不存在"}), 404

    # 验证权限（只能删除自己的搜索历史）
    if history.user_id != int(current_user_id):
        return jsonify({"error": "没有权限删除此记录"}), 403

    # 删除记录
    db.session.delete(history)
    db.session.commit()

    return jsonify({"message": "搜索历史记录删除成功"}), 200


@channels_bp.route("/search/history", methods=["DELETE"])
@jwt_required()
@require_permission("message.manage_history")
def clear_search_history():
    """
    清空用户的所有搜索历史记录
    ---
    tags:
      - Search
    security:
      - Bearer: []
    responses:
      200:
        description: 清空成功
        schema:
          type: object
          properties:
            message:
              type: string
            deleted_count:
              type: integer
      401:
        description: 未授权
    """
    from flask_jwt_extended import get_jwt_identity

    # 获取当前用户ID
    current_user_id = get_jwt_identity()

    # 删除用户的所有搜索历史记录
    deleted_count = SearchHistory.query.filter_by(user_id=int(current_user_id)).delete()
    db.session.commit()

    return (
        jsonify({"message": "搜索历史记录清空成功", "deleted_count": deleted_count}),
        200,
    )
