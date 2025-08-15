from flask import Blueprint

roles_bp = Blueprint("roles", __name__)

from . import views  # 导入视图，确保路由注册
