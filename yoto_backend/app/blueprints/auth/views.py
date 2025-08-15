from . import auth_bp
from flask import request, jsonify
from app.core.extensions import db
from app.blueprints.auth.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.core.pydantic_schemas import UserSchema
from flasgger import swag_from


# 登录API
@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """
    用户登录
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              example: alice
            password:
              type: string
              example: 123456
    responses:
      200:
        description: 登录成功
        schema:
          type: object
          properties:
            message:
              type: string
            user_id:
              type: integer
            access_token:
              type: string
      400:
        description: 参数错误
      401:
        description: 用户名或密码错误
    """
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "用户名或密码错误"}), 401
    access_token = create_access_token(identity=str(user.id))
    return (
        jsonify(
            {"message": "登录成功", "user_id": user.id, "access_token": access_token}
        ),
        200,
    )


@auth_bp.route("/auth/register", methods=["POST"])
@swag_from(
    {
        "tags": ["Auth"],
        "summary": "用户注册",
        "description": "注册新用户，用户名唯一。",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "example": "alice"},
                        "password": {"type": "string", "example": "123456"},
                    },
                    "required": ["username", "password"],
                },
            }
        ],
        "responses": {
            200: {
                "description": "注册成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                    },
                },
            },
            409: {"description": "用户名已存在"},
            400: {"description": "参数错误"},
        },
    }
)
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 409
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return (
        jsonify({"message": "注册成功", "user": UserSchema.from_orm(user).dict()}),
        201,
    )


@auth_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    """
    获取当前用户信息
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    responses:
      200:
        description: 用户信息
        schema:
          type: object
          properties:
            id:
              type: integer
            username:
              type: string
      401:
        description: 未授权
      404:
        description: 用户不存在
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify(UserSchema.from_orm(user).dict()), 200


@auth_bp.route("/auth/profile", methods=["PATCH"])
@jwt_required()
def update_profile():
    """
    更新用户资料
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            username:
              type: string
              example: new_username
    responses:
      200:
        description: 更新成功
        schema:
          type: object
          properties:
            id:
              type: integer
            username:
              type: string
      401:
        description: 未授权
      404:
        description: 用户不存在
      409:
        description: 用户名已存在
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    data = request.get_json() or {}
    new_username = data.get("username")
    if new_username:
        if User.query.filter_by(username=new_username).first():
            return jsonify({"error": "用户名已存在"}), 409
        user.username = new_username
        db.session.commit()
    return jsonify(UserSchema.from_orm(user).dict()), 200


@auth_bp.route("/auth/change_password", methods=["PATCH"])
@jwt_required()
def change_password():
    """
    修改密码
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - old_password
            - new_password
          properties:
            old_password:
              type: string
              example: old123
            new_password:
              type: string
              example: new123
    responses:
      200:
        description: 密码修改成功
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: 参数错误
      401:
        description: 原密码错误或未授权
      404:
        description: 用户不存在
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    data = request.get_json() or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    if not old_password or not new_password:
        return jsonify({"error": "原密码和新密码必填"}), 400
    if not check_password_hash(user.password_hash, old_password):
        return jsonify({"error": "原密码错误"}), 401
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "密码修改成功"}), 200


@auth_bp.route("/auth/reset_password", methods=["POST"])
def reset_password():
    """
    重置密码
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - new_password
          properties:
            username:
              type: string
              example: alice
            new_password:
              type: string
              example: new123
    responses:
      200:
        description: 密码重置成功
        schema:
          type: object
          properties:
            message:
              type: string
            user:
              type: object
              properties:
                id:
                  type: integer
                username:
                  type: string
      400:
        description: 参数错误
      404:
        description: 用户不存在
    """
    data = request.get_json() or {}
    username = data.get("username")
    new_password = data.get("new_password")
    if not username or not new_password:
        return jsonify({"error": "用户名和新密码必填"}), 400
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return (
        jsonify({"message": "密码重置成功", "user": UserSchema.from_orm(user).dict()}),
        200,
    )


@auth_bp.route("/auth/login/wechat", methods=["POST"])
def login_wechat():
    """
    微信登录
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - wechat_openid
          properties:
            wechat_openid:
              type: string
              example: wx123456789
    responses:
      200:
        description: 微信登录成功
        schema:
          type: object
          properties:
            message:
              type: string
            user:
              type: object
              properties:
                id:
                  type: integer
                username:
                  type: string
            access_token:
              type: string
      400:
        description: 参数错误
    """
    data = request.get_json() or {}
    openid = data.get("wechat_openid")
    if not openid:
        return jsonify({"error": "wechat_openid 必填"}), 400
    user = User.query.filter_by(username=openid).first()
    if not user:
        import uuid

        user = User(
            username=openid, password_hash=generate_password_hash(str(uuid.uuid4()))
        )
        db.session.add(user)
        db.session.commit()
    access_token = create_access_token(identity=user.id)
    return (
        jsonify(
            {
                "message": "微信登录成功",
                "user": UserSchema.from_orm(user).dict(),
                "access_token": access_token,
            }
        ),
        200,
    )
