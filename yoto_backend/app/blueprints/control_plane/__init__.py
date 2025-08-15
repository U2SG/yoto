"""
控制平面蓝图

提供权限系统的运维仪表盘功能，包括：
- 系统状态监控
- 配置管理
- 实时事件流
- 性能分析
"""

from flask import Blueprint

control_plane_bp = Blueprint("control_plane", __name__, url_prefix="/control")

from . import views, websocket
