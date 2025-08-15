"""
媒体处理相关 Celery 任务定义。
"""

from app.core.extensions import celery


@celery.task(name="tasks.process_uploaded_image")
def process_uploaded_image(image_id):
    """异步图片处理任务（接口预留）"""
    # TODO: 实现图片处理逻辑
    pass
