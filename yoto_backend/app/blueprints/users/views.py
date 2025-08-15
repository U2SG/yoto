from . import users_bp
from flask import jsonify
from flask import request
from app.blueprints.auth.models import User
from app.core.pydantic_schemas import UserSchema
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.blueprints.users.models import Friendship
from app.blueprints.channels.models import Message
from app.core.extensions import db
from app.blueprints.channels.models import Channel


# 示例路由，后续实现
@users_bp.route("/users", methods=["GET"])
def list_users():
    """
    获取用户列表
    ---
    description: |
      获取用户列表，支持分页参数 page, per_page。
    tags:
      - Users
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
        description: 用户列表
        schema:
          type: object
          properties:
            users:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  username:
                    type: string
            page:
              type: integer
            per_page:
              type: integer
            total:
              type: integer
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    pagination = User.query.paginate(page=page, per_page=per_page, error_out=False)
    users = [UserSchema.from_orm(u).dict() for u in pagination.items]
    return (
        jsonify(
            {
                "users": users,
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
            }
        ),
        200,
    )


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """
    获取用户详情
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: 用户ID
        example: 1
    responses:
      200:
        description: 用户详情
        schema:
          type: object
          properties:
            id:
              type: integer
            username:
              type: string
      404:
        description: 用户不存在
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify(UserSchema.from_orm(user).dict()), 200


# 新增RESTful路由：添加好友
@users_bp.route("/users/<int:user_id>/friends", methods=["POST"])
@jwt_required()
def add_friend_restful(user_id):
    """
    添加好友（RESTful补充，推荐使用）
    ---
    tags:
      - Users
    security:
      - Bearer: []
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: 要添加的用户ID
        example: 1
    responses:
      201:
        description: 添加好友成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 不能添加自己为好友
      401:
        description: 未授权
      404:
        description: 用户不存在
      409:
        description: 已是好友
    """
    return add_friend(user_id)


# 原有接口加注释：建议使用新RESTful接口
@users_bp.route("/users/<int:user_id>/add_friend", methods=["POST"])
@jwt_required()
def add_friend(user_id):
    """
    添加好友（已废弃，建议使用POST /users/<user_id>/friends）
    ---
    tags:
      - Users
    security:
      - Bearer: []
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: 要添加的用户ID
        example: 1
    responses:
      201:
        description: 添加好友成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 不能添加自己为好友
      401:
        description: 未授权
      404:
        description: 用户不存在
      409:
        description: 已是好友
    """
    current_user_id = get_jwt_identity()
    if current_user_id == user_id:
        return jsonify({"error": "不能添加自己为好友"}), 400
    from app.blueprints.auth.models import User

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    exists = (
        Friendship.query.filter_by(user_id=current_user_id, friend_id=user_id).first()
        or Friendship.query.filter_by(
            user_id=user_id, friend_id=current_user_id
        ).first()
    )
    if exists:
        return jsonify({"error": "已是好友"}), 409
    db.session.add(Friendship(user_id=current_user_id, friend_id=user_id))
    db.session.add(Friendship(user_id=user_id, friend_id=current_user_id))
    db.session.commit()
    return jsonify({"message": "添加好友成功"}), 201


@users_bp.route("/users/friends", methods=["GET"])
@jwt_required()
def list_friends():
    """
    获取好友列表
    ---
    tags:
      - Users
    security:
      - Bearer: []
    responses:
      200:
        description: 好友列表
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              username:
                type: string
      401:
        description: 未授权
    """
    current_user_id = get_jwt_identity()
    # 查找所有好友id
    friend_ids = [
        f.friend_id for f in Friendship.query.filter_by(user_id=current_user_id).all()
    ]
    from app.blueprints.auth.models import User

    friends = User.query.filter(User.id.in_(friend_ids)).all() if friend_ids else []
    return jsonify([UserSchema.from_orm(u).dict() for u in friends]), 200


