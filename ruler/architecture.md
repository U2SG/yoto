---

# **Yoto - 系统架构设计文档**

### **版本：1.0**
### **日期：2025年7月25日**

---

## **1. 架构总览 (Architecture Overview)**

本系统采用**面向服务的、可扩展的单体架构（Scalable Monolith）**，利用Flask蓝图实现内部模块化，为未来平滑过渡到微服务架构奠定基础。整体架构遵循关注点分离原则，将API服务、实时通讯服务和异步任务处理服务进行解耦。

#### **架构关系图 (文本描述)**

```
                                +-----------------------------------+
                                |            用户 (iOS App)         |
                                +-----------------------------------+
                                     |            |              |
                          (HTTPS/443)  |  (WSS/443)   | (HTTPS/443)
                                     |            |              |
                                +----v------------v--------------v----+
                                |         Nginx (反向代理/负载均衡)      |
                                +-----------------------------------+
                                |                |                  |
              (uWSGI/HTTP)      |                | (HTTP)           |
          +---------------------v-+      +-------v----------+     |
          | Gunicorn (WSGI Server)  |      | Uvicorn (ASGI Server)|     | (Static Files)
          | +-------------------+ |      | +----------------+ |     |
          | |   Flask API App   | |      | | WebSocket App  | |     |
          | +-------------------+ |      | +----------------+ |     |
          +-----------------------+      +------------------+     |
              |    |       |                     |               |
              |    |       +---------------------+               |
              |    |       | (TCP/IP Connections)|               |
              |    +-------+---------------------v---------------+
              |            |                     |
      +-------v-+    +-----v------+      +-------v--------+  +-----v-------+
      |  MySQL  |    |   Redis    |      | Celery Workers |  | Elasticsearch |
      | (主数据库) |    | (缓存/消息队列) |      | (异步任务处理)   |  | (全文搜索)    |
      +---------+    +------------+      +----------------+  +-------------+

```

#### **核心流程:**
1.  **API 请求:** iOS App通过HTTPS向Nginx发送API请求。Nginx将请求反向代理到Gunicorn。Gunicorn运行的Flask应用处理请求，与MySQL、Redis、Elasticsearch交互，并将响应返回。
2.  **实时通讯:** iOS App通过WSS（Secure WebSocket）向Nginx发起长连接请求。Nginx将该请求代理到专门处理WebSocket的ASGI服务器（如Uvicorn）。WebSocket服务与Redis的Pub/Sub功能紧密集成，用于接收和广播实时消息。
3.  **异步任务:** 当API应用遇到耗时操作（如发送推送、处理图片）时，它不会直接执行，而是创建一个任务并将其放入Redis的消息队列中。独立的Celery Worker进程会监听队列，获取并执行任务，执行结果可能会更新回MySQL。

---

## **2. 文件夹与文件结构 (Folder & File Structure)**

项目将采用“应用工厂”（Application Factory）模式进行组织，结构清晰，易于维护和测试。

```
yoto_backend/
├── app/                                # Flask应用核心代码
│   ├── __init__.py                     # 应用工厂函数 create_app()
│   ├── blueprints/                     # 业务模块蓝图
│   │   ├── __init__.py
│   │   ├── auth/                       # 认证与授权 (注册, 登录, JWT)
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   └── models.py
│   │   ├── servers/                    # 星球(Server)管理
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   ├── models.py
│   │   │   └── schemas.py              # (可选) Marshmallow/Pydantic序列化
│   │   ├── channels/                   # 星轨(Channel)管理
│   │   ├── roles/                      # 角色与权限管理
│   │   └── users/                      # 用户资料与好友关系
│   ├── core/                           # 核心组件与扩展
│   │   ├── __init__.py
│   │   ├── cache.py                    # 多级缓存实现
│   │   └── extensions.py               # 统一管理Flask扩展实例 (db, migrate, etc.)
│   ├── models/                         # 全局或共享的数据模型
│   │   ├── __init__.py
│   │   └── base.py                     # 模型基类 (如含created_at等公共字段)
│   ├── static/                         # 静态文件 (本项目中主要由Nginx提供)
│   ├── tasks/                          # Celery异步任务定义
│   │   ├── __init__.py
│   │   ├── notification_tasks.py
│   │   ├── media_tasks.py
│   │   └── community_tasks.py
│   └── ws/                             # WebSocket相关逻辑
│       ├── __init__.py
│       └── handlers.py                 # WebSocket连接管理与消息处理
│
├── migrations/                         # Flask-Migrate 数据库迁移脚本
├── tests/                              # 单元测试与集成测试
│   ├── __init__.py
│   └── test_servers.py
│
├── .env                                # 环境变量 (私密配置)
├── .flaskenv                           # Flask CLI 环境变量
├── .gitignore
├── config.py                           # 配置类 (Development, Production, Testing)
├── celery_worker.py                    # Celery Worker的启动入口
├── Dockerfile                          # 应用容器化配置
├── docker-compose.yml                  # 开发环境编排 (MySQL, Redis, ES...)
├── requirements.txt                    # Python依赖列表
└── run.py                              # 开发服务器启动脚本
```

