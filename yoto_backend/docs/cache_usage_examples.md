# 缓存服务使用示例

本文档展示如何在其他模块中复用通用缓存服务。

## 示例1：用户数据缓存

```python
from app.core.cache_service import CacheService

class UserCacheService:
    """用户数据缓存服务示例"""
    
    def __init__(self):
        self.cache = CacheService(cache_type="multilevel", name="user_cache")
    
    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户资料（带缓存）"""
        cache_key = f"user_profile:{user_id}"
        return self.cache.get(cache_key)
    
    def set_user_profile(self, user_id: int, profile: Dict[str, Any], ttl: int = 3600):
        """设置用户资料缓存"""
        cache_key = f"user_profile:{user_id}"
        self.cache.set(cache_key, profile, ttl)
    
    def invalidate_user_profile(self, user_id: int):
        """失效用户资料缓存"""
        cache_key = f"user_profile:{user_id}"
        self.cache.delete(cache_key)
```

## 示例2：服务器数据缓存

```python
class ServerCacheService:
    """服务器数据缓存服务示例"""
    
    def __init__(self):
        self.cache = CacheService(cache_type="multilevel", name="server_cache")
    
    def get_server_info(self, server_id: int) -> Optional[Dict[str, Any]]:
        """获取服务器信息（带缓存）"""
        cache_key = f"server_info:{server_id}"
        return self.cache.get(cache_key)
    
    def set_server_info(self, server_id: int, info: Dict[str, Any], ttl: int = 7200):
        """设置服务器信息缓存"""
        cache_key = f"server_info:{server_id}"
        self.cache.set(cache_key, info, ttl)
```

## 示例3：使用缓存装饰器

```python
from app.core.cache_service import cached, get_global_cache

class CachedDataService:
    """使用缓存装饰器的数据服务示例"""
    
    @cached(ttl=3600, cache_type="multilevel")
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户统计信息（自动缓存）"""
        # 模拟从数据库获取数据
        return {
            'user_id': user_id,
            'message_count': 1000,
            'server_count': 5,
            'friend_count': 50,
            'last_active': '2024-12-19T10:00:00Z'
        }
    
    @cached(ttl=1800, cache_type="multilevel")
    def get_server_statistics(self, server_id: int) -> Dict[str, Any]:
        """获取服务器统计信息（自动缓存）"""
        return {
            'server_id': server_id,
            'member_count': 100,
            'message_count': 5000,
            'channel_count': 10,
            'created_at': '2024-01-01T00:00:00Z'
        }
```

## 示例4：缓存监控和统计

```python
class CacheMonitorService:
    """缓存监控服务示例"""
    
    def __init__(self):
        self.user_cache = CacheService(cache_type="multilevel", name="user_cache")
        self.server_cache = CacheService(cache_type="multilevel", name="server_cache")
        self.message_cache = CacheService(cache_type="multilevel", name="message_cache")
    
    def get_all_cache_stats(self) -> Dict[str, Any]:
        """获取所有缓存统计信息"""
        return {
            'user_cache': self.user_cache.get_stats(),
            'server_cache': self.server_cache.get_stats(),
            'message_cache': self.message_cache.get_stats(),
            'global_cache': get_global_cache().get_stats()
        }
    
    def get_cache_performance_report(self) -> Dict[str, Any]:
        """获取缓存性能报告"""
        stats = self.get_all_cache_stats()
        
        total_hits = 0
        total_misses = 0
        
        for cache_name, cache_stats in stats.items():
            if 'l1_cache' in cache_stats:
                # 多级缓存
                l1_stats = cache_stats['l1_cache']
                total_hits += l1_stats.get('hit_count', 0)
                total_misses += l1_stats.get('miss_count', 0)
            else:
                # 单级缓存
                total_hits += cache_stats.get('hit_count', 0)
                total_misses += cache_stats.get('miss_count', 0)
        
        total_requests = total_hits + total_misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        return {
            'overall_hit_rate': overall_hit_rate,
            'total_requests': total_requests,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'cache_details': stats
        }
```

## 示例5：缓存策略配置

```python
class CacheConfigService:
    """缓存配置服务示例"""
    
    def __init__(self):
        self.configs = {
            'user_profile': {
                'ttl': 3600,  # 1小时
                'cache_type': 'multilevel',
                'maxsize': 1000
            },
            'server_info': {
                'ttl': 7200,  # 2小时
                'cache_type': 'multilevel',
                'maxsize': 500
            },
            'message_list': {
                'ttl': 300,   # 5分钟
                'cache_type': 'multilevel',
                'maxsize': 2000
            }
        }
    
    def get_cache_config(self, cache_name: str) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.configs.get(cache_name, {
            'ttl': 300,
            'cache_type': 'multilevel',
            'maxsize': 1000
        })
    
    def create_cache_service(self, cache_name: str) -> CacheService:
        """根据配置创建缓存服务"""
        config = self.get_cache_config(cache_name)
        return CacheService(
            cache_type=config['cache_type'],
            name=cache_name,
            l1_maxsize=config.get('maxsize', 1000)
        )
```

## 使用建议

1. **选择合适的缓存类型**：
   - LRU缓存：适合高频访问的本地数据
   - Redis缓存：适合跨服务共享的数据
   - 多级缓存：适合需要最佳性能的场景

2. **合理设置TTL**：
   - 用户资料：1-2小时
   - 服务器信息：2-4小时
   - 消息列表：5-15分钟
   - 统计数据：30分钟-1小时

3. **缓存键设计**：
   - 使用有意义的键名
   - 包含必要的参数信息
   - 避免键名过长

4. **缓存失效策略**：
   - 数据更新时主动失效
   - 设置合理的TTL
   - 监控缓存命中率

5. **性能监控**：
   - 定期检查缓存统计
   - 监控缓存命中率
   - 根据使用情况调整配置 