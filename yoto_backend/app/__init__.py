# 在应用创建之前进行eventlet monkey patching
import eventlet

eventlet.monkey_patch()

from flask import Flask
from config import (
    DevelopmentConfig,
    TestingConfig,
    MySQLTestingConfig,
    ProductionConfig,
)
from app.core.extensions import db, migrate, jwt, celery
from flasgger import Swagger
import os
from dotenv import load_dotenv

# 导入所有模型以确保它们被注册到SQLAlchemy元数据中
from app.blueprints.auth.models import User
from app.blueprints.roles.models import (
    Role,
    UserRole,
    RolePermission,
    Permission,
    PermissionAuditLog,
)
from app.blueprints.servers.models import Server, ServerMember
from app.blueprints.channels.models import Channel, Message, Category, ChannelMember
from app.blueprints.users.models import Friendship

# 注册蓝图
from app.blueprints.auth import auth_bp
from app.blueprints.servers import servers_bp
from app.blueprints.channels import channels_bp
from app.blueprints.roles import roles_bp
from app.blueprints.users import users_bp
from app.blueprints.admin import admin_bp
from app.blueprints.admin import audit_bp
from app.blueprints.resilience import resilience_bp
from app.blueprints.control_plane import control_plane_bp

# 导入权限系统模块
from app.core.permission import initialize_permission_platform
from app.core.permission.permissions_refactored import (
    warm_up_cache,
    register_permission,
)
from app.ws import init_socketio

# 导入韧性模块
from app.core.permission.permission_resilience import resilience

# 导入高级优化模块
from app.core.permission.advanced_optimization import advanced_optimization_ext
from app.core.permission.hybrid_permission_cache import (
    hybrid_cache,
)  # Import the instance

# 加载.env文件
load_dotenv()

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Yoto 后台管理 API",
        "description": "Yoto 社区后台管理接口文档，供超级管理员和开发者使用。",
        "contact": {
            "responsibleOrganization": "Yoto",
            "responsibleDeveloper": "Yoto Team",
            "email": "admin@yoto.com",
            "url": "https://yoto.com",
        },
        "termsOfService": "https://yoto.com/terms",
        "version": "1.0.0",
    },
    "host": "localhost:5000",  # 部署时可自动替换
    "basePath": "/api",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT认证，格式: Bearer <token>",
        }
    },
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # 所有路由
            "model_filter": lambda tag: True,  # 所有模型
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",  # 仅开发环境下生效
    "swagger_ui_config": {
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "defaultModelRendering": "model",
        "displayRequestDuration": True,
        "showExtensions": True,
    },
}


def create_app(config_name="development"):
    """应用工厂函数"""
    app = Flask(__name__)

    # 根据配置名称选择配置类
    if config_name == "testing":
        config_class = TestingConfig
    elif config_name == "mysql_testing":
        config_class = MySQLTestingConfig
    elif config_name == "production":
        config_class = ProductionConfig
    else:
        config_class = DevelopmentConfig

    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    celery.conf.update(app.config)

    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(servers_bp, url_prefix="/api")
    app.register_blueprint(channels_bp, url_prefix="/api")
    app.register_blueprint(roles_bp, url_prefix="/api")
    app.register_blueprint(users_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(audit_bp, url_prefix="/api")
    app.register_blueprint(resilience_bp)
    app.register_blueprint(control_plane_bp)

    # 【核心修改】按照依赖顺序初始化扩展
    # 1. 韧性模块，创建并提供Redis客户端
    resilience.init_app(app)

    # 2. 混合缓存模块，依赖Redis客户端
    hybrid_cache.init_app(app)

    # 3. 高级优化模块，依赖Redis客户端和缓存
    advanced_optimization_ext.init_app(app)

    # 初始化权限平台（显式依赖注入）
    with app.app_context():
        if not initialize_permission_platform():
            raise RuntimeError("权限平台初始化失败")

    # 权限缓存预热（仅在非测试环境下）
    if config_name != "testing":
        with app.app_context():
            warm_up_cache()

    # 初始化WebSocket
    from app.ws import init_socketio

    init_socketio(app)

    # 仅开发/测试环境下启用默认Swagger UI
    if config_name in ("development", "testing"):
        Swagger(app, template=swagger_template, config=swagger_config)
    else:
        # 生产环境禁用默认Swagger UI
        Swagger(
            app, template=swagger_template, config={"swagger_ui": False, "specs": []}
        )

    # 注册Swagger UI访问权限 - 延迟注册，避免数据库连接问题
    def register_swagger_permission():
        try:
            with app.app_context():
                register_permission(
                    "admin.view_swagger",
                    group="admin",
                    description="访问Swagger UI权限",
                )
        except Exception:
            # 在测试或开发环境中可能没有数据库连接，忽略错误
            pass

    # 延迟注册权限
    register_swagger_permission()

    return app


def make_celery(app=None):
    app = app or create_app()
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
