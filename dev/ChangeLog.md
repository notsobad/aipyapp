# 0.1.29
## b0
- 修补打卡记录任务的代码错误
- 所有非代码文件都移到 res/ 目录下，例如 default.toml 和 HTML 模版等
- 增加 blocks.py
- 修改 aipy/config.py，__init__  参数里去掉 default.toml，改成内部获取
- 下任务接口里去掉 max_rounds 参数
- Merge MCP changes

# 0.1.28
- 日志记录
- aipyw.exe
- 更新检查
- GUI LLM 配置向导

## b25
- 删除 google-client 库
- 修改系统提示词，强调使用相同语言回复
- 增加任务时间统计
- 调整任务历史文件路径到 .aipyapp/
- 默认自动安装 Python 包

# 0.1.27
- 修补插件执行问题
- 修补 win 下 API 配置界面问题

# 0.1.25
- wxgui 增加结束任务功能
- wxgui 增加 --debug 参数
- 增加诊断接口
- 增加关于对话框
- 增加配置窗口
- 增加 TT 认证
- 修改 runtime.install_packages 定义
- 修补自动安装包问题
- 调整输入框字体
- 输入框可以拖入文件
- 状态栏增加打开工作目录功能


# 0.1.24
- 流式输出改为行输出
- 重构流式输出实现
- 实现 wxGUI 界面

# 0.1.23
- 自动安装包时支持配置国内 pypi 源
- 修补 ollama 问题
- 修补 Grok token 统计丢失问题
- 改进系统提示词
- 修改默认配置
- 增加 temperature 配置

# 0.1.22
- 修改 Docker 相关代码
- 多模型混合调用
- 任务自动保存和加载
- 定制提示词

# 0.1.21
- 修补没有因为没有 _tkinter 的启动错误
- 增加自动执行轮数限制：
 - `max_round` 配置
 - Python 模式下，ai("任务", max_rounds=10000000) 临时调整
 - 默认 16
- Python 模式：ai.config_files 数组包含加载的配置文件
- 自动修改用户提示词
- 增加 __blocks__ 变量
- 修改系统提示词
- 重新实现返回信息解析逻辑
- 删除 agent.py，增加 taskmgr.py 和 task.py
- 支持 exit 命令
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
