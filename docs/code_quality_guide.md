# 代码质量指南

## 概述

本项目使用多种工具来确保代码质量和一致性：

- **Black**: 自动代码格式化
- **Flake8**: 代码质量检查
- **isort**: 导入语句排序
- **pre-commit**: 提交前自动检查

## 快速开始

### 1. 安装开发依赖

```bash
# 安装核心开发工具
pip install -r requirements-dev-simple.txt

# 或者安装完整开发依赖（如果编码没问题）
pip install -r requirements-dev.txt
```

### 2. 设置pre-commit钩子

```bash
# 安装pre-commit钩子
pre-commit install

# 在现有代码上运行所有钩子
pre-commit run --all-files
```

## 工具使用

### Black - 代码格式化

```bash
# 格式化单个文件
black yoto_backend/app/core/permission/permission_resilience.py

# 格式化整个目录
black yoto_backend/

# 格式化整个项目
black .

# 检查哪些文件需要格式化（不实际修改）
black --check .
```

### Flake8 - 代码质量检查

```bash
# 检查整个项目
flake8 .

# 检查特定目录
flake8 yoto_backend/

# 生成详细报告
flake8 --output-file=flake8_report.txt .
```

### isort - 导入排序

```bash
# 排序单个文件
isort yoto_backend/app/core/permission/permission_resilience.py

# 排序整个项目
isort .

# 检查哪些文件需要排序（不实际修改）
isort --check-only .
```

## IDE集成

### VS Code

在VS Code中安装以下扩展：
- Python
- Black Formatter
- Flake8

在settings.json中添加：

```json
{
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.flake8Args": ["--max-line-length=88"],
    "editor.formatOnSave": true,
    "python.sortImports.args": ["--profile", "black"]
}
```

### PyCharm

1. 安装Black插件
2. 配置External Tools：
   - Black: `black $FilePath$`
   - Flake8: `flake8 $FilePath$`
3. 设置保存时自动格式化

## 配置文件说明

### pyproject.toml

- **Black配置**: 行长度88，Python 3.8+兼容
- **isort配置**: 与Black兼容的导入排序
- **mypy配置**: 类型检查配置
- **pytest配置**: 测试框架配置

### .flake8

- **行长度**: 88字符（与Black一致）
- **忽略规则**: 忽略与Black冲突的错误码
- **复杂度阈值**: 函数复杂度不超过10
- **排除目录**: 忽略构建、缓存等目录

### .pre-commit-config.yaml

- **Black**: 自动格式化
- **isort**: 自动排序导入
- **Flake8**: 代码质量检查
- **安全检查**: Bandit安全检查
- **文件检查**: 文件结尾、YAML格式等

## 最佳实践

### 1. 提交前检查

每次提交前，pre-commit会自动运行以下检查：
- 代码格式化（Black）
- 导入排序（isort）
- 代码质量（Flake8）
- 安全检查（Bandit）

### 2. 手动检查

在开发过程中，可以手动运行检查：

```bash
# 格式化代码
black .

# 检查代码质量
flake8 .

# 运行所有检查
pre-commit run --all-files
```

### 3. 忽略规则

如果某些代码需要忽略检查，可以使用以下注释：

```python
# flake8: noqa
import some_unused_module  # noqa: F401

# 忽略特定错误
def complex_function():  # noqa: C901
    pass
```

### 4. 团队协作

- 所有团队成员都应该安装pre-commit钩子
- 提交前确保所有检查通过
- 定期运行完整的代码质量检查
- 及时修复发现的问题

## 故障排除

### 编码问题

如果遇到编码错误，使用简化的依赖文件：

```bash
pip install -r requirements-dev-simple.txt
```

### 性能问题

如果pre-commit运行太慢，可以：

1. 只运行特定钩子：
```bash
pre-commit run black
pre-commit run flake8
```

2. 跳过某些检查（临时）：
```bash
git commit --no-verify
```

### 配置冲突

如果工具配置有冲突：

1. 检查pyproject.toml中的配置
2. 确保.flake8与Black配置一致
3. 更新pre-commit配置

## 持续集成

在CI/CD流水线中，建议添加以下步骤：

```yaml
- name: Install dependencies
  run: pip install -r requirements-dev-simple.txt

- name: Run code formatting check
  run: black --check .

- name: Run code quality check
  run: flake8 .

- name: Run security check
  run: bandit -r yoto_backend/ -f json -o bandit-report.json
```

## 更新工具

定期更新工具版本：

```bash
# 更新pre-commit钩子
pre-commit autoupdate

# 更新依赖
pip install --upgrade black flake8 isort
```

## 贡献指南

1. 确保代码通过所有质量检查
2. 遵循项目的代码风格
3. 添加适当的测试
4. 更新相关文档

---

更多信息请参考：
- [Black文档](https://black.readthedocs.io/)
- [Flake8文档](https://flake8.pycqa.org/)
- [pre-commit文档](https://pre-commit.com/) 