"""
社区管理相关 Celery 任务定义。
"""

from app.core.extensions import celery


@celery.task(name="tasks.on_user_join_server")
def on_user_join_server(user_id, server_id):
    """用户加入星球后的异步处理任务（接口预留）"""
    # TODO: 实现欢迎消息、统计更新等逻辑
    pass


@celery.task(name="tasks.generate_daily_report")
def generate_daily_report():
    """定时生成日报表任务（接口预留）"""
    # TODO: 实现报表生成逻辑
    pass
