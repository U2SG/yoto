from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from . import views  # 导入视图，确保路由注册
