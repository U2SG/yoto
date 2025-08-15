"""
Redis集群配置示例

说明如何在测试和生产环境中配置Redis集群
"""

# ==================== 测试环境配置 ====================

# 测试环境 - 使用本地Redis集群（6379, 6380, 6381）
TEST_REDIS_CONFIG = {
    "startup_nodes": [
        {"host": "localhost", "port": 6379},
        {"host": "localhost", "port": 6380},
        {"host": "localhost", "port": 6381},
    ],
    "additional_nodes": [
        {"host": "localhost", "port": 6380},
        {"host": "localhost", "port": 6381},
    ],
}

# ==================== 生产环境配置 ====================

# 生产环境 - 使用实际的Redis集群
PRODUCTION_REDIS_CONFIG = {
    "startup_nodes": [
        {"host": "redis-cluster-1.prod.com", "port": 6379},
        {"host": "redis-cluster-2.prod.com", "port": 6379},
        {"host": "redis-cluster-3.prod.com", "port": 6379},
    ],
    "additional_nodes": [
        {"host": "redis-cluster-4.prod.com", "port": 6379},
        {"host": "redis-cluster-5.prod.com", "port": 6379},
        {"host": "redis-cluster-6.prod.com", "port": 6379},
    ],
}

# ==================== 开发环境配置 ====================

# 开发环境 - 使用单节点Redis
DEV_REDIS_CONFIG = {
    "startup_nodes": [{"host": "localhost", "port": 6379}],
    "additional_nodes": [],
}

# ==================== 配置使用示例 ====================


def get_redis_config(environment="dev"):
    """
    根据环境获取Redis配置

    参数:
        environment (str): 环境类型 ('dev', 'test', 'prod')

    返回:
        dict: Redis配置
    """
    configs = {
        "dev": DEV_REDIS_CONFIG,
        "test": TEST_REDIS_CONFIG,
        "prod": PRODUCTION_REDIS_CONFIG,
    }

    return configs.get(environment, DEV_REDIS_CONFIG)


# ==================== Flask应用配置示例 ====================


def configure_redis_for_flask(app, environment="dev"):
    """
    为Flask应用配置Redis

    参数:
        app: Flask应用实例
        environment (str): 环境类型
    """
    redis_config = get_redis_config(environment)
    app.config["REDIS_CONFIG"] = redis_config

    # 设置Redis URL（用于降级到单节点）
    if environment == "dev":
        app.config["REDIS_URL"] = "redis://localhost:6379/0"
    elif environment == "test":
        app.config["REDIS_URL"] = "redis://localhost:6379/0"
    else:
        app.config["REDIS_URL"] = "redis://redis-cluster-1.prod.com:6379/0"


# ==================== 使用说明 ====================

"""
使用方法：

1. 测试环境配置：
   app.config['REDIS_CONFIG'] = TEST_REDIS_CONFIG

2. 生产环境配置：
   app.config['REDIS_CONFIG'] = PRODUCTION_REDIS_CONFIG

3. 开发环境配置：
   app.config['REDIS_CONFIG'] = DEV_REDIS_CONFIG

4. 动态配置：
   configure_redis_for_flask(app, 'test')  # 测试环境
   configure_redis_for_flask(app, 'prod')  # 生产环境

注意事项：
- 测试环境使用本地端口6379、6380、6381
- 生产环境使用实际的Redis集群地址
- 开发环境使用单节点Redis
- 所有配置都支持降级到单节点模式
"""
