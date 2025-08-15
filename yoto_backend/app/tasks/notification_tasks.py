"""
通知推送相关 Celery 任务定义。
"""

from app.core.extensions import celery


@celery.task(name="tasks.send_push_notification")
def send_push_notification(user_ids, title, body):
    """异步推送通知任务（接口预留）"""
    # TODO: 实现推送逻辑
    pass
