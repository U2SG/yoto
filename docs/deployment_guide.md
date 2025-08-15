# 部署指南

## 概述

本指南介绍如何使用自动化CD流水线部署Yoto应用到不同环境。

## 环境说明

### 生产环境 (Production)
- **分支**: `main`
- **触发**: 代码推送到main分支时自动触发
- **镜像**: `docker.io/U2SG/yoto:latest`
- **端口**: 5000
- **副本数**: 3

### Staging环境
- **分支**: `develop`
- **触发**: 代码推送到develop分支时自动触发
- **镜像**: `docker.io/U2SG/yoto:staging-latest`
- **端口**: 5001
- **副本数**: 1

## 前置条件

### 1. Docker Swarm集群
确保生产服务器已初始化Docker Swarm：

```bash
# 在Manager节点上
docker swarm init --advertise-addr <MANAGER_IP>

# 在Worker节点上
docker swarm join --token <WORKER_TOKEN> <MANAGER_IP>:2377
```

### 2. GitHub Secrets配置
在GitHub仓库中配置以下Secrets：

#### 生产环境
- `DOCKER_USERNAME`: Docker Hub用户名
- `DOCKER_PASSWORD`: Docker Hub密码
- `SSH_HOST`: 生产服务器IP
- `SSH_USER`: SSH用户名
- `SSH_PRIVATE_KEY`: SSH私钥
- `DATABASE_URI`: 生产数据库连接字符串
- `REDIS_URL`: 生产Redis连接字符串

#### Staging环境
- `STAGING_SSH_HOST`: Staging服务器IP
- `STAGING_SSH_USER`: Staging SSH用户名
- `STAGING_SSH_PRIVATE_KEY`: Staging SSH私钥
- `STAGING_DATABASE_URI`: Staging数据库连接字符串
- `STAGING_REDIS_URL`: Staging Redis连接字符串

#### 通知配置
- `SLACK_WEBHOOK_URL`: Slack Webhook URL (可选)

## 部署流程

### 1. 开发流程
```bash
# 1. 从develop分支创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/new-feature

# 2. 开发完成后，创建PR到develop分支
git push origin feature/new-feature
# 在GitHub上创建PR

# 3. 合并到develop分支，自动部署到Staging
# 4. 验证Staging环境后，创建PR到main分支
# 5. 合并到main分支，自动部署到Production
```

### 2. 手动部署

#### 生产环境
```bash
# 在Manager节点上
cd /opt/yoto/deploy
bash deploy.sh <IMAGE_TAG>
```

#### Staging环境
```bash
# 在Staging服务器上
cd /opt/yoto-staging/deploy
bash deploy-staging.sh <IMAGE_TAG>
```

## 监控和故障排除

### 1. 查看服务状态
```bash
# 查看所有服务
docker service ls

# 查看特定服务详情
docker service ps yoto-stack_yoto-api

# 查看服务日志
docker service logs yoto-stack_yoto-api
```

### 2. 健康检查
```bash
# 检查API健康状态
curl http://localhost:5000/health

# 检查Staging API健康状态
curl http://localhost:5001/health
```

### 3. 回滚操作
如果部署失败，系统会自动回滚到上一个版本。也可以手动回滚：

```bash
# 查看服务历史
docker service ps yoto-stack_yoto-api

# 手动回滚
docker service rollback yoto-stack_yoto-api
```

## 故障排除

### 常见问题

1. **服务启动失败**
   - 检查环境变量配置
   - 查看服务日志
   - 确认数据库和Redis连接

2. **镜像拉取失败**
   - 检查Docker Hub认证
   - 确认镜像标签存在
   - 检查网络连接

3. **健康检查失败**
   - 检查应用是否正常启动
   - 确认健康检查端点可用
   - 查看应用日志

### 日志查看
```bash
# 查看实时日志
docker service logs -f yoto-stack_yoto-api

# 查看最近100行日志
docker service logs --tail 100 yoto-stack_yoto-api
```

## 安全考虑

1. **访问控制**: 限制对生产环境的直接访问
2. **密钥管理**: 使用GitHub Secrets管理敏感信息
3. **网络隔离**: 使用Docker Swarm网络隔离服务
4. **资源限制**: 设置CPU和内存限制防止资源耗尽

## 性能优化

1. **资源分配**: 根据实际需求调整CPU和内存限制
2. **副本数量**: 根据负载调整服务副本数
3. **更新策略**: 配置合适的更新并行度和延迟
4. **健康检查**: 设置合理的健康检查间隔

## 维护操作

### 定期维护
1. **清理旧镜像**: 定期清理不再使用的Docker镜像
2. **更新基础镜像**: 定期更新基础镜像以修复安全漏洞
3. **监控资源使用**: 监控集群资源使用情况
4. **备份数据**: 定期备份数据库和配置文件

### 紧急操作
1. **服务重启**: `docker service update --force yoto-stack_yoto-api`
2. **节点维护**: `docker node update --availability drain <NODE_ID>`
3. **集群扩展**: 添加新的Worker节点
4. **故障转移**: 在Manager节点故障时进行故障转移 