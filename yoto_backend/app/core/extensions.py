"""
Flask 扩展实例统一管理：
- db: SQLAlchemy
- migrate: Flask-Migrate
- jwt: Flask-JWT-Extended
- celery: Celery
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
celery = Celery()
