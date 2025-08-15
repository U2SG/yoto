from flask import Blueprint

servers_bp = Blueprint("servers", __name__)

from . import views  # 导入视图，确保路由注册
