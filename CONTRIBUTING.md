# 贡献指南

感谢您对Yoto项目的关注！本文档将指导您如何参与项目开发。

## 开发环境设置

### 1. 克隆项目

```bash
git clone https://github.com/your-username/yoto.git
cd yoto
```

### 2. 创建虚拟环境

```bash
python -m venv env
source env/bin/activate  # Linux/Mac
# 或
env\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 安装生产依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev-simple.txt
```

### 4. 设置pre-commit钩子

```bash
pre-commit install
```

## 开发流程

### 1. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

### 2. 开发代码

- 遵循项目的代码风格（Black格式化）
- 编写测试用例
- 确保代码通过所有质量检查

### 3. 提交代码

```bash
# 添加文件
git add .

# 提交（pre-commit会自动运行检查）
git commit -m "feat: add new feature"

# 推送到远程
git push origin feature/your-feature-name
```

### 4. 创建Pull Request

1. 在GitHub上创建Pull Request
2. 填写PR描述，说明变更内容
3. 等待CI检查通过
4. 请求代码审查

## CI/CD流水线

### 流水线检查项

我们的CI流水线包含以下检查：

1. **代码格式化检查** (Black)
   - 确保代码符合统一的格式标准
   - 行长度限制：88字符

2. **代码质量检查** (Flake8)
   - 检查代码风格和潜在问题
   - 复杂度控制
   - 未使用变量检查

3. **导入排序检查** (isort)
   - 确保导入语句按标准顺序排列
   - 与Black格式兼容

4. **安全检查** (Bandit)
   - 检查潜在的安全漏洞
   - 生成安全报告

5. **单元测试** (pytest)
   - 运行所有单元测试
   - 生成测试覆盖率报告
   - 支持多Python版本测试

6. **集成测试**
   - 在真实数据库环境中测试
   - 验证组件间集成

7. **性能测试** (可选)
   - 在PR时运行性能基准测试
   - 检测性能回归

### 查看CI结果

- 在GitHub PR页面查看CI状态
- 点击"Details"查看详细日志
- 查看测试覆盖率报告

### CI失败处理

如果CI失败，请：

1. 查看失败日志，了解具体错误
2. 在本地运行相同的检查命令
3. 修复问题后重新提交
4. 确保所有检查通过

## 代码规范

### 代码风格

- 使用Black进行自动格式化
- 行长度：88字符
- 使用4个空格缩进
- 使用UTF-8编码

### 命名规范

- 类名：PascalCase（如`UserManager`）
- 函数和变量：snake_case（如`get_user_info`）
- 常量：UPPER_SNAKE_CASE（如`MAX_RETRY_COUNT`）
- 文件名：snake_case（如`user_manager.py`）

### 文档规范

- 所有公共函数和类必须有文档字符串
- 使用Google风格的文档字符串
- 重要功能需要添加注释

### 测试规范

- 每个新功能必须有对应的测试
- 测试覆盖率不低于80%
- 使用描述性的测试名称
- 测试应该独立且可重复

## 分支策略

### 分支命名

- `main`: 主分支，用于生产环境
- `develop`: 开发分支，用于集成测试
- `feature/*`: 功能分支
- `fix/*`: 修复分支
- `hotfix/*`: 紧急修复分支

### 合并策略

1. **功能分支** → `develop`
   - 通过Pull Request合并
   - 需要代码审查
   - 必须通过所有CI检查

2. **develop** → `main`
   - 通过Pull Request合并
   - 需要代码审查
   - 必须通过所有CI检查
   - 建议在发布前进行充分测试

3. **hotfix** → `main`
   - 紧急修复直接合并到main
   - 事后必须同步到develop

## 代码审查

### 审查要点

1. **功能正确性**
   - 代码是否实现了预期功能
   - 是否有边界情况处理

2. **代码质量**
   - 代码是否清晰易读
   - 是否有重复代码
   - 是否有性能问题

3. **测试覆盖**
   - 是否有足够的测试
   - 测试是否有效

4. **安全性**
   - 是否有安全漏洞
   - 是否正确处理用户输入

### 审查流程

1. 创建Pull Request
2. 自动触发CI检查
3. 请求团队成员审查
4. 根据反馈修改代码
5. 审查通过后合并

## 发布流程

### 版本号规范

使用语义化版本号：`MAJOR.MINOR.PATCH`

- `MAJOR`: 不兼容的API变更
- `MINOR`: 向后兼容的功能新增
- `PATCH`: 向后兼容的问题修复

### 发布步骤

1. 在develop分支完成功能开发
2. 创建release分支
3. 更新版本号和更新日志
4. 合并到main分支
5. 创建GitHub Release
6. 部署到生产环境

## 问题报告

### Bug报告

请包含以下信息：

1. 问题描述
2. 重现步骤
3. 预期行为
4. 实际行为
5. 环境信息（操作系统、Python版本等）
6. 错误日志

### 功能请求

请包含以下信息：

1. 功能描述
2. 使用场景
3. 预期收益
4. 可能的实现方案

## 获取帮助

- 查看项目文档
- 搜索现有Issues
- 创建新的Issue
- 联系项目维护者

## 行为准则

- 尊重所有贡献者
- 保持专业和友善的交流
- 欢迎新手提问
- 积极帮助他人

---

感谢您的贡献！ 