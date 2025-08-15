"""
简化的韧性配置管理API测试

直接测试API函数逻辑，避免JWT认证问题
"""

import pytest
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock
from app.blueprints.resilience.views import (
    get_rate_limit_config,
    set_rate_limit_config_api,
    get_circuit_breaker_status,
    set_circuit_breaker_config_api,
    set_degradation_config_api,
    get_all_configs,
    clear_cache,
)
from app.core.permission_resilience import (
    RateLimitConfig,
    CircuitBreakerConfig,
    DegradationConfig,
    RateLimitType,
    CircuitBreakerState,
    DegradationLevel,
)


class TestResilienceAPISimple:
    """简化的韧性配置管理API测试"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 创建模拟的Flask请求对象
        self.mock_request = MagicMock()
        self.mock_jsonify = MagicMock()

        # 模拟jsonify函数
        with patch("app.blueprints.resilience.views.jsonify", self.mock_jsonify):
            self.mock_jsonify.return_value = MagicMock()

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

            # 模拟请求参数
            self.mock_request.args.get.return_value = "test_limiter"

            # 调用API函数
            with patch("app.blueprints.resilience.views.request", self.mock_request):
                result = get_rate_limit_config()

            # 验证结果
            assert result[1] == 200  # 状态码
            self.mock_jsonify.assert_called_once()

    def test_get_rate_limit_config_missing_name(self):
        """测试获取限流器配置缺少名称参数"""
        # 模拟请求参数
        self.mock_request.args.get.return_value = None

        # 调用API函数
        with patch("app.blueprints.resilience.views.request", self.mock_request):
            result = get_rate_limit_config()

        # 验证结果
        assert result[1] == 400  # 状态码
        self.mock_jsonify.assert_called_once()

    def test_get_rate_limit_config_not_found(self):
        """测试获取不存在的限流器配置"""
        with patch("app.core.permission_resilience.get_rate_limit_status") as mock_get:
            mock_get.return_value = None

            # 模拟请求参数
            self.mock_request.args.get.return_value = "nonexistent"

            # 调用API函数
            with patch("app.blueprints.resilience.views.request", self.mock_request):
                result = get_rate_limit_config()

            # 验证结果
            assert result[1] == 404  # 状态码
            self.mock_jsonify.assert_called_once()

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

                # 模拟请求数据
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
                self.mock_request.get_json.return_value = config_data

                # 调用API函数
                with patch(
                    "app.blueprints.resilience.views.request", self.mock_request
                ):
                    result = set_rate_limit_config_api()

                # 验证结果
                assert result[1] == 200  # 状态码
                self.mock_jsonify.assert_called_once()

    def test_set_rate_limit_config_missing_name(self):
        """测试设置限流器配置缺少名称"""
        # 模拟请求数据
        config_data = {"enabled": True, "limit_type": "token_bucket"}
        self.mock_request.get_json.return_value = config_data

        # 调用API函数
        with patch("app.blueprints.resilience.views.request", self.mock_request):
            result = set_rate_limit_config_api()

        # 验证结果
        assert result[1] == 400  # 状态码
        self.mock_jsonify.assert_called_once()

    def test_set_rate_limit_config_failure(self):
        """测试设置限流器配置失败"""
        with patch("app.core.permission_resilience.set_rate_limit_config") as mock_set:
            mock_set.return_value = False

            # 模拟请求数据
            config_data = {"name": "test_limiter", "enabled": True}
            self.mock_request.get_json.return_value = config_data

            # 调用API函数
            with patch("app.blueprints.resilience.views.request", self.mock_request):
                result = set_rate_limit_config_api()

            # 验证结果
            assert result[1] == 500  # 状态码
            self.mock_jsonify.assert_called_once()

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

            # 模拟请求参数
            self.mock_request.args.get.return_value = "test_breaker"

            # 调用API函数
            with patch("app.blueprints.resilience.views.request", self.mock_request):
                result = get_circuit_breaker_status()

            # 验证结果
            assert result[1] == 200  # 状态码
            self.mock_jsonify.assert_called_once()

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

                # 模拟请求数据
                config_data = {
                    "name": "test_breaker",
                    "failure_threshold": 5,
                    "recovery_timeout": 60.0,
                    "state": "closed",
                }
                self.mock_request.get_json.return_value = config_data

                # 调用API函数
                with patch(
                    "app.blueprints.resilience.views.request", self.mock_request
                ):
                    result = set_circuit_breaker_config_api()

                # 验证结果
                assert result[1] == 200  # 状态码
                self.mock_jsonify.assert_called_once()

    def test_set_degradation_config_success(self):
        """测试设置降级配置成功"""
        with patch("app.core.permission_resilience.set_degradation_config") as mock_set:
            mock_set.return_value = True

            # 模拟请求数据
            config_data = {
                "name": "test_degradation",
                "level": "none",
                "enabled": False,
                "timeout": 5.0,
            }
            self.mock_request.get_json.return_value = config_data

            # 调用API函数
            with patch("app.blueprints.resilience.views.request", self.mock_request):
                result = set_degradation_config_api()

            # 验证结果
            assert result[1] == 200  # 状态码
            self.mock_jsonify.assert_called_once()

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

            # 调用API函数
            result = get_all_configs()

            # 验证结果
            assert result[1] == 200  # 状态码
            self.mock_jsonify.assert_called_once()

    def test_clear_cache_success(self):
        """测试清理缓存成功"""
        with patch(
            "app.core.permission_resilience.get_resilience_controller"
        ) as mock_get:
            mock_controller = MagicMock()
            mock_get.return_value = mock_controller

            # 调用API函数
            result = clear_cache()

            # 验证结果
            assert result[1] == 200  # 状态码
            self.mock_jsonify.assert_called_once()

            # 验证调用了clear_cache方法
            mock_controller.clear_cache.assert_called_once()

    def test_clear_cache_failure(self):
        """测试清理缓存失败"""
        with patch(
            "app.core.permission_resilience.get_resilience_controller"
        ) as mock_get:
            mock_get.side_effect = Exception("Cache error")

            # 调用API函数
            result = clear_cache()

            # 验证结果
            assert result[1] == 500  # 状态码
            self.mock_jsonify.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
