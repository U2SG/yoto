"""
韧性配置管理API测试

测试熔断器、限流器、降级等韧性策略的API端点
"""

import pytest
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock
from app import create_app
from app.core.permission_resilience import (
    RateLimitConfig,
    CircuitBreakerConfig,
    DegradationConfig,
    RateLimitType,
    CircuitBreakerState,
    DegradationLevel,
)


class TestResilienceAPI:
    """测试韧性配置管理API"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.app = create_app("testing")
        self.client = self.app.test_client()

        # 直接mock JWT装饰器函数
        import flask_jwt_extended

        flask_jwt_extended.verify_jwt_in_request = lambda: True
        flask_jwt_extended.get_jwt_identity = lambda: "test_user"

    def test_get_rate_limit_config_success(self):
        """测试获取限流器配置成功"""
        with patch("app.core.permission_resilience.get_rate_limit_status") as mock_get:
            mock_get.return_value = {
                "name": "test_limiter",
                "enabled": True,
                "limit_type": "token_bucket",
                "max_requests": 100,
                "time_window": 60.0,
                "multi_dimensional": True,
                "user_id_limit": 50,
                "server_id_limit": 200,
                "ip_limit": 100,
                "combined_limit": 300,
            }

            response = self.client.get("/api/resilience/rate-limit?name=test_limiter")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["name"] == "test_limiter"
            assert data["enabled"] is True
            assert data["multi_dimensional"] is True

    def test_get_rate_limit_config_missing_name(self):
        """测试获取限流器配置缺少名称参数"""
        response = self.client.get("/api/resilience/rate-limit")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "限流器名称必填" in data["error"]

    def test_get_rate_limit_config_not_found(self):
        """测试获取不存在的限流器配置"""
        with patch("app.core.permission_resilience.get_rate_limit_status") as mock_get:
            mock_get.return_value = None

            response = self.client.get("/api/resilience/rate-limit?name=nonexistent")
            assert response.status_code == 404

            data = json.loads(response.data)
            assert "error" in data
            assert "限流器不存在" in data["error"]

    def test_set_rate_limit_config_success(self):
        """测试设置限流器配置成功"""
        with patch("app.core.permission_resilience.set_rate_limit_config") as mock_set:
            mock_set.return_value = True

            with patch(
                "app.core.permission_resilience.get_rate_limit_status"
            ) as mock_get:
                mock_get.return_value = {
                    "name": "test_limiter",
                    "enabled": True,
                    "multi_dimensional": True,
                }

                config_data = {
                    "name": "test_limiter",
                    "enabled": True,
                    "limit_type": "token_bucket",
                    "max_requests": 100,
                    "time_window": 60.0,
                    "multi_dimensional": True,
                    "user_id_limit": 50,
                    "server_id_limit": 200,
                    "ip_limit": 100,
                    "combined_limit": 300,
                }

                response = self.client.post(
                    "/api/resilience/rate-limit",
                    data=json.dumps(config_data),
                    content_type="application/json",
                )

                assert response.status_code == 200

                data = json.loads(response.data)
                assert "message" in data
                assert "配置设置成功" in data["message"]
                assert "config" in data

    def test_set_rate_limit_config_missing_name(self):
        """测试设置限流器配置缺少名称"""
        config_data = {"enabled": True, "limit_type": "token_bucket"}

        response = self.client.post(
            "/api/resilience/rate-limit",
            data=json.dumps(config_data),
            content_type="application/json",
        )

        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "限流器名称必填" in data["error"]

    def test_set_rate_limit_config_failure(self):
        """测试设置限流器配置失败"""
        with patch("app.core.permission_resilience.set_rate_limit_config") as mock_set:
            mock_set.return_value = False

            config_data = {"name": "test_limiter", "enabled": True}

            response = self.client.post(
                "/api/resilience/rate-limit",
                data=json.dumps(config_data),
                content_type="application/json",
            )

            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data
            assert "配置设置失败" in data["error"]

    def test_get_circuit_breaker_status_success(self):
        """测试获取熔断器状态成功"""
        with patch(
            "app.core.permission_resilience.get_circuit_breaker_state"
        ) as mock_get:
            mock_get.return_value = {
                "name": "test_breaker",
                "state": "closed",
                "failure_count": 0,
                "config": {"failure_threshold": 5, "recovery_timeout": 60.0},
            }

            response = self.client.get(
                "/api/resilience/circuit-breaker?name=test_breaker"
            )
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["name"] == "test_breaker"
            assert data["state"] == "closed"
            assert data["failure_count"] == 0

    def test_set_circuit_breaker_config_success(self):
        """测试设置熔断器配置成功"""
        with patch(
            "app.core.permission_resilience.set_circuit_breaker_config"
        ) as mock_set:
            mock_set.return_value = True

            with patch(
                "app.core.permission_resilience.get_circuit_breaker_state"
            ) as mock_get:
                mock_get.return_value = {
                    "name": "test_breaker",
                    "state": "closed",
                    "config": {},
                }

                config_data = {
                    "name": "test_breaker",
                    "failure_threshold": 5,
                    "recovery_timeout": 60.0,
                    "state": "closed",
                }

                response = self.client.post(
                    "/api/resilience/circuit-breaker",
                    data=json.dumps(config_data),
                    content_type="application/json",
                )

                assert response.status_code == 200

                data = json.loads(response.data)
                assert "message" in data
                assert "配置设置成功" in data["message"]

    def test_set_degradation_config_success(self):
        """测试设置降级配置成功"""
        with patch("app.core.permission_resilience.set_degradation_config") as mock_set:
            mock_set.return_value = True

            config_data = {
                "name": "test_degradation",
                "level": "none",
                "enabled": False,
                "timeout": 5.0,
            }

            response = self.client.post(
                "/api/resilience/degradation",
                data=json.dumps(config_data),
                content_type="application/json",
            )

            assert response.status_code == 200

            data = json.loads(response.data)
            assert "message" in data
            assert "配置设置成功" in data["message"]

    def test_get_all_configs_success(self):
        """测试获取所有配置成功"""
        with patch(
            "app.core.permission_resilience.get_all_resilience_configs"
        ) as mock_get:
            mock_get.return_value = {
                "circuit_breakers": {"test_breaker": {}},
                "rate_limits": {"test_limiter": {}},
                "degradations": {"test_degradation": {}},
                "global_switches": {"test_switch": "true"},
            }

            response = self.client.get("/api/resilience/configs")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "circuit_breakers" in data
            assert "rate_limits" in data
            assert "degradations" in data
            assert "global_switches" in data

    def test_clear_cache_success(self):
        """测试清理缓存成功"""
        with patch(
            "app.core.permission_resilience.get_resilience_controller"
        ) as mock_get:
            mock_controller = MagicMock()
            mock_get.return_value = mock_controller

            response = self.client.post("/api/resilience/cache/clear")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "message" in data
            assert "缓存清理成功" in data["message"]

            # 验证调用了clear_cache方法
            mock_controller.clear_cache.assert_called_once()

    def test_clear_cache_failure(self):
        """测试清理缓存失败"""
        with patch(
            "app.core.permission_resilience.get_resilience_controller"
        ) as mock_get:
            mock_get.side_effect = Exception("Cache error")

            response = self.client.post("/api/resilience/cache/clear")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data
            assert "清理缓存失败" in data["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
