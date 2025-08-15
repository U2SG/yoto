#!/usr/bin/env python3
"""
Yoto Backend - Flask应用启动文件
"""

# 步骤1：确保monkey_patch是程序执行的第一行代码
import eventlet

eventlet.monkey_patch()

import os
from app import create_app
from app.ws import init_socketio, get_socketio


def main():
    """主函数 - 启动Flask应用"""
    # 获取配置名称，默认为development
    config_name = os.getenv("FLASK_ENV", "development")

    # 创建Flask应用实例
    app = create_app(config_name)

    # 初始化SocketIO
    socketio = init_socketio(app)

    # 获取端口，默认为5000
    port = int(os.getenv("PORT", 5000))

    # 获取主机地址，默认为0.0.0.0（允许外部访问）
    host = os.getenv("HOST", "0.0.0.0")

    # 获取调试模式，默认为True
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    print(f"Starting Yoto Backend on {host}:{port}")
    print(f"Environment: {config_name}")
    print(f"Debug mode: {debug}")
    print(f"WebSocket enabled: True")
    print(f"Control plane namespace: /control")

    # 使用eventlet服务器启动应用
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=debug)


if __name__ == "__main__":
    main()
