# GitHub Secrets 配置指南

## 概述

GitHub Secrets 用于安全地存储敏感信息，如密码、密钥等，供 GitHub Actions 使用。

## 配置步骤

### 1. 访问 Secrets 配置页面

1. 打开 GitHub 仓库页面
2. 点击 `Settings` 标签
3. 在左侧菜单中点击 `Secrets and variables`
4. 选择 `Actions`

### 2. 创建 Repository Secrets

点击 `New repository secret` 按钮，依次创建以下 Secrets：

#### Docker 镜像仓库认证
- **`DOCKER_USERNAME`**: Docker Hub 用户名
- **`DOCKER_PASSWORD`**: Docker Hub 密码或访问令牌

#### SSH 连接认证
- **`SSH_HOST`**: Swarm Manager 节点的公网IP地址
- **`SSH_USER`**: SSH 登录用户名 (如 `ubuntu`)
- **`SSH_PRIVATE_KEY`**: SSH 私钥内容

#### 数据库连接
- **`DATABASE_URI`**: 生产环境数据库连接字符串
- **`STAGING_DATABASE_URI`**: Staging环境数据库连接字符串

#### Redis 连接
- **`REDIS_URL`**: 生产环境Redis连接字符串
- **`STAGING_REDIS_URL`**: Staging环境Redis连接字符串

#### 通知配置
- **`SLACK_WEBHOOK_URL`**: Slack Webhook URL (可选)
- **`DISCORD_WEBHOOK_URL`**: Discord Webhook URL (可选)

## Secrets 命名规范

- 使用大写字母和下划线
- 名称要具有描述性
- 按功能分组

## 安全最佳实践

1. **定期轮换**: 定期更新密码和密钥
2. **最小权限**: 只授予必要的权限
3. **环境隔离**: 不同环境使用不同的密钥
4. **审计日志**: 定期检查 Secrets 使用情况

## 示例配置

```bash
# Docker 认证
DOCKER_USERNAME=your-docker-username
DOCKER_PASSWORD=your-docker-password

# SSH 连接
SSH_HOST=192.168.1.100
SSH_USER=ubuntu
SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...

# 数据库连接
DATABASE_URI=mysql+pymysql://user:pass@host:3306/db
STAGING_DATABASE_URI=mysql+pymysql://user:pass@staging-host:3306/staging-db

# Redis 连接
REDIS_URL=redis://host:6379/0
STAGING_REDIS_URL=redis://staging-host:6379/0

# 通知
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## 验证配置

创建 Secrets 后，可以在 GitHub Actions 中通过以下方式引用：

```yaml
- name: Use Secret
  run: |
    echo "Using secret: ${{ secrets.SECRET_NAME }}"
```

## 注意事项

1. Secrets 一旦创建就无法查看内容，只能更新
2. Secrets 对仓库的所有协作者可见（但内容不可见）
3. 删除 Secrets 后，相关的 Actions 将无法运行
4. 建议在测试环境中先验证 Secrets 配置 