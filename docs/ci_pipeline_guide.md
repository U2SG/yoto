# CI流水线使用指南

## 概述

本项目使用GitHub Actions实现自动化CI/CD流水线，确保代码质量和部署可靠性。

## 流水线架构

### 基础流水线 (ci.yml)

适用于日常开发和快速反馈：

- **触发条件**: push到main/develop分支，或PR到main/develop分支
- **运行环境**: Ubuntu Latest
- **Python版本**: 3.12
- **服务**: MySQL 8, Redis 7
- **检查项**: 代码格式化、质量检查、测试、覆盖率

### 高级流水线 (ci-advanced.yml)

适用于重要发布和全面验证：

- **并行化任务**: linting、testing、integration、performance
- **矩阵构建**: 支持Python 3.10、3.11、3.12
- **多环境测试**: 单元测试、集成测试、性能测试
- **条件执行**: 性能测试仅在PR时运行

## 流水线步骤详解

### 1. 代码检出 (Checkout)

```yaml
- name: Checkout code
  uses: actions/checkout@v4
```

- 检出最新的代码
- 支持浅克隆以提高速度

### 2. Python环境设置

```yaml
- name: Set up Python 3.12
  uses: actions/setup-python@v4
  with:
    python-version: '3.12'
    cache: 'pip'
```

- 安装指定版本的Python
- 启用pip缓存，大幅提升依赖安装速度

### 3. 依赖安装

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt

- name: Install development dependencies
  run: |
    pip install -r requirements-dev-simple.txt
```

- 分别安装生产依赖和开发依赖
- 使用requirements-dev-simple.txt避免编码问题

### 4. 代码质量检查

#### Black格式化检查

```yaml
- name: Run code formatting check
  run: |
    black --check .
```

- 检查代码是否符合Black格式标准
- 失败时提供格式化建议

#### Flake8质量检查

```yaml
- name: Run code quality check
  run: |
    flake8 . --count --show-source --statistics
```

- 检查代码风格和潜在问题
- 生成详细的统计信息

#### isort导入排序

```yaml
- name: Run import sorting check
  run: |
    isort --check-only --diff .
```

- 检查导入语句是否按标准排序
- 与Black格式兼容

#### Bandit安全检查

```yaml
- name: Run security check
  run: |
    bandit -r yoto_backend/ -f json -o bandit-report.json || true
```

- 检查潜在的安全漏洞
- 生成JSON格式的安全报告
- 使用`|| true`避免安全检查失败导致流水线中断

### 5. 测试执行

#### 环境变量配置

```yaml
- name: Run tests
  env:
    DATABASE_URI: mysql+pymysql://yoto_test_user:yoto_test_password@127.0.0.1:3306/yoto_test_db
    TEST_DATABASE_URI: mysql+pymysql://yoto_test_user:yoto_test_password@127.0.0.1:3306/yoto_test_db
    REDIS_URL: redis://127.0.0.1:6379/0
    CELERY_BROKER_URL: redis://127.0.0.1:6379/0
    CELERY_RESULT_BACKEND: redis://127.0.0.1:6379/0
    FLASK_ENV: testing
  run: |
    cd yoto_backend
    pytest --cov=app --cov-report=xml --cov-report=term-missing -v
```

- 配置测试数据库连接
- 配置Redis连接
- 设置Flask测试环境
- 生成XML和终端格式的覆盖率报告

### 6. 覆盖率报告上传

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    file: ./yoto_backend/coverage.xml
    flags: unittests
    name: codecov-umbrella
    fail_ci_if_error: false
```

- 上传覆盖率报告到Codecov
- 在PR中显示覆盖率变化
- 使用`fail_ci_if_error: false`避免上传失败影响流水线

## 服务容器配置

### MySQL服务

```yaml
services:
  mysql:
    image: mysql:8-alpine
    env:
      MYSQL_ROOT_PASSWORD: password
      MYSQL_DATABASE: yoto_test_db
      MYSQL_USER: yoto_test_user
      MYSQL_PASSWORD: yoto_test_password
    options: >-
      --health-cmd="mysqladmin ping"
      --health-interval=10s
      --health-timeout=5s
      --health-retries=3
    ports:
      - 3306:3306
```

