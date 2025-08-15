"""
权限轮询检查模块

实现客户端权限变更的实时检测和同步：
- 定期检查权限变更
- 检测权限冲突
- 实时同步到服务器
- 变更通知机制
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class PollingStatus(Enum):
    """轮询状态"""

    IDLE = "idle"
    CHECKING = "checking"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class PermissionSnapshot:
    """权限快照"""

    user_id: str
    permissions: Dict[str, bool]  # permission_name -> has_permission
    timestamp: float
    hash: str  # 权限状态的哈希值


class PermissionPoller:
    """权限轮询检查器"""

    def __init__(self, sync_manager, app):
        self.sync_manager = sync_manager
        self.app = app
        self.polling_interval = 10  # 10秒检查一次
        self.last_snapshots: Dict[str, PermissionSnapshot] = {}
        self.current_snapshots: Dict[str, PermissionSnapshot] = {}

        # 轮询统计
        self.polling_stats = {
            "total_checks": 0,
            "changes_detected": 0,
            "last_check_time": 0,
            "avg_check_time": 0,
        }

        # 轮询线程
        self.polling_thread = None
        self.running = False

        # 回调函数
        self.on_permission_change: Optional[Callable] = None
        self.on_conflict_detected: Optional[Callable] = None

        # 启动轮询线程
        self._start_polling_thread()

    def _start_polling_thread(self):
        """启动轮询线程"""
        self.running = True
        self.polling_thread = threading.Thread(target=self._polling_worker, daemon=True)
        self.polling_thread.start()
        logger.info("权限轮询线程已启动")

    def _polling_worker(self):
        """轮询工作线程"""
        while self.running:
            try:
                with self.app.app_context():
                    self._check_permission_changes()
                time.sleep(self.polling_interval)
            except Exception as e:
                logger.error(f"轮询线程错误: {e}")
                time.sleep(5)

    def _check_permission_changes(self):
        """检查权限变更"""
        start_time = time.time()
        self.polling_stats["total_checks"] += 1

        try:
            # 获取当前权限快照
            current_snapshots = self._get_current_permission_snapshots()

            # 检测变更
            changes_detected = []
            for user_id, current_snapshot in current_snapshots.items():
                if user_id in self.last_snapshots:
                    last_snapshot = self.last_snapshots[user_id]

                    # 比较权限变更
                    changes = self._compare_permissions(last_snapshot, current_snapshot)
                    if changes:
                        changes_detected.extend(changes)
                        self.polling_stats["changes_detected"] += len(changes)

                        # 记录变更
                        for change in changes:
                            self._record_permission_change(change)

                # 更新快照
                self.last_snapshots[user_id] = current_snapshot

            # 更新统计
            check_time = time.time() - start_time
            self.polling_stats["avg_check_time"] = (
                self.polling_stats["avg_check_time"]
                * (self.polling_stats["total_checks"] - 1)
                + check_time
            ) / self.polling_stats["total_checks"]
            self.polling_stats["last_check_time"] = time.time()

            if changes_detected:
                logger.info(f"检测到 {len(changes_detected)} 个权限变更")

                # 触发回调
                if self.on_permission_change:
                    self.on_permission_change(changes_detected)

        except Exception as e:
            logger.error(f"权限变更检查失败: {e}")

    def _get_current_permission_snapshots(self) -> Dict[str, PermissionSnapshot]:
        """获取当前权限快照"""
        snapshots = {}

        try:
            from app.blueprints.auth.models import User
            from app.blueprints.roles.models import (
                UserRole,
                Role,
                RolePermission,
                Permission,
            )
            from app.core.extensions import db
            from flask import current_app

            # 确保在应用上下文中运行
            if not current_app:
                logger.warning("不在Flask应用上下文中，跳过权限快照获取")
                return snapshots

            # 获取所有用户
            users = User.query.all()

            for user in users:
                permissions = {}

                # 获取用户的所有权限
                user_roles = UserRole.query.filter_by(user_id=user.id).all()
                for user_role in user_roles:
                    role = Role.query.get(user_role.role_id)
                    if role:
                        role_permissions = RolePermission.query.filter_by(
                            role_id=role.id
                        ).all()
                        for role_permission in role_permissions:
                            permission = Permission.query.get(
                                role_permission.permission_id
                            )
                            if permission:
                                permissions[permission.name] = True

                # 创建快照
                permissions_str = json.dumps(permissions, sort_keys=True)
                snapshot_hash = hashlib.md5(permissions_str.encode()).hexdigest()

                snapshot = PermissionSnapshot(
                    user_id=user.username,
                    permissions=permissions,
                    timestamp=time.time(),
                    hash=snapshot_hash,
                )

                snapshots[user.username] = snapshot

        except Exception as e:
            logger.error(f"获取权限快照失败: {e}")

        return snapshots

    def _compare_permissions(
        self, last_snapshot: PermissionSnapshot, current_snapshot: PermissionSnapshot
    ) -> List[Dict]:
        """比较权限变更"""
        changes = []

        # 获取所有权限名称
        all_permissions = set(last_snapshot.permissions.keys()) | set(
            current_snapshot.permissions.keys()
        )

        for permission_name in all_permissions:
            last_has_permission = last_snapshot.permissions.get(permission_name, False)
            current_has_permission = current_snapshot.permissions.get(
                permission_name, False
            )

            if last_has_permission != current_has_permission:
                change = {
                    "user_id": current_snapshot.user_id,
                    "permission_name": permission_name,
                    "old_value": last_has_permission,
                    "new_value": current_has_permission,
                    "change_type": "grant" if current_has_permission else "revoke",
                    "timestamp": time.time(),
                    "source": "client",
                    "detection_method": "polling",
                }
                changes.append(change)

        return changes

    def _record_permission_change(self, change: Dict):
        """记录权限变更"""
        from .permission_sync import PermissionChange, SyncStatus

        permission_change = PermissionChange(
            user_id=change["user_id"],
            permission_name=change["permission_name"],
            resource_type="unknown",  # 需要根据权限名称推断
            resource_id="unknown",
            old_value=change["old_value"],
            new_value=change["new_value"],
            change_type=change["change_type"],
            timestamp=change["timestamp"],
            source=change["source"],
            sync_status=SyncStatus.PENDING,
        )

        # 添加到同步管理器
        self.sync_manager.add_permission_change(permission_change)

    def get_polling_status(self) -> Dict:
        """获取轮询状态"""
        return {
            "stats": self.polling_stats,
            "polling_interval": f"{self.polling_interval}s",
            "last_check_time": (
                datetime.fromtimestamp(self.polling_stats["last_check_time"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if self.polling_stats["last_check_time"] > 0
                else "Never"
            ),
            "avg_check_time": f"{self.polling_stats['avg_check_time']:.3f}s",
            "monitored_users": len(self.last_snapshots),
            "running": self.running,
        }

    def get_user_permission_history(
        self, user_id: str, limit: int = 10
    ) -> List[PermissionSnapshot]:
        """获取用户权限历史"""
        # 这里可以实现权限历史记录
        return []

    def set_polling_interval(self, interval: int):
        """设置轮询间隔"""
        self.polling_interval = interval
        logger.info(f"轮询间隔已设置为 {interval} 秒")

    def stop(self):
        """停止轮询"""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        logger.info("权限轮询已停止")


class PermissionConflictDetector:
    """权限冲突检测器"""

    def __init__(self):
        self.conflict_rules = {
            "admin_and_user": ["admin", "user"],
            "read_and_write": ["read", "write"],
            "manage_and_view": ["manage", "view"],
        }

    def detect_conflicts(self, permissions: Dict[str, bool]) -> List[Dict]:
        """检测权限冲突"""
        conflicts = []

        for rule_name, conflicting_permissions in self.conflict_rules.items():
            active_conflicts = []
            for perm in conflicting_permissions:
                if permissions.get(perm, False):
                    active_conflicts.append(perm)

            if len(active_conflicts) > 1:
                conflicts.append(
                    {
                        "rule": rule_name,
                        "conflicting_permissions": active_conflicts,
                        "severity": "high" if "admin" in active_conflicts else "medium",
                    }
                )

        return conflicts

    def resolve_conflicts(self, conflicts: List[Dict]) -> Dict[str, bool]:
        """解决权限冲突"""
        resolved_permissions = {}

        for conflict in conflicts:
            # 根据冲突规则解决
            if conflict["rule"] == "admin_and_user":
                # 保留admin权限，移除user权限
                resolved_permissions["admin"] = True
                resolved_permissions["user"] = False
            elif conflict["rule"] == "read_and_write":
                # 保留write权限，移除read权限
                resolved_permissions["write"] = True
                resolved_permissions["read"] = False
            elif conflict["rule"] == "manage_and_view":
                # 保留manage权限，移除view权限
                resolved_permissions["manage"] = True
                resolved_permissions["view"] = False

        return resolved_permissions


# 全局实例
_permission_poller = None
_conflict_detector = None


def get_permission_poller(app=None):
    """获取权限轮询器"""
    global _permission_poller
    if _permission_poller is None:
        from .permission_sync import get_sync_manager

        if app is None:
            raise RuntimeError("必须传入app对象")
        sync_manager = get_sync_manager(app)
        _permission_poller = PermissionPoller(sync_manager, app)
    return _permission_poller


def get_conflict_detector():
    """获取冲突检测器"""
    global _conflict_detector
    if _conflict_detector is None:
        _conflict_detector = PermissionConflictDetector()
    return _conflict_detector