# 新增RESTful路由：删除好友
@users_bp.route("/users/<int:user_id>/friends/<int:friend_id>", methods=["DELETE"])
@jwt_required()
def remove_friend_restful(user_id, friend_id):
    """
    删除好友（RESTful补充，推荐使用）
    ---
    tags:
      - Users
    security:
      - Bearer: []
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: 当前用户ID
        example: 1
      - in: path
        name: friend_id
        type: integer
        required: true
        description: 要删除的好友ID
        example: 2
    responses:
      200:
        description: 删除好友成功
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: 未授权
      404:
        description: 好友关系不存在
    """
    # 兼容原有remove_friend逻辑，friend_id为目标用户
    # 只允许当前登录用户操作自己的好友
    current_user_id = get_jwt_identity()
    if current_user_id != user_id:
        return jsonify({"error": "无权限操作"}), 403
    # 复用原有逻辑
    # 这里friend_id是目标好友
    f1 = Friendship.query.filter_by(user_id=user_id, friend_id=friend_id).first()
    f2 = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id).first()
    if not f1 and not f2:
        return jsonify({"error": "好友关系不存在"}), 404
    if f1:
        db.session.delete(f1)
    if f2:
        db.session.delete(f2)
    db.session.commit()
    return jsonify({"message": "删除好友成功"}), 200


@users_bp.route("/users/<int:user_id>/remove_friend", methods=["POST"])
@jwt_required()
def remove_friend(user_id):
    """
    删除好友（已废弃，建议使用DELETE /users/<user_id>/friends/<friend_id>）
    ---
    tags:
      - Users
    security:
      - Bearer: []
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: 要删除的好友用户ID
        example: 1
    responses:
      200:
        description: 删除好友成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 不能删除自己
      401:
        description: 未授权
      404:
        description: 不是好友
    """
    current_user_id = get_jwt_identity()
    if current_user_id == user_id:
        return jsonify({"error": "不能删除自己"}), 400
    f1 = Friendship.query.filter_by(user_id=current_user_id, friend_id=user_id).first()
    f2 = Friendship.query.filter_by(user_id=user_id, friend_id=current_user_id).first()
    if not f1 and not f2:
        return jsonify({"error": "不是好友"}), 404
    if f1:
        db.session.delete(f1)
    if f2:
        db.session.delete(f2)
    db.session.commit()
    return jsonify({"message": "删除好友成功"}), 200


@users_bp.route("/users/mentions", methods=["GET"])
@jwt_required()
def get_user_mentions():
    """
    获取当前用户被@的消息列表
    ---
    tags:
      - Users
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
        description: 每页数量（默认20，最大100）
        example: 20
      - in: query
        name: channel_id
        type: integer
        description: 频道ID过滤（可选）
        example: 1
    responses:
      200:
        description: 被@消息列表
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
                  content:
                    type: string
                  type:
                    type: string
                  created_at:
                    type: string
                  channel_name:
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
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)  # 限制最大100
    channel_id = request.args.get("channel_id", type=int)

    # 构建查询条件：查找mentions字段包含当前用户ID的消息
    query = Message.query.filter(
        Message.mentions.isnot(None),
        Message.mentions.contains([int(user_id)]),
        Message.is_deleted == False,
    )

    # 如果指定了频道ID，添加频道过滤
    if channel_id:
        query = query.filter(Message.channel_id == channel_id)

    # 按创建时间倒序排列
    query = query.order_by(Message.created_at.desc())

    # 分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 构建返回数据
    messages = []
    for msg in pagination.items:
        # 获取发送者信息
        sender = User.query.get(msg.user_id)
        # 获取频道信息
        channel = Channel.query.get(msg.channel_id)

        message_data = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": msg.user_id,
            "username": sender.username if sender else "Unknown",
            "content": msg.content,
            "type": msg.type,
            "created_at": msg.created_at.isoformat(),
            "channel_name": channel.name if channel else "Unknown",
        }
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