- 使用MySQL 8 Alpine镜像（轻量级）
- 配置测试数据库和用户
- 健康检查确保服务可用
- 暴露3306端口

### Redis服务

```yaml
redis:
  image: redis:7-alpine
  options: >-
    --health-cmd="redis-cli ping"
    --health-interval=10s
    --health-timeout=5s
    --health-retries=3
  ports:
    - 6379:6379
```

- 使用Redis 7 Alpine镜像
- 健康检查确保服务可用
- 暴露6379端口

## 并行化策略

### 任务分离

高级流水线将任务分为四个独立的job：

1. **linting**: 代码质量检查（最快完成）
2. **testing**: 单元测试（多版本矩阵）
3. **integration**: 集成测试（依赖linting和testing）
4. **performance**: 性能测试（可选，仅在PR时运行）

### 依赖关系

```yaml
integration:
  needs: [linting, testing]
  
performance:
  needs: [linting, testing]
  if: github.event_name == 'pull_request'
```

- integration和performance依赖linting和testing完成
- performance仅在PR时运行，节省资源

## 矩阵构建

### Python版本矩阵

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
    database: [mysql]
```

- 支持Python 3.10、3.11、3.12
- 确保代码在不同Python版本下都能正常工作
- 为每个版本生成独立的测试报告

## 缓存策略

### pip缓存

```yaml
- name: Set up Python 3.12
  uses: actions/setup-python@v4
  with:
    python-version: '3.12'
    cache: 'pip'
```

- 缓存pip下载的包
- 如果requirements.txt没有变化，安装速度从几分钟缩短到几秒钟

## 错误处理

### 安全检查容错

```yaml
- name: Run security check
  run: |
    bandit -r yoto_backend/ -f json -o bandit-report.json || true
```

- 使用`|| true`避免安全检查失败导致流水线中断
- 安全检查结果作为警告而非阻塞

### 覆盖率上传容错

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    fail_ci_if_error: false
```

- 使用`fail_ci_if_error: false`避免上传失败影响流水线
- 覆盖率报告作为补充信息而非必需

## 本地测试

### 运行相同的检查

在本地运行与CI相同的检查：

```bash
# 代码格式化检查
black --check .

# 代码质量检查
flake8 . --count --show-source --statistics

# 导入排序检查
isort --check-only --diff .

# 安全检查
bandit -r yoto_backend/ -f json -o bandit-report.json

# 测试
cd yoto_backend
pytest --cov=app --cov-report=term-missing -v
```

### 使用Docker Compose测试

```bash
# 启动测试环境
docker-compose up -d db redis

# 运行测试
cd yoto_backend
pytest --cov=app --cov-report=term-missing -v

# 清理
docker-compose down
```

## 故障排除

### 常见问题

1. **CI失败但本地通过**
   - 检查环境变量配置
   - 确认依赖版本一致
   - 查看CI日志中的具体错误

2. **测试超时**
   - 检查数据库连接配置
   - 确认服务健康检查通过
   - 考虑增加超时时间

3. **覆盖率报告问题**
   - 确认coverage.xml文件生成
   - 检查Codecov配置
   - 验证上传权限

### 调试技巧

1. **查看详细日志**
   - 在GitHub Actions页面点击"Details"
   - 查看每个步骤的详细输出

2. **本地复现**
   - 使用相同的环境变量
   - 运行相同的命令
   - 使用Docker Compose模拟CI环境

3. **临时跳过检查**
   - 使用`[skip ci]`在提交信息中跳过CI
   - 仅在紧急情况下使用

## 最佳实践

### 1. 提交前检查

```bash
# 运行pre-commit钩子
pre-commit run --all-files

# 或手动运行检查
black .
flake8 .
isort .
pytest
```

### 2. 分支策略

- 功能开发使用feature分支
- 修复使用fix分支
- 通过PR合并到develop
- 定期从develop合并到main

### 3. 代码审查

- 所有PR必须通过CI检查
- 审查代码质量和测试覆盖
- 关注安全检查和性能影响

### 4. 持续改进

- 定期更新依赖版本
- 优化流水线性能
- 添加新的检查项
- 收集团队反馈

---

更多信息请参考：
- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Codecov文档](https://docs.codecov.io/)
- [项目贡献指南](CONTRIBUTING.md) 