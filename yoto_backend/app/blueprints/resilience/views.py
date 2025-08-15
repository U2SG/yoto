"""
韧性配置管理API

提供熔断器、限流器、降级等韧性策略的动态配置接口
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from flasgger import swag_from
from . import resilience_bp
from app.core.permission.permission_resilience import (
    get_resilience_controller,
    set_rate_limit_config,
    set_circuit_breaker_config,
    set_degradation_config,
    get_rate_limit_status,
    get_circuit_breaker_state,
    get_all_resilience_configs,
    RateLimitConfig,
    CircuitBreakerConfig,
    DegradationConfig,
    RateLimitType,
    CircuitBreakerState,
    DegradationLevel,
)


@resilience_bp.route("/rate-limit", methods=["GET"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "获取限流器配置",
        "description": "获取指定限流器的配置信息",
        "parameters": [
            {
                "name": "name",
                "in": "query",
                "type": "string",
                "required": True,
                "description": "限流器名称",
            }
        ],
        "responses": {
            200: {
                "description": "获取成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "limit_type": {"type": "string"},
                        "max_requests": {"type": "integer"},
                        "time_window": {"type": "number"},
                        "multi_dimensional": {"type": "boolean"},
                        "user_id_limit": {"type": "integer"},
                        "server_id_limit": {"type": "integer"},
                        "ip_limit": {"type": "integer"},
                        "combined_limit": {"type": "integer"},
                    },
                },
            },
            404: {"description": "限流器不存在"},
        },
    }
)
def get_rate_limit_config():
    """获取限流器配置"""
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "限流器名称必填"}), 400

    status = get_rate_limit_status(name)
    if not status:
        return jsonify({"error": "限流器不存在"}), 404

    return jsonify(status), 200


@resilience_bp.route("/rate-limit", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "设置限流器配置",
        "description": "设置或更新限流器配置",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": "api_rate_limit"},
                        "enabled": {"type": "boolean", "example": True},
                        "limit_type": {
                            "type": "string",
                            "enum": ["token_bucket", "sliding_window", "fixed_window"],
                            "example": "token_bucket",
                        },
                        "max_requests": {"type": "integer", "example": 100},
                        "time_window": {"type": "number", "example": 60.0},
                        "multi_dimensional": {"type": "boolean", "example": True},
                        "user_id_limit": {"type": "integer", "example": 50},
                        "server_id_limit": {"type": "integer", "example": 200},
                        "ip_limit": {"type": "integer", "example": 100},
                        "combined_limit": {"type": "integer", "example": 300},
                    },
                    "required": ["name"],
                },
            }
        ],
        "responses": {
            200: {
                "description": "设置成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "config": {"type": "object"},
                    },
                },
            },
            400: {"description": "参数错误"},
            500: {"description": "设置失败"},
        },
    }
)
def set_rate_limit_config_api():
    """设置限流器配置"""
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "限流器名称必填"}), 400

    try:
        # 构建配置对象
        config_params = {
            "enabled": data.get("enabled", True),
            "limit_type": RateLimitType(data.get("limit_type", "token_bucket")),
            "max_requests": data.get("max_requests", 100),
            "time_window": data.get("time_window", 60.0),
            "burst_size": data.get("burst_size", 10),
            "tokens_per_second": data.get("tokens_per_second", 10.0),
            "multi_dimensional": data.get("multi_dimensional", False),
            "user_id_limit": data.get("user_id_limit", 50),
            "server_id_limit": data.get("server_id_limit", 200),
            "ip_limit": data.get("ip_limit", 100),
            "combined_limit": data.get("combined_limit", 300),
        }

        success = set_rate_limit_config(name, **config_params)

        if success:
            return (
                jsonify(
                    {
                        "message": "限流器配置设置成功",
                        "config": get_rate_limit_status(name),
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "限流器配置设置失败"}), 500

    except Exception as e:
        return jsonify({"error": f"配置错误: {str(e)}"}), 400


@resilience_bp.route("/circuit-breaker", methods=["GET"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "获取熔断器状态",
        "description": "获取指定熔断器的状态信息",
        "parameters": [
            {
                "name": "name",
                "in": "query",
                "type": "string",
                "required": True,
                "description": "熔断器名称",
            }
        ],
        "responses": {
            200: {
                "description": "获取成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "state": {"type": "string"},
                        "failure_count": {"type": "integer"},
                        "config": {"type": "object"},
                    },
                },
            },
            404: {"description": "熔断器不存在"},
        },
    }
)
def get_circuit_breaker_status():
    """获取熔断器状态"""
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "熔断器名称必填"}), 400

    status = get_circuit_breaker_state(name)
    if not status:
        return jsonify({"error": "熔断器不存在"}), 404

    return jsonify(status), 200


@resilience_bp.route("/circuit-breaker", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "设置熔断器配置",
        "description": "设置或更新熔断器配置",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": "api_circuit_breaker"},
                        "failure_threshold": {"type": "integer", "example": 5},
                        "recovery_timeout": {"type": "number", "example": 60.0},
                        "expected_exception": {
                            "type": "string",
                            "example": "Exception",
                        },
                        "monitor_interval": {"type": "number", "example": 10.0},
                        "state": {
                            "type": "string",
                            "enum": ["closed", "open", "half_open"],
                            "example": "closed",
                        },
                    },
                    "required": ["name"],
                },
            }
        ],
        "responses": {
            200: {
                "description": "设置成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "config": {"type": "object"},
                    },
                },
            },
            400: {"description": "参数错误"},
            500: {"description": "设置失败"},
        },
    }
)
def set_circuit_breaker_config_api():
    """设置熔断器配置"""
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "熔断器名称必填"}), 400

    try:
        # 构建配置对象
        config_params = {
            "failure_threshold": data.get("failure_threshold", 5),
            "recovery_timeout": data.get("recovery_timeout", 60.0),
            "expected_exception": data.get("expected_exception", "Exception"),
            "monitor_interval": data.get("monitor_interval", 10.0),
            "state": CircuitBreakerState(data.get("state", "closed")),
        }

        success = set_circuit_breaker_config(name, **config_params)

        if success:
            return (
                jsonify(
                    {
                        "message": "熔断器配置设置成功",
                        "config": get_circuit_breaker_state(name),
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "熔断器配置设置失败"}), 500

    except Exception as e:
        return jsonify({"error": f"配置错误: {str(e)}"}), 400


@resilience_bp.route("/degradation", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "设置降级配置",
        "description": "设置或更新降级配置",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": "api_degradation"},
                        "level": {
                            "type": "string",
                            "enum": ["none", "light", "medium", "heavy"],
                            "example": "none",
                        },
                        "fallback_function": {
                            "type": "string",
                            "example": "fallback_handler",
                        },
                        "timeout": {"type": "number", "example": 5.0},
                        "enabled": {"type": "boolean", "example": False},
                    },
                    "required": ["name"],
                },
            }
        ],
        "responses": {
            200: {
                "description": "设置成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "config": {"type": "object"},
                    },
                },
            },
            400: {"description": "参数错误"},
            500: {"description": "设置失败"},
        },
    }
)
def set_degradation_config_api():
    """设置降级配置"""
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "降级配置名称必填"}), 400

    try:
        # 构建配置对象
        config_params = {
            "level": DegradationLevel(data.get("level", "none")),
            "fallback_function": data.get("fallback_function", ""),
            "timeout": data.get("timeout", 5.0),
            "enabled": data.get("enabled", False),
        }

        success = set_degradation_config(name, **config_params)

        if success:
            return (
                jsonify(
                    {
                        "message": "降级配置设置成功",
                        "config": {
                            "name": name,
                            **config_params,
                            "level": config_params["level"].value,
                        },
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "降级配置设置失败"}), 500

    except Exception as e:
        return jsonify({"error": f"配置错误: {str(e)}"}), 400


@resilience_bp.route("/configs", methods=["GET"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "获取所有韧性配置",
        "description": "获取所有熔断器、限流器、降级配置的概览",
        "responses": {
            200: {
                "description": "获取成功",
                "schema": {
                    "type": "object",
                    "properties": {
                        "circuit_breakers": {"type": "object"},
                        "rate_limits": {"type": "object"},
                        "degradations": {"type": "object"},
                        "global_switches": {"type": "object"},
                    },
                },
            }
        },
    }
)
def get_all_configs():
    """获取所有韧性配置"""
    try:
        configs = get_all_resilience_configs()
        return jsonify(configs), 200
    except Exception as e:
        return jsonify({"error": f"获取配置失败: {str(e)}"}), 500


@resilience_bp.route("/cache/clear", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Resilience"],
        "summary": "清理配置缓存",
        "description": "清理韧性控制器的本地缓存，强制从数据源重新加载配置",
        "responses": {
            200: {
                "description": "清理成功",
                "schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                },
            }
        },
    }
)
def clear_cache():
    """清理配置缓存"""
    try:
        controller = get_resilience_controller()
        controller.clear_cache()
        return jsonify({"message": "配置缓存清理成功"}), 200
    except Exception as e:
        return jsonify({"error": f"清理缓存失败: {str(e)}"}), 500
