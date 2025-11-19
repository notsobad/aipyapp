# PromptFeatures 功能开关机制

这是一个灵活的模板功能开关系统，允许通过配置文件或参数控制模板内容的包含。

## 核心特性

- **字符串驱动**: 支持任意功能名称，无需修改代码
- **配置驱动**: 通过角色配置文件控制功能开关
- **细粒度控制**: 可以控制模板内的具体功能块
- **向后兼容**: 保持现有 API 不变

## 使用方式

### 1. 参数传递方式

```python
from aipy.prompts import Prompts, PromptFeatures

prompts = Prompts()

# 创建功能开关
features = PromptFeatures({
    'survey_system': False,      # 禁用 Survey 系统
    'task_status_system': True,   # 启用任务状态系统
    'survey_examples': False      # 禁用 Survey 示例
})

# 使用功能开关
prompt = prompts.get_default_prompt(features=features)
```

### 2. 角色配置方式

在角色 TOML 文件中添加 `[features]` 节：

```toml
[features]
# 主要系统功能
survey_system = true
task_status_system = true

# Survey 细粒度控制
survey_overview = true
survey_usage_guidelines = true
survey_howto = true
survey_results_format = true
survey_best_practices = true
survey_examples = true
survey_optimization_tips = false

# Task Status 细粒度控制
task_priority_guidelines = true
task_header_format = true
task_status_types = true
task_examples = true
task_key_rules = true
task_decision_guide = true
```

### 3. 模板中的使用

在 Jinja2 模板中使用 `features.has()` 语法：

```jinja2
{# 控制整个功能块 #}
{% if features.has('survey_system') %}
<survey_guide>
...survey 内容...
{% endif %}

{# 控制细粒度功能 #}
{% if features.has('survey_examples') %}
<examples>
...示例内容...
</examples>
{% endif %}
```

## 支持的功能开关

### 主要系统功能

- **`survey_system`**: 整个 Survey 系统
- **`task_status_system`**: 整个任务状态系统

### Survey 细粒度控制

- **`survey_overview`**: Survey 概述部分
- **`survey_usage_guidelines`**: Survey 使用指南
- **`survey_howto`**: Survey 使用方法
- **`survey_results_format`**: Survey 结果格式说明
- **`survey_best_practices`**: Survey 最佳实践
- **`survey_examples`**: Survey 示例
- **`survey_optimization_tips`**: Survey 优化提示

### Task Status 细粒度控制

- **`task_priority_guidelines`**: 任务优先级指南
- **`task_header_format`**: 任务状态头部格式
- **`task_status_types`**: 任务状态类型说明
- **`task_examples`**: 任务状态示例
- **`task_key_rules`**: 任务关键规则
- **`task_decision_guide`**: 任务决策指南

## PromptFeatures API

### 基本方法

```python
features = PromptFeatures()

# 设置功能
features.set('survey_system', True)

# 检查功能
if features.has('survey_system'):
    print("Survey 系统已启用")

# 批量更新
features.update({
    'survey_examples': False,
    'task_status_system': True
})

# 获取功能值
enabled = features.get('custom_feature', default=False)

# 转换为字典
all_features = features.to_dict()
```

## 预设配置示例

### 最小模式
```python
minimal_features = PromptFeatures({
    'survey_system': False,
    'task_status_system': False,
    'survey_examples': False,
    'task_examples': False
})
```

### 调试模式
```python
debug_features = PromptFeatures({
    'survey_system': True,
    'task_status_system': True,
    'survey_optimization_tips': True,
    'survey_examples': True,
    'task_examples': True
})
```

## 扩展新功能

添加新的功能开关非常简单：

1. **在角色配置中添加新功能名**：
```toml
[features]
new_feature = true
```

2. **在模板中使用**：
```jinja2
{% if features.has('new_feature') %}
<new_feature>
...新功能内容...
</new_feature>
{% endif %}
```

无需修改任何 Python 代码！