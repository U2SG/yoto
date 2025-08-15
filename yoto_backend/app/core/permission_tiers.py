"""
权限分级模块

定义不同级别的权限验证策略，实现分层权限管理
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)


class PermissionTier(Enum):
    """权限级别"""

    BASIC = "basic"  # 基础权限 - 可客户端验证
    STANDARD = "standard"  # 标准权限 - 可客户端缓存
    ADVANCED = "advanced"  # 高级权限 - 需要服务器验证
    CRITICAL = "critical"  # 关键权限 - 强制服务器验证


@dataclass
class PermissionDefinition:
    """权限定义"""

    name: str
    tier: PermissionTier
    description: str
    client_cache_ttl: int = 3600  # 客户端缓存时间
    require_server_validation: bool = True
    risk_level: str = "low"  # low, medium, high, critical


class PermissionTierManager:
    """权限分级管理器"""

    def __init__(self):
        self.permission_definitions = {}
        self.tier_configs = {
            PermissionTier.BASIC: {
                "client_cache_enabled": True,
                "server_validation_required": False,
                "cache_ttl": 7200,  # 2小时
                "description": "基础权限，可完全在客户端验证",
            },
            PermissionTier.STANDARD: {
                "client_cache_enabled": True,
                "server_validation_required": True,
                "cache_ttl": 3600,  # 1小时
                "description": "标准权限，客户端缓存但需要服务器验证",
            },
            PermissionTier.ADVANCED: {
                "client_cache_enabled": False,
                "server_validation_required": True,
                "cache_ttl": 0,
                "description": "高级权限，必须服务器验证",
            },
            PermissionTier.CRITICAL: {
                "client_cache_enabled": False,
                "server_validation_required": True,
                "cache_ttl": 0,
                "description": "关键权限，强制服务器验证且不缓存",
            },
        }

        self._initialize_permission_definitions()

    def _initialize_permission_definitions(self):
        """初始化权限定义"""
        # 基础权限 - 可客户端验证
        basic_permissions = [
            ("read_server", "读取服务器信息"),
            ("read_channel", "读取频道信息"),
            ("read_message", "读取消息"),
            ("view_member_list", "查看成员列表"),
            ("search_message", "搜索消息"),
            ("view_server_info", "查看服务器信息"),
            ("view_channel_list", "查看频道列表"),
            ("view_role_list", "查看角色列表"),
            ("view_permission_list", "查看权限列表"),
            ("view_audit_log", "查看审计日志"),
        ]

        # 标准权限 - 可客户端缓存
        standard_permissions = [
            ("send_message", "发送消息"),
            ("edit_message", "编辑消息"),
            ("delete_message", "删除消息"),
            ("react_message", "消息反应"),
            ("pin_message", "置顶消息"),
            ("join_channel", "加入频道"),
            ("leave_channel", "离开频道"),
            ("view_channel_history", "查看频道历史"),
            ("upload_file", "上传文件"),
            ("download_file", "下载文件"),
        ]

        # 高级权限 - 需要服务器验证
        advanced_permissions = [
            ("manage_channel", "管理频道"),
            ("manage_role", "管理角色"),
            ("assign_role", "分配角色"),
            ("kick_member", "踢出成员"),
            ("ban_member", "封禁成员"),
            ("invite_member", "邀请成员"),
            ("manage_permission", "管理权限"),
            ("view_analytics", "查看分析数据"),
            ("manage_integration", "管理集成"),
            ("manage_webhook", "管理Webhook"),
        ]

        # 关键权限 - 强制服务器验证
        critical_permissions = [
            ("manage_server", "管理服务器"),
            ("delete_server", "删除服务器"),
            ("transfer_ownership", "转移所有权"),
            ("manage_admin", "管理管理员"),
            ("view_sensitive_data", "查看敏感数据"),
            ("manage_security", "管理安全设置"),
            ("manage_billing", "管理账单"),
            ("access_api", "访问API"),
            ("manage_backup", "管理备份"),
            ("system_admin", "系统管理员"),
        ]

        # 注册权限定义
        for perm_name, description in basic_permissions:
            self.register_permission(perm_name, PermissionTier.BASIC, description)

        for perm_name, description in standard_permissions:
            self.register_permission(perm_name, PermissionTier.STANDARD, description)

        for perm_name, description in advanced_permissions:
            self.register_permission(perm_name, PermissionTier.ADVANCED, description)

        for perm_name, description in critical_permissions:
            self.register_permission(perm_name, PermissionTier.CRITICAL, description)

    def register_permission(self, name: str, tier: PermissionTier, description: str):
        """注册权限定义"""
        config = self.tier_configs[tier]

        self.permission_definitions[name] = PermissionDefinition(
            name=name,
            tier=tier,
            description=description,
            client_cache_ttl=config["cache_ttl"],
            require_server_validation=config["server_validation_required"],
        )

    def get_permission_tier(self, permission_name: str) -> Optional[PermissionTier]:
        """获取权限级别"""
        if permission_name in self.permission_definitions:
            return self.permission_definitions[permission_name].tier
        return None

    def can_cache_in_client(self, permission_name: str) -> bool:
        """判断权限是否可以在客户端缓存"""
        if permission_name not in self.permission_definitions:
            return False

        config = self.tier_configs[self.permission_definitions[permission_name].tier]
        return config["client_cache_enabled"]

    def requires_server_validation(self, permission_name: str) -> bool:
        """判断权限是否需要服务器验证"""
        if permission_name not in self.permission_definitions:
            return True  # 默认需要服务器验证

        config = self.tier_configs[self.permission_definitions[permission_name].tier]
        return config["server_validation_required"]

    def get_cache_ttl(self, permission_name: str) -> int:
        """获取权限的缓存TTL"""
        if permission_name not in self.permission_definitions:
            return 0

        return self.permission_definitions[permission_name].client_cache_ttl

    def get_permissions_by_tier(self, tier: PermissionTier) -> List[str]:
        """获取指定级别的所有权限"""
        return [
            name
            for name, definition in self.permission_definitions.items()
            if definition.tier == tier
        ]

    def get_tier_statistics(self) -> Dict:
        """获取权限级别统计"""
        stats = {}
        for tier in PermissionTier:
            permissions = self.get_permissions_by_tier(tier)
            stats[tier.value] = {
                "count": len(permissions),
                "permissions": permissions,
                "config": self.tier_configs[tier],
            }
        return stats


class TieredPermissionValidator:
    """分级权限验证器"""

    def __init__(self, tier_manager: PermissionTierManager):
        self.tier_manager = tier_manager
        self.validation_stats = {
            "basic_validations": 0,
            "standard_validations": 0,
            "advanced_validations": 0,
            "critical_validations": 0,
            "client_cache_hits": 0,
            "server_validations": 0,
        }
        # 添加客户端缓存
        self.client_cache = {}
        self.cache_ttl = 3600  # 默认1小时TTL

    def validate_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict = None,
    ) -> Dict:
        """分级权限验证"""
        tier = self.tier_manager.get_permission_tier(permission_name)

        if tier == PermissionTier.BASIC:
            return self._validate_basic_permission(
                user_id, permission_name, resource_type, resource_id, user_context
            )
        elif tier == PermissionTier.STANDARD:
            return self._validate_standard_permission(
                user_id, permission_name, resource_type, resource_id, user_context
            )
        elif tier == PermissionTier.ADVANCED:
            return self._validate_advanced_permission(
                user_id, permission_name, resource_type, resource_id, user_context
            )
        elif tier == PermissionTier.CRITICAL:
            return self._validate_critical_permission(
                user_id, permission_name, resource_type, resource_id, user_context
            )
        else:
            # 未知权限，默认服务器验证
            return self._validate_unknown_permission(
                user_id, permission_name, resource_type, resource_id, user_context
            )

    def _validate_basic_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict,
    ) -> Dict:
        """验证基础权限 - 完全客户端验证"""
        self.validation_stats["basic_validations"] += 1

        # 基础权限可以在客户端完全验证
        allowed = self._check_basic_permission_rules(
            user_id, permission_name, resource_type, resource_id
        )

        # 基础权限也可以缓存结果
        result = {
            "allowed": allowed,
            "reason": "客户端基础权限验证",
            "tier": PermissionTier.BASIC.value,
            "client_validated": True,
            "server_validated": False,
            "cached": False,
        }

        # 缓存基础权限结果
        self._cache_permission_result(
            user_id, permission_name, resource_type, resource_id, result
        )

        return result

    def _validate_standard_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict,
    ) -> Dict:
        """验证标准权限 - 客户端缓存 + 服务器验证"""
        self.validation_stats["standard_validations"] += 1

        # 检查客户端缓存
        cached_result = self._check_client_cache(
            user_id, permission_name, resource_type, resource_id
        )
        if cached_result:
            self.validation_stats["client_cache_hits"] += 1
            return {
                "allowed": cached_result["allowed"],
                "reason": "客户端缓存验证",
                "tier": PermissionTier.STANDARD.value,
                "client_validated": True,
                "server_validated": False,
                "cached": True,
            }

        # 需要服务器验证
        server_result = self._validate_with_server(
            user_id, permission_name, resource_type, resource_id
        )
        self.validation_stats["server_validations"] += 1

        # 缓存结果
        if server_result["allowed"]:
            self._cache_permission_result(
                user_id, permission_name, resource_type, resource_id, server_result
            )

        return {
            **server_result,
            "tier": PermissionTier.STANDARD.value,
            "client_validated": False,
            "server_validated": True,
            "cached": False,
        }

    def _validate_advanced_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict,
    ) -> Dict:
        """验证高级权限 - 必须服务器验证"""
        self.validation_stats["advanced_validations"] += 1
        self.validation_stats["server_validations"] += 1

        # 高级权限必须服务器验证
        server_result = self._validate_with_server(
            user_id, permission_name, resource_type, resource_id
        )

        return {
            **server_result,
            "tier": PermissionTier.ADVANCED.value,
            "client_validated": False,
            "server_validated": True,
            "cached": False,
        }

    def _validate_critical_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict,
    ) -> Dict:
        """验证关键权限 - 强制服务器验证"""
        self.validation_stats["critical_validations"] += 1
        self.validation_stats["server_validations"] += 1

        # 关键权限强制服务器验证，不缓存
        server_result = self._validate_with_server(
            user_id, permission_name, resource_type, resource_id
        )

        return {
            **server_result,
            "tier": PermissionTier.CRITICAL.value,
            "client_validated": False,
            "server_validated": True,
            "cached": False,
            "critical": True,
        }

    def _validate_unknown_permission(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        user_context: Dict,
    ) -> Dict:
        """验证未知权限 - 默认服务器验证"""
        self.validation_stats["server_validations"] += 1

        server_result = self._validate_with_server(
            user_id, permission_name, resource_type, resource_id
        )

        return {
            **server_result,
            "tier": "unknown",
            "client_validated": False,
            "server_validated": True,
            "cached": False,
        }

    def _check_basic_permission_rules(
        self, user_id: str, permission_name: str, resource_type: str, resource_id: str
    ) -> bool:
        """检查基础权限规则"""
        # 简单的客户端验证规则
        if permission_name == "read_server":
            return True  # 所有用户都可以读取服务器信息
        elif permission_name == "read_channel":
            return True  # 所有用户都可以读取频道信息
        elif permission_name == "read_message":
            return True  # 所有用户都可以读取消息
        elif permission_name == "view_member_list":
            return True  # 所有用户都可以查看成员列表

        return False

    def _check_client_cache(
        self, user_id: str, permission_name: str, resource_type: str, resource_id: str
    ) -> Optional[Dict]:
        """检查客户端缓存"""
        cache_key = f"{user_id}:{permission_name}:{resource_type}:{resource_id}"

        if cache_key in self.client_cache:
            cached = self.client_cache[cache_key]
            if time.time() < cached["expires_at"]:
                logger.info(f"客户端缓存命中: {cache_key}")
                return cached["result"]
            else:
                # 缓存过期，删除
                del self.client_cache[cache_key]

        return None

    def _cache_permission_result(
        self,
        user_id: str,
        permission_name: str,
        resource_type: str,
        resource_id: str,
        result: Dict,
    ):
        """缓存权限结果"""
        cache_key = f"{user_id}:{permission_name}:{resource_type}:{resource_id}"

        # 获取权限的缓存TTL
        ttl = self.tier_manager.get_cache_ttl(permission_name)
        if ttl > 0:  # 只有TTL大于0的权限才缓存
            self.client_cache[cache_key] = {
                "result": result,
                "expires_at": time.time() + ttl,
                "cached_at": time.time(),
            }
            logger.info(f"缓存权限结果: {cache_key} (TTL: {ttl}s)")

    def _validate_with_server(
        self, user_id: str, permission_name: str, resource_type: str, resource_id: str
    ) -> Dict:
        """与服务器验证权限"""
        # 这里应该实现实际的服务器验证逻辑
        # 暂时返回模拟结果
        return {"allowed": True, "reason": "服务器验证通过"}

    def get_validation_stats(self) -> Dict:
        """获取验证统计"""
        total = sum(
            [
                self.validation_stats["basic_validations"],
                self.validation_stats["standard_validations"],
                self.validation_stats["advanced_validations"],
                self.validation_stats["critical_validations"],
            ]
        )

        if total > 0:
            client_rate = (
                self.validation_stats["basic_validations"]
                + self.validation_stats["client_cache_hits"]
            ) / total
            server_rate = self.validation_stats["server_validations"] / total
        else:
            client_rate = server_rate = 0

        return {
            **self.validation_stats,
            "total_validations": total,
            "client_validation_rate": client_rate,
            "server_validation_rate": server_rate,
        }

    def cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []

        for key, cached in self.client_cache.items():
            if current_time >= cached["expires_at"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.client_cache[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total_cache = len(self.client_cache)
        valid_cache = sum(
            1
            for cached in self.client_cache.values()
            if time.time() < cached["expires_at"]
        )

        # 计算总验证次数
        total_validations = sum(
            [
                self.validation_stats["basic_validations"],
                self.validation_stats["standard_validations"],
                self.validation_stats["advanced_validations"],
                self.validation_stats["critical_validations"],
            ]
        )

        return {
            "total_cache": total_cache,
            "valid_cache": valid_cache,
            "expired_cache": total_cache - valid_cache,
            "cache_hit_rate": self.validation_stats["client_cache_hits"]
            / max(total_validations, 1),
        }


# 全局实例
_tier_manager = None
_tiered_validator = None


def get_tier_manager() -> PermissionTierManager:
    """获取权限分级管理器"""
    global _tier_manager
    if _tier_manager is None:
        _tier_manager = PermissionTierManager()
    return _tier_manager


def get_tiered_validator() -> TieredPermissionValidator:
    """获取分级权限验证器"""
    global _tiered_validator
    if _tiered_validator is None:
        tier_manager = get_tier_manager()
        _tiered_validator = TieredPermissionValidator(tier_manager)
    return _tiered_validator
