"""
客户端验证增强模块

实现本地权限验证和规则引擎，减少服务器验证压力
"""

import time
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ValidationRuleType(Enum):
    """验证规则类型"""

    PERMISSION_LEVEL = "permission_level"
    RESOURCE_OWNER = "resource_owner"
    TIME_BASED = "time_based"
    LOCATION_BASED = "location_based"
    CUSTOM_RULE = "custom_rule"


@dataclass
class ValidationRule:
    """验证规则"""

    rule_id: str
    rule_type: ValidationRuleType
    conditions: Dict
    action: str  # allow, deny, require_server_check
    priority: int = 0
    description: str = ""


class ClientSideValidator:
    """客户端验证器"""

    def __init__(self):
        self.rules = []
        self.cached_validations = {}
        self.validation_stats = {
            "total_validations": 0,
            "cache_hits": 0,
            "server_checks": 0,
            "local_validations": 0,
        }

    def add_rule(self, rule: ValidationRule):
        """添加验证规则"""
        self.rules.append(rule)
        # 按优先级排序
        self.rules.sort(key=lambda x: x.priority, reverse=True)
        logger.info(f"添加验证规则: {rule.rule_id} ({rule.rule_type.value})")

    def validate_permission_locally(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        user_context: Dict = None,
    ) -> Tuple[bool, str, bool]:
        """
        本地验证权限
        返回: (是否允许, 原因, 是否需要服务器验证)
        """
        self.validation_stats["total_validations"] += 1

        # 检查缓存
        cache_key = self._generate_cache_key(
            user_id, resource_type, resource_id, action
        )
        if cache_key in self.cached_validations:
            cached = self.cached_validations[cache_key]
            if time.time() < cached["expires_at"]:
                self.validation_stats["cache_hits"] += 1
                return cached["result"], cached["reason"], cached["require_server"]

        # 执行规则验证
        result, reason, require_server = self._execute_rules(
            user_id, resource_type, resource_id, action, user_context
        )

        # 缓存结果
        self.cached_validations[cache_key] = {
            "result": result,
            "reason": reason,
            "require_server": require_server,
            "expires_at": time.time() + 300,  # 5分钟缓存
        }

        if require_server:
            self.validation_stats["server_checks"] += 1
        else:
            self.validation_stats["local_validations"] += 1

        return result, reason, require_server

    def _execute_rules(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        user_context: Dict = None,
    ) -> Tuple[bool, str, bool]:
        """执行验证规则"""
        user_context = user_context or {}

        for rule in self.rules:
            if self._match_rule(
                rule, user_id, resource_type, resource_id, action, user_context
            ):
                if rule.action == "allow":
                    return True, f"规则 {rule.rule_id} 允许访问", False
                elif rule.action == "deny":
                    return False, f"规则 {rule.rule_id} 拒绝访问", False
                elif rule.action == "require_server_check":
                    return False, f"规则 {rule.rule_id} 要求服务器验证", True

        # 默认需要服务器验证
        return False, "无匹配规则，需要服务器验证", True

    def _match_rule(
        self,
        rule: ValidationRule,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        user_context: Dict,
    ) -> bool:
        """检查规则是否匹配"""
        conditions = rule.conditions

        # 检查用户ID
        if "user_id" in conditions:
            if isinstance(conditions["user_id"], list):
                if user_id not in conditions["user_id"]:
                    return False
            elif conditions["user_id"] != user_id:
                return False

        # 检查资源类型
        if "resource_type" in conditions:
            if isinstance(conditions["resource_type"], list):
                if resource_type not in conditions["resource_type"]:
                    return False
            elif conditions["resource_type"] != resource_type:
                return False

        # 检查资源ID
        if "resource_id" in conditions:
            if isinstance(conditions["resource_id"], list):
                if resource_id not in conditions["resource_id"]:
                    return False
            elif conditions["resource_id"] != resource_id:
                return False

        # 检查操作
        if "action" in conditions:
            if isinstance(conditions["action"], list):
                if action not in conditions["action"]:
                    return False
            elif conditions["action"] != action:
                return False

        # 检查时间规则
        if rule.rule_type == ValidationRuleType.TIME_BASED:
            if not self._check_time_condition(conditions):
                return False

        # 检查位置规则
        if rule.rule_type == ValidationRuleType.LOCATION_BASED:
            if not self._check_location_condition(conditions, user_context):
                return False

        # 检查自定义规则
        if rule.rule_type == ValidationRuleType.CUSTOM_RULE:
            if not self._check_custom_condition(conditions, user_context):
                return False

        return True

    def _check_time_condition(self, conditions: Dict) -> bool:
        """检查时间条件"""
        current_time = time.time()
        current_hour = time.localtime(current_time).tm_hour

        # 检查时间范围
        if "time_range" in conditions:
            start_hour, end_hour = conditions["time_range"]
            if not (start_hour <= current_hour <= end_hour):
                return False

        # 检查工作日
        if "workdays_only" in conditions and conditions["workdays_only"]:
            weekday = time.localtime(current_time).tm_wday
            if weekday >= 5:  # 周六日
                return False

        return True

    def _check_location_condition(self, conditions: Dict, user_context: Dict) -> bool:
        """检查位置条件"""
        user_location = user_context.get("location")
        if not user_location:
            return True  # 没有位置信息，跳过检查

        # 检查IP白名单
        if "allowed_ips" in conditions:
            user_ip = user_context.get("ip")
            if user_ip and user_ip not in conditions["allowed_ips"]:
                return False

        # 检查地理位置
        if "allowed_regions" in conditions:
            user_region = user_context.get("region")
            if user_region and user_region not in conditions["allowed_regions"]:
                return False

        return True

    def _check_custom_condition(self, conditions: Dict, user_context: Dict) -> bool:
        """检查自定义条件"""
        # 检查用户角色
        if "required_roles" in conditions:
            user_roles = user_context.get("roles", [])
            required_roles = conditions["required_roles"]
            if not any(role in user_roles for role in required_roles):
                return False

        # 检查用户状态
        if "user_status" in conditions:
            user_status = user_context.get("status")
            if user_status != conditions["user_status"]:
                return False

        # 检查设备类型
        if "device_type" in conditions:
            device_type = user_context.get("device_type")
            if device_type != conditions["device_type"]:
                return False

        return True

    def _generate_cache_key(
        self, user_id: str, resource_type: str, resource_id: str, action: str
    ) -> str:
        """生成缓存键"""
        key_data = f"{user_id}:{resource_type}:{resource_id}:{action}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []

        for key, cached in self.cached_validations.items():
            if current_time >= cached["expires_at"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cached_validations[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期验证缓存")

    def get_validation_stats(self) -> Dict:
        """获取验证统计"""
        total = self.validation_stats["total_validations"]
        if total > 0:
            cache_hit_rate = self.validation_stats["cache_hits"] / total
            local_rate = self.validation_stats["local_validations"] / total
            server_rate = self.validation_stats["server_checks"] / total
        else:
            cache_hit_rate = local_rate = server_rate = 0

        return {
            **self.validation_stats,
            "cache_hit_rate": cache_hit_rate,
            "local_validation_rate": local_rate,
            "server_check_rate": server_rate,
            "cached_validations": len(self.cached_validations),
            "active_rules": len(self.rules),
        }


class RuleEngine:
    """规则引擎"""

    def __init__(self):
        self.validators = {}
        self.rule_templates = {}

    def create_validator(self, name: str) -> ClientSideValidator:
        """创建验证器"""
        validator = ClientSideValidator()
        self.validators[name] = validator
        return validator

    def get_validator(self, name: str) -> Optional[ClientSideValidator]:
        """获取验证器"""
        return self.validators.get(name)

    def add_rule_template(self, template_name: str, template: Dict):
        """添加规则模板"""
        self.rule_templates[template_name] = template
        logger.info(f"添加规则模板: {template_name}")

    def create_rule_from_template(self, template_name: str, **kwargs) -> ValidationRule:
        """从模板创建规则"""
        if template_name not in self.rule_templates:
            raise ValueError(f"规则模板不存在: {template_name}")

        template = self.rule_templates[template_name]
        rule_data = template.copy()
        rule_data.update(kwargs)

        return ValidationRule(
            rule_id=rule_data["rule_id"],
            rule_type=ValidationRuleType(rule_data["rule_type"]),
            conditions=rule_data["conditions"],
            action=rule_data["action"],
            priority=rule_data.get("priority", 0),
            description=rule_data.get("description", ""),
        )

    def setup_default_rules(self, validator: ClientSideValidator):
        """设置默认规则"""
        # 超级管理员规则
        super_admin_rule = ValidationRule(
            rule_id="super_admin_access",
            rule_type=ValidationRuleType.PERMISSION_LEVEL,
            conditions={
                "user_id": ["superadmin", "admin"],
                "action": ["read", "write", "delete", "admin"],
            },
            action="allow",
            priority=100,
            description="超级管理员拥有所有权限",
        )
        validator.add_rule(super_admin_rule)

        # 工作时间规则
        work_time_rule = ValidationRule(
            rule_id="work_time_restriction",
            rule_type=ValidationRuleType.TIME_BASED,
            conditions={"time_range": [9, 18], "workdays_only": True},  # 9点到18点
            action="require_server_check",
            priority=50,
            description="工作时间外需要服务器验证",
        )
        validator.add_rule(work_time_rule)

        # 只读用户规则
        read_only_rule = ValidationRule(
            rule_id="read_only_users",
            rule_type=ValidationRuleType.CUSTOM_RULE,
            conditions={"user_id": ["alice", "bob", "charlie"], "action": ["read"]},
            action="allow",
            priority=30,
            description="普通用户只能读取",
        )
        validator.add_rule(read_only_rule)

        logger.info("已设置默认验证规则")


# 全局实例
_rule_engine = None


def get_rule_engine() -> RuleEngine:
    """获取规则引擎"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