---

## **3. 各模块职责详解 (Detailed Role of Each Module)**

*   **`app/`**: 项目的核心目录。
    *   **`__init__.py`**: 定义`create_app`工厂函数。负责初始化Flask应用、配置、注册蓝图和扩展。
    *   **`blueprints/`**: 业务逻辑的核心。每个子目录是一个独立的模块（蓝图），包含自己的视图(views)、模型(models)，实现高内聚。
        *   `auth/`: 处理用户注册、登录、登出、密码重置和JWT令牌的生成与验证。
        *   `servers/`: 处理星球的创建、加入、设置、成员管理等所有API。
    *   **`core/`**: 存放非业务逻辑的核心代码。
        *   `extensions.py`: 实例化所有Flask扩展（如`db = SQLAlchemy()`），避免循环导入问题。
        *   `cache.py`: 实现`cachetools`本地缓存和`Redis`分布式缓存的统一调用接口。
    *   **`models/`**: 定义全局共享的数据模型，或作为所有模型定义的聚合点。
    *   **`tasks/`**: 存放所有Celery异步任务。每个文件按功能划分，如`notification_tasks.py`处理所有推送通知任务。
    *   **`ws/`**: 存放所有WebSocket连接管理和消息处理的逻辑。

*   **`migrations/`**: 由`Flask-Migrate`自动生成和管理，记录数据库结构的所有变更历史。

*   **`tests/`**: 存放所有使用`pytest`编写的测试用例。

*   **`.env`**: 存储敏感信息，如数据库密码、API密钥。**此文件绝不应提交到版本控制系统**。

*   **`config.py`**: 定义不同环境（开发、测试、生产）的配置类，从`.env`文件中读取敏感信息。

*   **`celery_worker.py`**: Celery应用的入口文件。Celery Worker进程会加载此文件来启动。

*   **`Dockerfile`**: 定义如何将Flask应用打包成一个Docker镜像，用于生产部署。

*   **`docker-compose.yml`**: 用于在开发环境中一键启动和管理所有依赖的服务（MySQL, Redis, Elasticsearch）。

*   **`run.py`**: 一个简单的脚本，用于在本地开发环境中启动Flask应用。

---

## **4. 状态存储与服务连接 (State Storage & Service Connectivity)**

| 服务/组件 (Service/Component) | 状态存储位置 (State Storage Location) | 如何连接 (How It Connects) |
| :--- | :--- | :--- |
| **Nginx** | 无状态 (Stateless)。日志存储在本地文件系统。 | 监听公网`80/443`端口。通过Unix Socket或本地端口(`8000`)反向代理到Gunicorn。通过另一本地端口(`8001`)反向代理到Uvicorn。直接提供`/static/`下的静态文件。 |
| **Gunicorn (Flask App)** | 无状态。为实现可扩展性，应用本身不保存任何请求间的状态。 | 通过`config.py`中的连接字符串连接到**MySQL** (持久化数据) 和**Redis** (缓存/会话)。需要执行异步任务时，通过Celery API将任务信息和参数发送到**Redis** (作为Broker)。通过API连接到**Elasticsearch**。 |
| **Uvicorn (WebSocket App)** | 状态主要在Redis中。维护活跃的WebSocket连接列表，并将连接ID与用户ID的映射关系存储在**Redis**中。 | 通过`config.py`中的连接字符串连接到**Redis**。使用Redis的Pub/Sub功能订阅特定频道的消息，并将收到的消息广播给对应的WebSocket客户端。 |
| **Celery Workers** | 无状态。Worker本身是计算单元，不存储长期状态。 | 持续监听**Redis**中的特定任务队列。接收到任务后，根据任务逻辑可能会连接**MySQL**读写数据，或调用第三方API。 |
| **MySQL** | 本地文件系统。作为系统唯一的持久化数据存储源（Source of Truth）。 | 接受来自**Gunicorn (Flask App)**和**Celery Workers**的TCP/IP连接（由`SQLAlchemy`的连接池管理）。 |
| **Redis** | 内存 (主要)，可配置持久化到磁盘 (AOF/RDB)。 | 接受来自**Gunicorn (Flask App)**、**Uvicorn (WebSocket App)**和**Celery Workers**的TCP/IP连接。用作：① 分布式缓存 ② WebSocket用户状态和消息广播 ③ Celery的消息中间件和结果后端。 |
| **Elasticsearch** | 本地文件系统。存储搜索索引。 | 接受来自**Gunicorn (Flask App)**的HTTP API请求。数据同步通常由Celery异步任务在数据创建/更新后触发。 |