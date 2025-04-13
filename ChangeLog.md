
# 0.1.21
- 修补没有因为没有 _tkinter 的启动错误
- 增加自动执行轮数限制：
 - `max_round` 配置
 - Python 模式下，ai("任务", max_rounds=10000000) 临时调整
 - 默认 16
- Python 模式：ai.config_files 数组包含加载的配置文件
- 自动修改用户提示词
- hook os.getenv
- 增加 __blocks__ 变量
- 修改系统提示词
- 重新实现返回信息解析逻辑
- 删除 agent.py，增加 taskmgr.py 和 task.py
- 支持 exit 命令
- 增加免责声明
- 调整 Live 显示

# 0.1.20
- 增加 Azure API 支持
- 重构 LLM 实现
  - 延迟 import
  - 可用性自动检测
- 更新 help 描述
- 增加 ChangeLog

# 0.1.19
- 内置字体支持，希望解决绘图时的中文乱码问题
- 增加位置参数，直接命令行执行任务：`aipy "who are you?"`
