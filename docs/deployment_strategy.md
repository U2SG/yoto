# 部署环境与分支策略

## 环境规划

### 1. 生产环境 (Production)
- **用途**: 面向最终用户的生产服务
- **触发条件**: 代码合并到 `main` 分支
- **基础设施**: 5台云服务器集群 (Docker Swarm)
- **部署目标**: 高可用、高性能的生产服务

### 2. 预发布/测试环境 (Staging)
- **用途**: 生产前的最终验证环境
- **触发条件**: 代码合并到 `develop` 分支
- **基础设施**: 迷你版生产环境 (1台API服务器 + 1台Redis/DB服务器)
- **部署目标**: 与生产环境高度一致的验证环境

### 3. 开发环境 (Development)
- **用途**: 开发人员本地开发和测试
- **触发条件**: 本地开发
- **基础设施**: 本地Docker Compose
- **部署目标**: 快速迭代和调试

## 分支策略

### 主要分支
- **`main`**: 生产环境分支，稳定版本
- **`develop`**: 开发集成分支，预发布版本
- **`feature/*`**: 功能开发分支
- **`hotfix/*`**: 紧急修复分支

### 工作流程
1. 开发人员从 `develop` 分支创建 `feature/*` 分支
2. 完成开发后，创建PR合并到 `develop` 分支
3. `develop` 分支自动部署到Staging环境进行验证
4. 验证通过后，创建PR合并到 `main` 分支
5. `main` 分支自动部署到Production环境

## 部署配置

### 生产环境配置
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    image: your-repo/yoto-api:${IMAGE_TAG}
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    environment:
      - FLASK_ENV=production
      - DATABASE_URI=${DATABASE_URI}
      - REDIS_URL=${REDIS_URL}
```

### Staging环境配置
```yaml
# docker-compose.staging.yml
version: '3.8'
services:
  api:
    image: your-repo/yoto-api:${IMAGE_TAG}
    deploy:
      replicas: 1
    environment:
      - FLASK_ENV=staging
      - DATABASE_URI=${STAGING_DATABASE_URI}
      - REDIS_URL=${STAGING_REDIS_URL}
```

## 安全考虑

1. **环境隔离**: 生产、Staging、开发环境完全隔离
2. **密钥管理**: 使用GitHub Secrets管理敏感信息
3. **访问控制**: 限制对生产环境的直接访问
4. **回滚机制**: 支持快速回滚到之前的版本

## 监控与告警

1. **部署监控**: 监控部署成功/失败状态
2. **服务健康检查**: 监控服务运行状态
3. **性能监控**: 监控系统性能指标
4. **告警通知**: 部署状态通知到Slack/Discord 