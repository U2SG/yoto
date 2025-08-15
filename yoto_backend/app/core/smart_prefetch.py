"""
智能预取和客户端优化模块

基于用户行为分析，实现智能预取系统，提升客户端响应速度和用户体验
"""

import time
import json
import logging
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import redis

logger = logging.getLogger(__name__)


@dataclass
class UserBehavior:
    """用户行为数据模型"""

    user_id: str
    action: str  # 操作类型：view, edit, delete, etc.
    resource_type: str  # 资源类型：server, channel, role, etc.
    resource_id: str  # 资源ID
    timestamp: float  # 时间戳
    session_id: str  # 会话ID
    context: Dict[str, Any]  # 上下文信息


class BehaviorAnalyzer:
    """行为分析器"""

    def __init__(self, redis_client: redis.Redis = None):
        self.redis_client = redis_client
        self.behavior_key_prefix = "user_behavior:"
        self.pattern_key_prefix = "behavior_pattern:"

    def record_behavior(self, behavior: UserBehavior):
        """记录用户行为"""
        try:
            if not self.redis_client:
                logger.warning("Redis客户端未配置，跳过行为记录")
                return

            # 存储行为数据
            behavior_key = f"{self.behavior_key_prefix}{behavior.user_id}"
            behavior_data = asdict(behavior)
            behavior_data["timestamp"] = str(behavior_data["timestamp"])

            # 使用Redis List存储最近的行为记录（保留最近1000条）
            self.redis_client.lpush(behavior_key, json.dumps(behavior_data))
            self.redis_client.ltrim(behavior_key, 0, 999)

            # 设置过期时间（7天）
            self.redis_client.expire(behavior_key, 7 * 24 * 3600)

            logger.debug(
                f"记录用户行为: {behavior.user_id} - {behavior.action} - {behavior.resource_type}"
            )

        except Exception as e:
            logger.error(f"记录用户行为失败: {e}")

    def _get_user_behaviors(self, user_id: str, limit: int = 100) -> List[UserBehavior]:
        """获取用户行为历史"""
        try:
            if not self.redis_client:
                return []

            behavior_key = f"{self.behavior_key_prefix}{user_id}"
            behavior_data_list = self.redis_client.lrange(behavior_key, 0, limit - 1)

            behaviors = []
            for data in behavior_data_list:
                try:
                    behavior_dict = json.loads(data)
                    behavior_dict["timestamp"] = float(behavior_dict["timestamp"])
                    behaviors.append(UserBehavior(**behavior_dict))
                except Exception as e:
                    logger.warning(f"解析行为数据失败: {e}")
                    continue

            return behaviors

        except Exception as e:
            logger.error(f"获取用户行为历史失败: {e}")
            return []

    def _analyze_patterns(self, behaviors: List[UserBehavior]) -> Dict[str, Any]:
        """分析行为模式"""
        if not behaviors:
            return {}

        # 按会话分组
        session_behaviors = defaultdict(list)
        for behavior in behaviors:
            session_behaviors[behavior.session_id].append(behavior)

        # 分析操作序列
        action_sequences = []
        for session_behaviors_list in session_behaviors.values():
            if len(session_behaviors_list) > 1:
                # 按时间排序
                sorted_behaviors = sorted(
                    session_behaviors_list, key=lambda x: x.timestamp
                )
                sequence = [
                    (b.action, b.resource_type, b.resource_id) for b in sorted_behaviors
                ]
                action_sequences.append(sequence)

        # 分析资源访问频率
        resource_frequency = Counter()
        for behavior in behaviors:
            resource_key = f"{behavior.resource_type}:{behavior.resource_id}"
            resource_frequency[resource_key] += 1

        # 分析操作类型分布
        action_frequency = Counter()
        for behavior in behaviors:
            action_frequency[behavior.action] += 1

        return {
            "action_sequences": action_sequences,
            "resource_frequency": dict(resource_frequency.most_common(10)),
            "action_frequency": dict(action_frequency.most_common(5)),
            "total_behaviors": len(behaviors),
            "unique_sessions": len(session_behaviors),
        }

    def predict_next_actions(
        self, user_id: str, current_context: Dict = None
    ) -> List[Dict]:
        """预测用户下一步可能的操作"""
        try:
            # 获取用户行为历史
            behaviors = self._get_user_behaviors(user_id, limit=200)
            if not behaviors:
                return []

            # 分析行为模式
            patterns = self._analyze_patterns(behaviors)

            predictions = []

            # 基于资源访问频率预测
            for resource_key, frequency in patterns.get(
                "resource_frequency", {}
            ).items():
                resource_type, resource_id = resource_key.split(":", 1)
                confidence = min(frequency / patterns["total_behaviors"], 0.8)

                predictions.append(
                    {
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "action": "view",  # 默认预测查看操作
                        "confidence": confidence,
                        "reason": f"历史访问频率: {frequency}次",
                        "prediction_type": "frequency_based",
                    }
                )

            # 基于操作序列预测
            action_sequences = patterns.get("action_sequences", [])
            if action_sequences:
                # 分析当前上下文是否匹配历史序列
                if current_context:
                    current_action = current_context.get("action")
                    current_resource = current_context.get("resource_type")

                    for sequence in action_sequences:
                        for i, (action, resource_type, resource_id) in enumerate(
                            sequence
                        ):
                            if (
                                action == current_action
                                and resource_type == current_resource
                                and i + 1 < len(sequence)
                            ):
                                # 找到匹配的序列，预测下一步
                                next_action, next_resource_type, next_resource_id = (
                                    sequence[i + 1]
                                )
                                confidence = 0.6  # 序列预测的置信度

                                predictions.append(
                                    {
                                        "resource_type": next_resource_type,
                                        "resource_id": next_resource_id,
                                        "action": next_action,
                                        "confidence": confidence,
                                        "reason": f"基于操作序列预测",
                                        "prediction_type": "sequence_based",
                                    }
                                )

            # 去重并排序
            unique_predictions = {}
            for pred in predictions:
                key = f"{pred['resource_type']}:{pred['resource_id']}:{pred['action']}"
                if (
                    key not in unique_predictions
                    or pred["confidence"] > unique_predictions[key]["confidence"]
                ):
                    unique_predictions[key] = pred

            return sorted(
                unique_predictions.values(), key=lambda x: x["confidence"], reverse=True
            )

        except Exception as e:
            logger.error(f"预测用户操作失败: {e}")
            return []


