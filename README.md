# Yoto Backend - 权限系统重构项目

## 项目简介

Yoto是一个基于Flask的现代化Web应用后端，专注于权限系统的模块化重构。项目采用微服务架构设计，实现了高度模块化、可测试和可维护的权限管理系统。

## 技术栈

### 核心框架
- **Flask 3.1.1** - Web应用框架
- **SQLAlchemy 2.0.35** - ORM数据库操作
- **Flask-SQLAlchemy 3.1.1** - Flask SQLAlchemy集成
- **Flask-Migrate 4.1.0** - 数据库迁移管理

### 认证和安全
- **Flask-JWT-Extended 4.7.1** - JWT认证
- **cryptography 45.0.5** - 加密功能

### 缓存和消息队列
- **redis 5.2.1** - 分布式缓存
- **celery 5.5.3** - 异步任务队列

### 实时通信
- **Flask-SocketIO 5.5.1** - WebSocket支持
- **eventlet 0.40.2** - 异步网络库
- **python-socketio 5.12.1** - Socket.IO协议

### 监控和性能
- **prometheus-client 0.22.1** - 监控指标
- **psutil 7.0.0** - 系统性能监控

### 测试框架
- **pytest 8.4.1** - 测试框架
- **pytest-cov 5.0.0** - 测试覆盖率

### 开发和工具
- **python-dotenv 1.0.1** - 环境变量管理
- **click 8.2.1** - 命令行工具
- **flasgger 0.9.7.1** - API文档生成

## 项目结构

```
yoto/
├── yoto_backend/          # 主应用目录
│   ├── app/              # 应用核心
│   │   ├── blueprints/   # 蓝图模块
│   │   ├── core/         # 核心功能
│   │   ├── models/       # 数据模型
│   │   ├── tasks/        # Celery任务
│   │   └── ws/           # WebSocket
│   ├── tests/            # 测试文件
│   ├── migrations/       # 数据库迁移
│   └── config.py         # 配置文件
├── ruler/                # 项目规范文档
├── docs/                 # 项目文档
├── requirements.txt       # 依赖列表
└── README.md            # 项目说明
```

## 安装和设置

### 1. 环境要求
- Python 3.12+
- MySQL 8.0+
- Redis 6.0+

### 2. 安装依赖
```bash
# 创建虚拟环境
python -m venv env

# 激活虚拟环境
# Windows
env\Scripts\activate
# Linux/Mac
source env/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 环境配置
复制环境变量模板：
```bash
cp yoto_backend/env.example .env
```

编辑`.env`文件，配置数据库和Redis连接：
```env
# 数据库配置
DATABASE_URI=mysql+pymysql://username:password@localhost:3306/yoto_db

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Flask配置
FLASK_ENV=development
FLASK_DEBUG=1
```

### 4. 数据库初始化
```bash
cd yoto_backend
flask db init
flask db migrate
flask db upgrade
```

### 5. 启动服务
```bash
# 启动Flask应用
python run.py

# 启动Celery Worker（新终端）
celery -A celery_worker.celery worker --loglevel=info

# 启动Celery Beat（新终端，如果需要定时任务）
celery -A celery_worker.celery beat --loglevel=info
```

## 权限系统架构

### 模块化设计
项目采用"外科手术式分解"策略，将权限系统分为以下层次：

1. **纯工具层** (`permission_utils.py`)
   - 无状态、无外部依赖的纯函数
   - 权限验证、键生成、哈希计算等基础功能

2. **抽象业务层** (`permission_abstractions.py`)
   - 权限模板、权限链、权限组等高级抽象
   - 支持依赖注入的设计模式

3. **工厂函数层** (`permission_factories.py`)
   - 权限创建和注册的工厂函数
   - 负责"创建"和"注册"逻辑

4. **数据查询层** (`permission_queries.py`)
   - 数据库查询相关功能
   - 用户权限摘要、权限元数据查询

### 核心特性
- ✅ 高度模块化设计
- ✅ 依赖注入支持
- ✅ 完整的测试覆盖
- ✅ 性能监控集成
- ✅ 分布式缓存支持
- ✅ 实时权限更新

## 测试

### 运行所有测试
```bash
cd yoto_backend
python -m pytest
```

### 运行特定测试
```bash
# 权限工具测试
python -m pytest tests/test_permission_utils.py

# 权限抽象测试
python -m pytest tests/test_permission_abstractions.py

# 权限工厂测试
python -m pytest tests/test_permission_factories.py
```

### 测试覆盖率
```bash
python -m pytest --cov=app --cov-report=html
```

## 开发规范

### 编码协议
- 编写绝对最少的必需代码
- 无重大变化，无无关编辑
- 专注当前任务
- 使代码精确、模块化、可测试
- 不要破坏功能

### 任务管理
- 严格按照`ruler/tasks.md`执行
- 一次完成一个任务
- 每完成一个任务停下来进行测试
- 测试通过后提交到GitHub

## 监控和性能

### Prometheus指标
- 权限检查性能指标
- 缓存命中率统计
- 系统资源使用情况

### 缓存策略
- 多级缓存架构
- LRU本地缓存
- Redis分布式缓存
- 智能缓存失效策略

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证

本项目采用MIT许可证。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件
- 项目讨论区 

---

**CI Pipeline Test**: This line was added to test the automated CI pipeline functionality. 