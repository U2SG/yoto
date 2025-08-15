### **第二周工作计划：搭建自动化CI流水线**

**核心目标**: 实现**代码变更的自动化验证**。确保任何提交到代码库（尤其是准备合入主干的）的代码，都经过了严格的、一致的、自动化的质量检查。

**周一：初识GitHub Actions，建立基础流水线**

*   **任务一：创建第一个Workflow文件**
    1.  **目标**: 让GitHub Actions为我们的项目“跑起来”。
    2.  **行动**:
        *   在项目根目录下，创建`.github/workflows/`目录。
        *   在该目录下，创建`ci.yml`文件。
        *   编写最基础的Workflow配置：
            *   **`name`**: 为流水线命名，如`Continuous Integration Pipeline`。
            *   **`on`**: 配置触发条件。初期可以设置为`push: branches: [ main, develop ]`和`pull_request: branches: [ main, develop ]`。这意味着，当有代码推送到`main`或`develop`分支，或者有PR指向这两个分支时，流水线就会被触发。
            *   **`jobs`**: 定义一个名为`build_and_test`的任务。
            *   **`runs-on`**: 指定运行环境为`ubuntu-latest`。
    3.  **产出**: 一个基础的、能被GitHub识别和触发的`ci.yml`文件。

*   **任务二：实现代码检出与环境设置**
    1.  **目标**: 让流水线能获取到我们的代码，并准备好Python运行环境。
    2.  **行动**: 在`ci.yml`的`steps`中，添加两个官方的Action：
        *   使用`actions/checkout@v3`来检出最新的代码。
        *   使用`actions/setup-python@v4`来安装指定版本的Python（如3.10），并配置**依赖缓存**。
            *   **关键细节**: 在`setup-python`中，配置`cache: 'pip'`。这将缓存`pip`下载的包。对于后续的构建，如果`requirements.txt`没有变化，安装依赖的速度将从几分钟缩短到几秒钟，**极大提升流水线效率**。
    3.  **产出**: 一个能够自动检出代码、安装Python并缓存依赖的基础流水线。团队成员可以尝试创建一个PR，然后在GitHub的“Actions”标签页看到它成功运行。

**周二：集成代码规范检查 (Linting & Formatting)**

*   **任务一：将本地检查命令线上化**
    1.  **目标**: 把我们在第一周使用的`flake8`, `black`, `mypy`命令，搬到流水线中自动执行。
    2.  **行动**: 在`ci.yml`的`steps`中，在安装完依赖后，增加以下步骤：
        *   **安装开发依赖**: `run: pip install -r requirements-dev.txt`。
        *   **运行Flake8**: `run: flake8 . --count --show-source --statistics`。
        *   **运行Black**: `run: black --check .`。
        *   **运行MyPy**: `run: mypy app/`。
    3.  **产出**: 流水线现在具备了自动化代码规范检查的能力。任何不符合规范的代码提交，都会导致流水线**失败并亮起红灯**，在PR页面清晰可见。

*   **任务二：制定并推行“PR必须通过CI检查”的规范**
    1.  **目标**: 将CI流水线作为代码合入主干的**强制性门禁**。
    2.  **行动**:
        *   在GitHub仓库的`Settings -> Branches`中，为`main`和`develop`分支**添加分支保护规则 (Branch protection rule)**。
        *   勾选**“Require status checks to pass before merging”**，并将我们的CI任务（`build_and_test`）设置为**必需 (required)** 的检查项。
    3.  **产出**: 从此刻起，任何未通过CI检查的Pull Request，其“Merge”按钮将是**灰色的、不可点击的**。这从制度上保证了代码库的质量。

**周三 & 周四：集成自动化测试 (Unit & Integration Tests)**

