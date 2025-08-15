#!/usr/bin/env python3
"""
权限系统控制平面启动脚本

启动统一的运维仪表盘，提供：
- 实时配置管理
- 性能监控可视化
- 系统状态查看
- 事件流监控
"""

import sys
import os
import argparse
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yoto_backend.app.control_plane import start_control_plane


def setup_logging(level=logging.INFO):
    """设置日志配置"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("control_plane.log")],
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动权限系统控制平面")
    parser.add_argument("--host", default="0.0.0.0", help="监听主机地址")
    parser.add_argument("--port", type=int, default=5001, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别",
    )

    args = parser.parse_args()

    # 设置日志级别
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)

    logger = logging.getLogger(__name__)
    logger.info(f"启动权限系统控制平面: http://{args.host}:{args.port}")

    try:
        start_control_plane(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("控制平面已停止")
    except Exception as e:
        logger.error(f"启动控制平面失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
