from flask import Blueprint

channels_bp = Blueprint("channels", __name__)

from . import views  # 导入视图，确保路由注册