*   **任务一：在CI环境中启动依赖服务**
    1.  **目标**: 为我们的集成测试，在CI环境中提供一个临时的、干净的数据库和Redis。
    2.  **行动**:
        *   在`ci.yml`的`jobs`部分，使用**`services`关键字**。
        *   定义一个`postgres`服务，使用`mysql:8-alpine`镜像，并设置好用户名、密码、数据库名等环境变量。
        *   定义一个`redis`服务，使用`redis:7-alpine`镜像。
        *   **关键细节**: GitHub Actions的`services`会自动为这些服务和主任务容器创建一个共享网络。你可以通过主机名`postgres`和`redis`以及默认端口，直接在测试代码中连接到它们。
    3.  **产出**: 一个带有临时数据库和Redis的、功能完备的测试环境。

*   **任务二：执行Pytest并处理环境变量**
    1.  **目标**: 在CI环境中运行我们在第一周编写的所有测试用例。
    2.  **行动**:
        *   在`ci.yml`的测试步骤中，通过`env`关键字设置**环境变量**，将数据库和Redis的连接地址指向`services`中定义的主机名（`DATABASE_URL=postgresql://user:pass@postgres:5432/testdb`, `REDIS_URL=redis://redis:6379`）。
        *   运行测试命令: `run: pytest --cov=app --cov-report=xml`。
            *   **关键细节**: `--cov-report=xml`会生成一个`coverage.xml`文件，这是下一步上传覆盖率报告所必需的。
    3.  **产出**: 流水线现在可以自动运行所有单元测试和集成测试。任何导致测试失败的代码提交，都会被CI流水线**无情地拦截**。

*   **任务三：集成Codecov实现覆盖率可视化**
    1.  **目标**: 将测试覆盖率报告直观地展示在每个Pull Request中，量化代码质量。
    2.  **行动**:
        *   在Codecov.io网站上，使用GitHub账号登录，并授权你的项目。
        *   从Codecov获取你的仓库上传令牌（`CODECOV_TOKEN`），并将其添加到GitHub仓库的**Secrets**中。
        *   在`ci.yml`的最后，添加`codecov/codecov-action@v3`这个Action。
        *   配置该Action，让它读取上一步生成的`coverage.xml`文件，并使用`secrets.CODECOV_TOKEN`进行上传。
    3.  **产出**: 每次提交PR后，Codecov机器人会自动在该PR下发表评论，清晰地展示出**“本次变更导致总覆盖率上升/下降了多少”**，并能高亮显示哪些代码行没有被测试覆盖到。

**周五：评审、优化与文档化**

*   **任务一：流水线优化**
    1  **目标**: 提升流水线运行效率和稳定性。
    2  **行动**:
        *   **并行化**: 如果未来测试时间过长，可以将`linting`和`testing`拆分为**两个并行的`job`**，以缩短总运行时间。
        *   **矩阵构建**: （可选）如果需要支持多个Python版本，可以使用`strategy: matrix`来自动为每个版本都运行一遍测试。
    3  **产出**: 一个更健壮、更高效的CI流水线。

*   **任务二：周会总结与文档化**
    1  **目标**: 确保团队所有成员都理解并能有效使用CI流水线。
    2  **行动**:
        *   **团队演示**: 在周会上，完整地演示一次“提交不规范代码 -> CI失败 -> 修复代码 -> CI通过 -> PR可以合并”的完整流程。
        *   **编写文档**: 在项目的`CONTRIBUTING.md`或Wiki中，添加一章节，详细说明：
            *   CI流水线的作用和检查项。
            *   如何解读CI失败的日志。
            *   分支保护策略和代码合并流程。
            *   如何查看测试覆盖率报告。
    3  **产出**: 一个**赋能团队**的、完整的CI流程和配套文档。

完成这“惊心动魄”的第二周后，您的团队开发模式将发生质的改变。代码质量将不再依赖于某个人的责任心，而是由**一套自动化的、不知疲倦的、公平公正的系统**来守护。您已经为下周构建**CD（持续部署）流水线**，实现“一键上线”，做好了最完美的铺垫。