
### **第三周工作计划：搭建自动化CD流水线**

**核心目标**: 实现**软件交付的完全自动化**。当经过CI验证的代码被合并到主干分支（如`main`）时，系统能够**自动地、安全地、可预测地**将其构建成Docker镜像，并部署到我们的生产环境（Docker Swarm集群）中。

**周一：准备CD流水线的基础设施**

*   **任务一：规划部署环境与分支策略 (负责人：主程/架构师 & 运维)**
    1.  **目标**: 明确不同环境的用途和触发部署的分支。
    2.  **行动**:
        *   **生产环境 (Production)**: 对应我们的5台云服务器集群。触发条件是代码**合并到`main`分支**。
        *   **预发布/测试环境 (Staging)**: **强烈建议**搭建一个独立的、配置较低的“迷你版”生产环境（比如1台API服务器+1台Redis/DB服务器）。触发条件是代码**合并到`develop`分支**。
        *   **好处**: 这提供了一个安全的“缓冲区”，所有变更在进入生产前，都可以在一个与生产环境高度一致的Staging环境中进行最终的验证。
    3.  **产出**: 一份清晰的分支策略与环境对应关系的文档。

*   **任务二：配置部署所需的Secrets (负责人：主程/架构师 & 运维)**
    1.  **目标**: 将所有敏感的认证信息，安全地提供给GitHub Actions使用。
    2.  **行动**:
        *   进入GitHub仓库的`Settings -> Secrets and variables -> Actions`页面。
        *   **创建Repository Secrets**:
            *   **`DOCKER_USERNAME`**: 登录镜像仓库的用户名。
            *   **`DOCKER_PASSWORD`**: 登录镜像仓库的密码或访问令牌（推荐）。
            *   **`SSH_HOST`**: 您的**Swarm Manager节点**（如`api-server-1`）的公网IP地址。
            *   **`SSH_USER`**: 用于SSH登录的用户名（如`ubuntu`）。
            *   **`SSH_PRIVATE_KEY`**: 用于SSH免密登录的**私钥**。
            *   **(可选) `SLACK_WEBHOOK_URL`**: 用于发送部署通知的Slack Webhook地址。
    3.  **产出**: 所有CI/CD流水线中需要用到的敏感凭证，都已安全地存储在GitHub Secrets中。

**周二：构建并推送Docker镜像**

*   **任务一：创建CD Workflow文件 (负责人：主程/架构师)**
    1.  **目标**: 建立一个独立的、只在代码合并到主干时触发的部署流水线。
    2.  **行动**:
        *   在`.github/workflows/`目录下，创建`cd.yml`文件。
        *   **`name`**: `Continuous Deployment`。
        *   **`on`**: 配置触发条件。
            ```yaml
            on:
              push:
                branches:
                  - main # 当有代码推送到main分支时触发
            ```
    3.  **产出**: 一个基础的`cd.yml`文件。

*   **任务二：实现镜像的自动化构建与推送 (负责人：全体开发)**
    1.  **目标**: 将合并到`main`分支的最新代码，自动构建成带版本号的Docker镜像，并推送到镜像仓库。
    2.  **行动**: 在`cd.yml`中，添加以下核心步骤：
        *   **代码检出**: `actions/checkout@v3`。
        *   **登录镜像仓库**: 使用`docker/login-action@v2`，并引用我们创建的`DOCKER_USERNAME`和`DOCKER_PASSWORD` secrets。
        *   **生成镜像标签**: 使用`docker/metadata-action@v4`或简单的shell脚本，生成两个Tag：
            *   一个是基于Git Commit短哈希的**唯一版本标签**，如`your-repo/permission-api:a1b2c3d`。
            *   另一个是**`latest`标签**，始终指向最新的版本。
        *   **构建并推送**: 使用`docker/build-push-action@v4`。
            *   设置`push: true`。
            *   将上一步生成的两个标签都作为`tags`参数传入。
    3.  **产出**: 一个完整的、能将最新代码自动发布为Docker镜像的流水线。可以尝试合并一个小的变更到`main`分支，然后去镜像仓库检查是否出现了新的带版本号的镜像。

**周三 & 周四：实现自动化部署到Docker Swarm**

