from flask import Blueprint

users_bp = Blueprint("users", __name__)

from . import views  # 导入视图，确保路由注册
