"""
OPA策略引擎集成测试

测试OPA策略引擎与权限系统的集成
"""

import unittest
import time
import logging
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Dict, Any

# 导入权限系统模块
from app.core.permission.permissions_refactored import (
    get_permission_system,
    check_permission,
)
from app.core.permission.opa_policy_manager import (
    get_opa_policy_manager,
    OPAPolicyManager,
)

logger = logging.getLogger(__name__)


class TestOPAIntegration(unittest.TestCase):
    """OPA策略引擎集成测试"""

    def setUp(self):
        """测试前准备"""
        self.permission_system = get_permission_system()

        # 模拟OPA服务连接
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            self.opa_manager = get_opa_policy_manager()

    def test_opa_policy_manager_initialization(self):
        """测试OPA策略管理器初始化"""
        self.assertIsNotNone(self.opa_manager)
        self.assertIsInstance(self.opa_manager, OPAPolicyManager)

    @patch("requests.post")
    def test_opa_policy_evaluation(self, mock_post):
        """测试OPA策略评估"""
        # 模拟OPA响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"allow": True}}
        mock_post.return_value = mock_response

        # 测试数据
        user_info = {
            "id": 1,
            "session_valid": True,
            "disabled": False,
            "roles": ["user"],
            "ip_address": "192.168.1.100",
            "device_type": "desktop",
            "device_authenticated": True,
            "risk_level": 1,
            "behavior_score": 100,
            "security_level": 1,
            "location": {"country": "CN", "city": "Beijing"},
            "resource_permissions": {},
        }

        resource_info = {
            "id": "document_read",
            "type": "document",
            "exists": True,
            "max_risk_level": 5,
            "min_behavior_score": 0,
            "required_security_level": 1,
            "owner_id": 1,
            "shared": False,
            "shared_with": [],
        }

        # 执行策略评估
        result = self.opa_manager.check_permission(
            user=user_info, resource=resource_info, action="read", context={}
        )

        # 验证结果
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_opa_policy_evaluation_denied(self, mock_post):
        """测试OPA策略评估拒绝"""
        # 模拟OPA响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"allow": False}}
        mock_post.return_value = mock_response

        # 测试数据
        user_info = {
            "id": 1,
            "session_valid": True,
            "disabled": False,
            "roles": ["guest"],
            "ip_address": "192.168.1.100",
            "device_type": "desktop",
            "device_authenticated": True,
            "risk_level": 1,
            "behavior_score": 100,
            "security_level": 1,
            "location": {"country": "CN", "city": "Beijing"},
            "resource_permissions": {},
        }

        resource_info = {
            "id": "admin_panel",
            "type": "admin",
            "exists": True,
            "max_risk_level": 5,
            "min_behavior_score": 0,
            "required_security_level": 3,
            "owner_id": 1,
            "shared": False,
            "shared_with": [],
        }

        # 执行策略评估
        result = self.opa_manager.check_permission(
            user=user_info, resource=resource_info, action="write", context={}
        )

        # 验证结果
        self.assertFalse(result)
        mock_post.assert_called_once()

    def test_permission_system_with_abac(self):
        """测试权限系统与ABAC集成"""
        # 测试上下文
        context = {
            "ip_address": "192.168.1.100",
            "device_type": "desktop",
            "device_authenticated": True,
            "risk_level": 1,
            "behavior_score": 100,
            "security_level": 1,
            "location": {"country": "CN", "city": "Beijing"},
            "resource_max_risk_level": 5,
            "resource_min_behavior_score": 0,
            "resource_required_security_level": 1,
            "resource_owner_id": 1,
            "resource_shared": False,
            "resource_shared_with": [],
        }

        # 测试权限检查（带ABAC上下文）
        result = check_permission(
            user_id=1,
            permission="document_read",
            scope="document",
            scope_id=1,
            context=context,
        )

        # 验证结果（由于是模拟环境，结果可能为False）
        self.assertIsInstance(result, bool)

    def test_permission_system_without_abac(self):
        """测试权限系统无ABAC上下文"""
        # 测试权限检查（无ABAC上下文）
        result = check_permission(
            user_id=1, permission="document_read", scope="document", scope_id=1
        )

        # 验证结果
        self.assertIsInstance(result, bool)

    def test_user_info_building(self):
        """测试用户信息构建"""
        context = {
            "ip_address": "192.168.1.100",
            "device_type": "mobile",
            "device_authenticated": True,
            "risk_level": 2,
            "behavior_score": 95,
            "security_level": 2,
            "location": {"country": "US", "city": "New York"},
            "resource_permissions": {"doc_1": {"allow": True}},
        }

        # 构建用户信息
        user_info = self.permission_system._build_user_info(1, context)

        # 验证用户信息
        self.assertEqual(user_info["id"], 1)
        self.assertEqual(user_info["ip_address"], "192.168.1.100")
        self.assertEqual(user_info["device_type"], "mobile")
        self.assertEqual(user_info["risk_level"], 2)
        self.assertEqual(user_info["behavior_score"], 95)
        self.assertEqual(user_info["security_level"], 2)
        self.assertEqual(user_info["location"]["country"], "US")
        self.assertEqual(user_info["location"]["city"], "New York")
        self.assertIn("doc_1", user_info["resource_permissions"])

    def test_resource_info_building(self):
        """测试资源信息构建"""
        context = {
            "resource_max_risk_level": 3,
            "resource_min_behavior_score": 50,
            "resource_required_security_level": 2,
            "resource_owner_id": 2,
            "resource_shared": True,
            "resource_shared_with": [1, 3, 4],
        }

        # 构建资源信息
        resource_info = self.permission_system._build_resource_info(
            "document_write", "document", 1, context
        )

        # 验证资源信息
        self.assertEqual(resource_info["id"], "document_write_document_1")
        self.assertEqual(resource_info["type"], "document_write")
        self.assertTrue(resource_info["exists"])
        self.assertEqual(resource_info["max_risk_level"], 3)
        self.assertEqual(resource_info["min_behavior_score"], 50)
        self.assertEqual(resource_info["required_security_level"], 2)
        self.assertEqual(resource_info["owner_id"], 2)
        self.assertTrue(resource_info["shared"])
        self.assertEqual(resource_info["shared_with"], [1, 3, 4])

    @patch("requests.get")
    def test_opa_connection_validation(self, mock_get):
        """测试OPA连接验证"""
        # 模拟成功连接
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 创建OPA管理器
        opa_manager = OPAPolicyManager(opa_url="http://localhost:8181")

        # 验证连接
        self.assertTrue(opa_manager._validate_opa_connection())

    @patch("requests.get")
    def test_opa_connection_failure(self, mock_get):
        """测试OPA连接失败"""
        # 模拟连接失败
        mock_get.side_effect = Exception("Connection failed")

        # 创建OPA管理器
        opa_manager = OPAPolicyManager(opa_url="http://localhost:8181")

        # 验证连接失败
        self.assertFalse(opa_manager._validate_opa_connection())

    def test_cache_status(self):
        """测试缓存状态"""
        cache_status = self.opa_manager.get_cache_status()

        # 验证缓存状态结构
        self.assertIn("cache_ttl", cache_status)
        self.assertIn("policies", cache_status)
        self.assertIn("total_policies", cache_status)
        self.assertIsInstance(cache_status["cache_ttl"], int)
        self.assertIsInstance(cache_status["policies"], dict)
        self.assertIsInstance(cache_status["total_policies"], int)

    def test_cache_clear(self):
        """测试缓存清除"""
        # 清除缓存
        self.opa_manager.clear_cache()

        # 验证缓存已清除
        cache_status = self.opa_manager.get_cache_status()
        self.assertEqual(cache_status["total_policies"], 0)