*   **任务一：编写部署脚本 (负责人：主程/架构师 & 运维)**
    1.  **目标**: 封装一个简单、可靠的部署命令，用于在服务器上执行。
    2.  **行动**:
        *   我们可以直接在GitHub Actions的`script`部分编写命令，但更好的方式是在代码仓库中创建一个`deploy/deploy.sh`脚本，更易于管理和测试。
        *   **`deploy/deploy.sh`**:
            ```bash
            #!/bin/bash
            set -e # 任何命令失败则立即退出

            IMAGE_TAG=${1:-latest} # 接收一个镜像标签作为参数，默认为latest
            STACK_NAME="api-stack"
            SERVICE_NAME="api-service"

            echo "Deploying image: your-docker-repo/permission-api:${IMAGE_TAG}"

            # 核心命令：使用新镜像更新Swarm中的服务
            # --with-registry-auth 确保worker节点能拉取私有镜像
            docker service update \
              --image your-docker-repo/permission-api:${IMAGE_TAG} \
              --with-registry-auth \
              ${STACK_NAME}_${SERVICE_NAME}

            echo "Service ${SERVICE_NAME} updated successfully!"
            ```
    3.  **产出**: 一个标准化的、可复用的部署脚本。

*   **任务二：在GitHub Actions中执行远程部署 (负责人：全体开发)**
    1.  **目标**: 在镜像推送成功后，安全地SSH连接到Swarm Manager服务器，并执行我们的部署脚本。
    2.  **行动**: 在`cd.yml`的最后，添加核心的部署步骤：
        *   使用`appleboy/ssh-action@master`这个广受好评的Action。
        *   配置`host`, `username`, `key`参数，引用我们创建的SSH相关Secrets。
        *   在`script`部分，调用我们编写的部署脚本，并**传入Git Commit哈希作为版本标签**。
            ```yaml
            - name: Deploy to Production Swarm
              uses: appleboy/ssh-action@master
              with:
                host: ${{ secrets.SSH_HOST }}
                username: ${{ secrets.SSH_USER }}
                key: ${{ secrets.SSH_PRIVATE_KEY }}
                script: |
                  cd /opt/my-app/deploy # 假设脚本在这个目录
                  # 将Git Commit的短哈希作为参数传递给部署脚本
                  bash deploy.sh ${{ github.sha }} 
            ```
    3.  **产出**: 一条完整的、从代码合并到服务上线的全自动化CD流水线。

**周五：部署演练、完善与通知**

*   **任务一：Staging环境部署演练 (负责人：全体开发)**
    1.  **目标**: 在进入生产环境前，对整个CD流程进行一次完整的、端到端的演练。
    2.  **行动**:
        *   复制`cd.yml`为`cd-staging.yml`，将其触发分支改为`develop`。
        *   配置Staging环境对应的SSH Secrets。
        *   团队成员创建一个PR到`develop`分支，走完CI流程，然后合并。
        *   **集体观察**Staging环境的CD流水线是否成功运行，服务是否按预期被更新。
    3.  **产出**: 验证了CD流程的正确性，并为生产部署建立了信心。

*   **任务二：集成部署通知 (负责人：主程/架构师)**
    1.  **目标**: 让团队能够实时感知每一次部署的状态。
    2.  **行动**:
        *   在`cd.yml`的最后，增加一个“Send Notification”的步骤。
        *   使用社区现成的Slack/Discord/DingTalk Action。
        *   根据流水线的成功或失败状态，发送不同的消息。
            *   **成功消息**: “✅ [Production] Deployment successful! Commit `${{ github.sha }}` by `${{ github.actor }}` is now live.”
            *   **失败消息**: “❌ [Production] Deployment FAILED! Please check the Actions log.”
    3.  **产出**: 一个具备即时反馈能力的、对团队透明的部署流程。

*   **任务三：周会总结与发布**
    1.  **目标**: 向团队正式宣布新的自动化部署流程上线，并明确发布规范。
    2.  **行动**:
        *   演示从PR合并到`main`分支，再到生产环境服务被自动更新，最后Slack收到通知的全过程。
        *   明确团队的发布纪律：**所有上线都必须通过PR合并到`main`分支的方式进行，严禁任何形式的手动SSH登录服务器修改代码的行为。**

完成这激动人心的第三周，您的团队将真正进入**现代化的DevOps时代**。软件交付不再是一件充满压力和风险的“大事”，而是变成了一个**平平无奇、随时可以进行、且高度可靠的自动化流程**。这将极大地解放您的生产力，让团队可以将更多精力投入到创造真正的业务价值上。