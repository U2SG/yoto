import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI", "mysql+pymysql://root:gt123456@localhost:3306/yoto_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Celery配置
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )

    # Redis配置
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")  # 使用IP地址避免DNS问题
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

    # Redis集群配置 - 修复'dict' object has no attribute 'name'错误
    REDIS_CLUSTER_NODES = [{"host": REDIS_HOST, "port": REDIS_PORT}]

    # 降级到单节点模式的配置
    REDIS_SINGLE_NODE_CONFIG = {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": REDIS_DB,
        "decode_responses": True,
    }

    # WebSocket配置
    WEBSOCKET_CONFIG = {
        "cors_allowed_origins": "*",
        "async_mode": "eventlet",
        "ping_timeout": 60,
        "ping_interval": 25,
        "max_http_buffer_size": 1e8,
        "max_message_size": 1e8,
        "transports": ["websocket", "polling"],
        "max_connections": 1000,
        "connection_timeout": 300,
        "health_check_interval": 30,
    }


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = "dev-secret-key-change-in-production"
    JWT_SECRET_KEY = "dev-jwt-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_EXPIRES = False  # 开发环境下token永不过期
    JWT_REFRESH_TOKEN_EXPIRES = False

    # 高级优化配置
    ADVANCED_OPTIMIZATION_CONFIG = {
        # 连接优化
        "connection_pool_size": 100,
        "socket_timeout": 0.5,
        "socket_connect_timeout": 0.5,
        "retry_on_timeout": True,
        "health_check_interval": 15,
        # 锁优化
        "lock_timeout": 2.0,
        "lock_retry_interval": 0.02,
        "lock_retry_count": 2,
        # 缓存优化
        "local_cache_size": 2000,
        "distributed_cache_ttl": 600,
        "compression_threshold": 512,
        # 批量操作优化
        "batch_size": 200,
        "batch_timeout": 1.0,
        "max_concurrent_batches": 10,
        # 预加载优化
        "preload_enabled": True,
        "preload_batch_size": 50,
        "preload_ttl": 1800,
        # 智能失效优化
        "smart_invalidation": True,
        "invalidation_batch_size": 100,
        "delayed_invalidation_delay": 5,
        # 性能监控
        "enable_advanced_monitoring": True,
        "monitoring_interval": 30,
        "performance_thresholds": {
            "local_cache_hit_rate": 0.95,
            "distributed_cache_hit_rate": 0.85,
            "lock_success_rate": 0.98,
            "avg_response_time_ms": 5.0,
        },
    }


class ProductionConfig(Config):
    DEBUG = False

    # 高级优化配置
    ADVANCED_OPTIMIZATION_CONFIG = {
        # 连接优化
        "connection_pool_size": 200,
        "socket_timeout": 1.0,
        "socket_connect_timeout": 1.0,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        # 锁优化
        "lock_timeout": 1.0,
        "lock_retry_interval": 0.05,
        "lock_retry_count": 3,
        # 缓存优化
        "local_cache_size": 5000,
        "distributed_cache_ttl": 3600,
        "compression_threshold": 1024,
        # 批量操作优化
        "batch_size": 500,
        "batch_timeout": 2.0,
        "max_concurrent_batches": 20,
        # 预加载优化
        "preload_enabled": False,
        "preload_batch_size": 100,
        "preload_ttl": 3600,
        # 智能失效优化
        "smart_invalidation": True,
        "invalidation_batch_size": 200,
        "delayed_invalidation_delay": 2,
        # 性能监控
        "enable_advanced_monitoring": True,
        "monitoring_interval": 60,
        "performance_thresholds": {
            "local_cache_hit_rate": 0.98,
            "distributed_cache_hit_rate": 0.90,
            "lock_success_rate": 0.99,
            "avg_response_time_ms": 2.0,
        },
        "batch_processing_interval": 1,
        "max_staleness": 0.1,
    }


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRES = False  # 测试环境下token永不过期
    JWT_REFRESH_TOKEN_EXPIRES = False

    # MySQL特定配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "echo": False,  # 设置为False减少日志输出
    }


class MySQLTestingConfig(Config):
    """MySQL测试配置，用于真实数据库环境测试"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "MYSQL_TEST_URI", "mysql+pymysql://root:gt123456@localhost:3306/yoto_test"
    )
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "mysql-test-secret"
    JWT_SECRET_KEY = "mysql-test-jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRES = False  # 测试环境下token永不过期
    JWT_REFRESH_TOKEN_EXPIRES = False

    # MySQL特定配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "echo": False,  # 设置为False减少日志输出
    }