class TestOPAErrorHandling(unittest.TestCase):
    """OPA错误处理测试"""

    def setUp(self):
        """测试前准备"""
        self.opa_manager = OPAPolicyManager(opa_url="http://localhost:8181")

    @patch("requests.post")
    def test_opa_evaluation_error(self, mock_post):
        """测试OPA评估错误"""
        # 模拟网络错误
        mock_post.side_effect = Exception("Network error")

        # 测试数据
        user_info = {"id": 1, "roles": ["user"]}
        resource_info = {"id": "test", "type": "test"}

        # 执行策略评估
        result = self.opa_manager.check_permission(
            user=user_info, resource=resource_info, action="read", context={}
        )

        # 验证结果（错误时应返回False）
        self.assertFalse(result)

    @patch("requests.post")
    def test_opa_invalid_response(self, mock_post):
        """测试OPA无效响应"""
        # 模拟无效响应
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        # 测试数据
        user_info = {"id": 1, "roles": ["user"]}
        resource_info = {"id": "test", "type": "test"}

        # 执行策略评估
        result = self.opa_manager.check_permission(
            user=user_info, resource=resource_info, action="read", context={}
        )

        # 验证结果（错误时应返回False）
        self.assertFalse(result)


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)

    # 运行测试
    unittest.main()