class SmartPrefetcher:
    """智能预取器"""

    def __init__(self, behavior_analyzer: BehaviorAnalyzer):
        self.analyzer = behavior_analyzer
        self.prefetch_queue = []
        self.prefetch_cache = {}
        self.last_prefetch_time = 0
        self.prefetch_interval = 60  # 1分钟预取一次

    def should_prefetch(self) -> bool:
        """判断是否应该预取"""
        return time.time() - self.last_prefetch_time > self.prefetch_interval

    def generate_prefetch_tasks(
        self, user_id: str, current_context: Dict = None
    ) -> List[Dict]:
        """生成预取任务"""
        predictions = self.analyzer.predict_next_actions(user_id, current_context)
        tasks = []

        for pred in predictions:
            if pred["confidence"] > 0.3:  # 只预取置信度较高的
                tasks.append(
                    {
                        "user_id": user_id,
                        "resource_type": pred["resource_type"],
                        "resource_id": pred["resource_id"],
                        "priority": pred["confidence"],
                        "reason": pred["reason"],
                        "timestamp": time.time(),
                    }
                )

        return tasks

    def add_prefetch_task(self, task: Dict):
        """添加预取任务"""
        self.prefetch_queue.append(task)
        # 按优先级排序
        self.prefetch_queue.sort(key=lambda x: x["priority"], reverse=True)

        logger.info(
            f"添加预取任务: {task['resource_type']}:{task['resource_id']} "
            f"(置信度: {task['priority']:.2f})"
        )

    def get_prefetch_batch(self, batch_size: int = 5) -> List[Dict]:
        """获取预取批次"""
        if not self.prefetch_queue:
            return []

        batch = self.prefetch_queue[:batch_size]
        self.prefetch_queue = self.prefetch_queue[batch_size:]

        return batch

    def cache_prefetched_data(
        self, user_id: str, resource_type: str, resource_id: str, data: Dict
    ):
        """缓存预取的数据"""
        cache_key = f"prefetch:{user_id}:{resource_type}:{resource_id}"
        self.prefetch_cache[cache_key] = {
            "data": data,
            "timestamp": time.time(),
            "expires_at": time.time() + 300,  # 5分钟过期
        }

        logger.debug(f"缓存预取数据: {cache_key}")

    def get_prefetched_data(
        self, user_id: str, resource_type: str, resource_id: str
    ) -> Optional[Dict]:
        """获取预取的数据"""
        cache_key = f"prefetch:{user_id}:{resource_type}:{resource_id}"
        cached = self.prefetch_cache.get(cache_key)

        if cached and time.time() < cached["expires_at"]:
            logger.debug(f"命中预取缓存: {cache_key}")
            return cached["data"]

        # 清理过期数据
        if cached:
            del self.prefetch_cache[cache_key]

        return None

    def cleanup_expired_cache(self):
        """清理过期的预取缓存"""
        current_time = time.time()
        expired_keys = []

        for key, cached in self.prefetch_cache.items():
            if current_time >= cached["expires_at"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.prefetch_cache[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期预取缓存")


class ClientSidePredictor:
    """客户端预测器"""

    def __init__(self):
        self.analyzer = BehaviorAnalyzer()
        self.prefetcher = SmartPrefetcher(self.analyzer)
        self.user_sessions = {}

    def record_user_action(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        session_id: str = None,
        context: Dict = None,
    ):
        """记录用户操作"""
        if session_id is None:
            session_id = f"{user_id}_{int(time.time() / 3600)}"  # 按小时生成会话ID

        behavior = UserBehavior(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=time.time(),
            session_id=session_id,
            context=context or {},
        )

        self.analyzer.record_behavior(behavior)

        # 更新用户会话
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = session_id

        # 检查是否需要预取
        if self.prefetcher.should_prefetch():
            self._trigger_prefetch(user_id, context)

    def _trigger_prefetch(self, user_id: str, context: Dict = None):
        """触发预取"""
        tasks = self.prefetcher.generate_prefetch_tasks(user_id, context)

        for task in tasks:
            self.prefetcher.add_prefetch_task(task)

        self.prefetcher.last_prefetch_time = time.time()
        logger.info(f"为用户 {user_id} 生成了 {len(tasks)} 个预取任务")

    def get_predicted_resources(self, user_id: str) -> List[Dict]:
        """获取预测的资源"""
        return self.analyzer.predict_next_actions(user_id)

    def get_prefetch_tasks(self, batch_size: int = 5) -> List[Dict]:
        """获取预取任务"""
        return self.prefetcher.get_prefetch_batch(batch_size)

    def get_optimization_stats(self) -> Dict:
        """获取优化统计"""
        return {
            "total_prefetch_tasks": len(self.prefetcher.prefetch_queue),
            "cached_items": len(self.prefetcher.prefetch_cache),
            "user_sessions": len(self.user_sessions),
            "last_prefetch_time": self.prefetcher.last_prefetch_time,
        }


# 全局实例
_client_predictor = None


def get_client_predictor() -> ClientSidePredictor:
    """获取客户端预测器实例"""
    global _client_predictor
    if _client_predictor is None:
        _client_predictor = ClientSidePredictor()
    return _client_predictor


def record_user_action(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    session_id: str = None,
    context: Dict = None,
):
    """记录用户操作的便捷函数"""
    predictor = get_client_predictor()
    predictor.record_user_action(
        user_id, action, resource_type, resource_id, session_id, context
    )


def get_predicted_resources(user_id: str) -> List[Dict]:
    """获取预测资源的便捷函数"""
    predictor = get_client_predictor()
    return predictor.get_predicted_resources(user_id)


def get_prefetch_tasks(batch_size: int = 5) -> List[Dict]:
    """获取预取任务的便捷函数"""
    predictor = get_client_predictor()
    return predictor.get_prefetch_tasks(batch_size)
