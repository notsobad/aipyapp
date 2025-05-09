#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import os
import ctypes
import platform

MESSAGES = {
    'zh': {
        'start_instruction': '开始处理指令',
        'start_execute': '开始执行代码块',
        'execute_result': '执行结果',
        'start_feedback': '开始反馈结果',
        'end_instruction': '结束处理指令',
        'no_context': '未找到上下文信息',
        'upload_success': '文章上传成功',
        'upload_failed': '上传失败 (状态码: {})',
        'reset_warning': '严重警告：这将重新初始化❗❗❗',
        'reset_confirm': '如果你确定要继续，请输入 y',
        'llm_response': '响应',
        'env_description': '环境变量名称和意义',
        'description': '描述',
        'unknown_format': '不支持的文件格式',
        'ask_for_packages': '申请安装第三方包',
        'agree_packages': '如果同意，请输入',
        'ask_for_env': '申请获取环境变量 {}，用途',
        'env_exist': '环境变量 {} 存在，返回给代码使用',
        'input_env': '未找到环境变量 {}，请输入',
        'call_failed': '调用失败',
        'think': '思考',
        'publish_disabled': "当前环境不支持发布",
        'auto_confirm': '自动确认',
        'packages_exist': '申请的第三方包已经安装',
        'thinking': '正在绞尽脑汁思考中，请稍等6-60秒',
        'no_available_llm': '没有可用的 LLM，请检查配置文件',
        'banner1_python': "请用 ai('任务') 输入需要 AI 处理的任务 (输入 ai.use(llm) 切换下述 LLM：",
        'banner1': "请输入需要 AI 处理的任务 (输入 /use <下述 LLM> 切换，输入 /info 查看系统信息)",
        'default': '默认',
        'enabled': '已启用',
        'ai_mode_enter': '进入 AI 模式，开始处理任务，输入 Ctrl+d 或 /done 结束任务',
        'ai_mode_exit': "[退出 AI 模式]",
        'ai_mode_unknown_command': "[AI 模式] 未知命令",
        'Task Summary': '任务总结',
        'Round': '轮次',
        'Time(s)': '时间(秒)',
        'In Tokens': '输入令牌数',
        'Out Tokens': '输出令牌数',
        'Total Tokens': '总令牌数',
        'sending_task': '正在向 {} 下达任务',
        'error_loading_config': "加载配置时出错: {}",
        'config_file_error': "请检查配置文件路径和格式。",
        'config_not_loaded': "配置尚未加载。",
        'llm_config_not_found': "缺少 'llm' 配置。",
        'not usable': "不可用",
        'permission_denied_error': "无权限创建目录: {}",
        'error_creating_config_dir': "创建配置目录时出错: {}",
        'migrate_config': "成功的将旧版本trustoken配置迁移到 {}",
        'migrate_user_config': "成功的将旧版本用户配置迁移到 {}",
        'binding_request_sent': "绑定请求发送成功。\n请求ID: {}\n\n>>> 请在已认证设备的浏览器中打开以下链接以批准:\n>>> {}\n\n(该链接将在{}秒后过期)",
        'scan_qr_code': "或者扫描下方二维码：",
        'config_help': "推荐您手机扫码绑定AiPy大脑，您也可以配置第三方大模型大脑，详情参考：https://d.aipy.app/d/77",
        'qr_code_display_failed': "(无法显示二维码: {})\n",
        'coordinator_request_error': "连接到协调服务器或请求时出错: {}",
        'unexpected_request_error': "请求过程中发生意外错误: {}",
        'waiting_for_approval': "浏览器已打开Trustoken网站，请注册或登录授权",
        'current_status': "当前状态: {}...",
        'binding_expired': "\n绑定请求已过期。",
        'unknown_status': "\n收到未知状态: {}",
        'coordinator_polling_error': "轮询协调服务器时出错: {}",
        'unexpected_polling_error': "轮询过程中发生意外错误: {}",
        'polling_cancelled': "\n用户取消了轮询。",
        'polling_timeout': "\n轮询超时。",
        'start_binding_process': "当前环境缺少必需的配置文件，开始进行配置初始化流程，与trustoken账号绑定即可自动获取配置...",
        'binding_success': "\n绑定流程已成功完成。",
        'binding_failed': "\n绑定流程失败或未完成。",
        'binding_request_failed': "\n绑定请求发起失败。",
        'cancel': "取消",
        'trust_token_auth': "TrustToken 认证",
        'Error': "错误",
        'Time remaining': "剩余时间：{} 秒",
        'approved': "已批准",
        'expired': "已过期",
        'pending': "待处理",
        'unknown_status': "收到未知状态: {}",
        'attempting_migration': '发现旧的配置文件: {}\n尝试从这些文件迁移配置...\n迁移之后，这些文件会被备份到 {}，请注意查看。',
        'task_saved': '结果文件已保存',
        'env_info': '当前配置文件目录：{} 工作目录: {}',
        'sys_info': '系统信息',
        'Save chat history as HTML': '保存聊天记录为 HTML',
        'Clear chat': '清空聊天',
        'Exit': '退出',
        'Start new task': '开始新任务',
        'Website': '官网',
        'Forum': '论坛',
        'WeChat Group': '微信群',
        'About': '关于',
        'Help': '帮助',
        'File': '文件',
        'Edit': '编辑',
        'Task': '任务',
        'Current task has ended': '当前任务已结束',
        'Operation in progress, please wait...': '操作进行中，请稍候...',
        'Operation completed. If you want to start the next task, please click the "End" button': '操作完成。如果开始下一个任务，请点击"结束"按钮',
        'Press Ctrl+Enter to send message': '按 Ctrl+Enter 发送消息',
        'Save chat history as HTML file': '保存聊天记录为 HTML 文件',
        'Exit program': '退出程序',
        'Clear all messages': '清除所有消息',
        'Start a new task': '开始一个新任务',
        'Official website': '官方网站',
        'Official forum': '官方论坛',
        'Official WeChat group': '官方微信群',
        'About AIPY': '关于爱派',
        'Configuration': '配置',
        'Configure program parameters': '配置程序参数',
        'Work Directory': '工作目录',
        'Browse...': '浏览...',
        'Select work directory': '选择工作目录',
        'Max Tokens': '最大Token数',
        'Timeout (seconds)': '超时时间(秒)',
        'Max Rounds': '最大执行轮数',
        'OK': '确定',
        'Cancel': '取消',
        'AIPY is an intelligent assistant that can help you complete various tasks.': '爱派是一个智能助手，可以帮助您完成各种任务。',
        'Current configuration directory': '当前配置目录',
        'Current working directory': '当前工作目录',
        'Version': '版本',
        'AIPY Team': '爱派团队',
        'You can create a new directory in the file dialog': '您可以在文件对话框中选择或创建新目录',
        'Settings': '设置',
        'Open work directory': '打开工作目录',
        'Open work directory in file manager': '在文件管理器中打开工作目录',
        'requesting_binding': '正在申请绑定',
        'Update available': '发现新版本',
        "tt_base_url": "https://api.trustoken.cn/v1",
        "tt_coordinator_url": "https://www.trustoken.cn/api",
    },
    'en': {
        'start_instruction': 'Start processing instruction',
        'start_execute': 'Start executing code block',
        'execute_result': 'Execution result',
        'start_feedback': 'Start sending feedback',
        'end_instruction': 'End processing instruction',
        'no_context': 'No context information found',
        'upload_success': 'Article uploaded successfully',
        'upload_failed': 'Upload failed (status code: {})',
        'reset_warning': 'Severe warning: This will reinitialize❗❗❗',
        'reset_confirm': 'If you are sure to continue, enter y',
        'llm_response': 'reply',
        'env_description': 'Environment variable name and meaning',
        'description': 'Description',
        'unknown_format': 'Unsupported file format',
        'ask_for_packages': 'Request to install third-party packages',
        'agree_packages': 'If you agree, please enter',
        'ask_for_env': 'Request to obtain environment variable {}, purpose',
        'env_exist': 'Environment variable {} exists, returned for code use',
        'input_env': 'Environment variable {} not found, please enter',
        'call_failed': 'Call failed',
        'think': 'Think',
        'publish_disabled': "Current environment does not support publishing",
        'auto_confirm': 'Auto confirm',
        'packages_exist': 'Third-party packages have been installed',
        'thinking': 'is thinking hard, please wait 6-60 seconds',
        'no_available_llm': 'No available LLM, please check the configuration file',
        'banner1_python': "Please use ai('task') to enter the task to be processed by AI (enter ai.use(llm) to switch to the following LLM:",
        'banner1': "Please enter the task to be processed by AI (enter /use <following LLM> to switch, enter /info to view system information)",
        'default': 'Default',
        'enabled': 'Enabled',
        'ai_mode_enter': 'Enter AI mode, start processing tasks, enter Ctrl+d or /done to end the task',
        'ai_mode_exit': "[Exit AI mode]",
        'ai_mode_unknown_command': "[AI mode] Unknown command",
        'Task Summary': 'Task Summary',
        'Round': 'Round',
        'Time(s)': 'Time(s)',
        'In Tokens': 'In Tokens',
        'Out Tokens': 'Out Tokens',
        'Total Tokens': 'Total Tokens',
        'sending_task': 'Sending task to {}',
        'error_loading_config': "Error loading configuration: {}",
        'config_file_error': "Please check the configuration file path and format.",
        'config_not_loaded': "Configuration not loaded.",
        'llm_config_not_found': "Missing 'llm' configuration.",
        'not usable': "Not usable",
        'permission_denied_error': "Permission denied to create directory: {}",
        'error_creating_config_dir': "Error creating configuration directory: {}",
        'migrate_config': "Successfully migrated old version trustoken configuration to {}",
        'migrate_user_config': "Successfully migrated old version user configuration to {}",
        'binding_request_sent': "Binding request sent successfully.\nRequest ID: {}\n\n>>> Please open this URL in your browser on an authenticated device to approve:\n>>> {}\n\n(This link expires in {} seconds)",
        'scan_qr_code': "Or scan the QR code below:",
        'config_help': "We recommend you scan the QR code to bind the AiPy brain, you can also configure a third-party large model brain, details refer to: https://d.aipy.app/d/77",
        'qr_code_display_failed': "(Could not display QR code: {})\n",
        'coordinator_request_error': "Error connecting to coordinator or during request: {}",
        'unexpected_request_error': "An unexpected error occurred during request: {}",
        'waiting_for_approval': "Browser has opened the Trustoken website, please register or login to authorize",
        'current_status': "Current status: {}...",
        'binding_expired': "\nBinding request expired.",
        'unknown_status': "\nUnknown status received: {}",
        'coordinator_polling_error': "Error connecting to coordinator during polling: {}",
        'unexpected_polling_error': "An unexpected error occurred during polling: {}",
        'polling_cancelled': "\nPolling cancelled by user.",
        'polling_timeout': "\nPolling timed out.",
        'start_binding_process': "The current environment lacks the required configuration file. Starting the configuration initialization process to bind with the Trustoken account...",
        'binding_success': "\nBinding process completed successfully.",
        'binding_failed': "\nBinding process failed or was not completed.",
        'binding_request_failed': "\nFailed to initiate binding request.",
        'cancel': "Cancel",
        'trust_token_auth': "TrustToken Authentication",
        'Error': "Error",
        'Time remaining': "Time remaining: {} seconds",
        'approved': "Approved",
        'expired': "Expired",
        'pending': "Pending",
        'unknown_status': "Received unknown status: {}",
        'attempting_migration': 'Found old configuration files: {}\nAttempting to migrate configuration from these files...\nAfter migration, these files will be backed up to {}, please check them.',
        'task_saved': 'Result file saved',
        'env_info': 'Current configuration file directory: {} Working directory: {}',
        'sys_info': 'System information',
        'Save chat history as HTML': 'Save chat history as HTML',
        'Clear chat': 'Clear chat',
        'Exit': 'Exit',
        'Start new task': 'Start new task',
        'Website': 'Website',
        'Forum': 'Forum',
        'WeChat Group': 'WeChat Group',
        'About': 'About',
        'Help': 'Help',
        'File': 'File',
        'Edit': 'Edit',
        'Task': 'Task',
        'Current task has ended': 'Current task has ended',
        'Operation in progress, please wait...': 'Operation in progress, please wait...',
        'Operation completed. If you want to start the next task, please click the "End" button': 'Operation completed. If you want to start the next task, please click the "End" button',
        'Press Ctrl+Enter to send message': 'Press Ctrl+Enter to send message',
        'Save chat history as HTML file': 'Save chat history as HTML file',
        'Exit program': 'Exit program',
        'Clear all messages': 'Clear all messages',
        'Start a new task': 'Start a new task',
        'Official website': 'Official website',
        'Official forum': 'Official forum',
        'Official WeChat group': 'Official WeChat group',
        'About AIPY': 'About AIPY',
        'Configuration': 'Configuration',
        'Configure program parameters': 'Configure program parameters',
        'Work Directory': 'Work Directory',
        'Browse...': 'Browse...',
        'Select work directory': 'Select work directory',
        'Max Tokens': 'Max Tokens',
        'Timeout (seconds)': 'Timeout (seconds)',
        'Max Rounds': 'Max Rounds',
        'OK': 'OK',
        'Cancel': 'Cancel',
        'AIPY is an intelligent assistant that can help you complete various tasks.': 'AIPY is an intelligent assistant that can help you complete various tasks.',
        'Current configuration directory': 'Current configuration directory',
        'Current working directory': 'Current working directory',
        'Version': 'Version',
        'AIPY Team': 'AIPY Team',
        'You can create a new directory in the file dialog': 'You can create a new directory in the file dialog',
        'Settings': 'Settings',
        'Open work directory': 'Open work directory',
        'Open work directory in file manager': 'Open work directory in file manager',
        'requesting_binding': 'Request binding',
        'Update available': 'Update available',
        "tt_base_url": "https://sapi.trustoken.ai/v1",
        "tt_coordinator_url": "https://www.trustoken.ai/api",
    }
}

__lang__ = 'en'

def set_lang(lang=None):
    global __lang__, MESSAGES
    if lang and lang in MESSAGES:
        __lang__ = lang
        return
    
    language, _ = locale.getlocale()
    if language:
        language = language.lower()
        if language.find('china') >=0 or language.find('chinese') >= 0 or language.find('zh_') >= 0:
            __lang__ = 'zh'

def T(key, *args):
    msg = MESSAGES[__lang__][key]
    return msg.format(*args) if args else msg

def get_system_language() -> str:
    """
    获取当前运行环境的语言代码 (例如 'en', 'zh')。
    支持 Windows, macOS, Linux。
    返回小写的语言代码，如果无法确定则返回 'en'。
    """
    language_code = 'en' # 默认英语

    try:
        if platform.system() == "Windows":
            # Windows: 使用 GetUserDefaultUILanguage 或 GetSystemDefaultUILanguage
            # https://learn.microsoft.com/en-us/windows/win32/intl/language-identifiers
            windll = ctypes.windll.kernel32
            # GetUserDefaultUILanguage 返回当前用户的UI语言ID
            lang_id = windll.GetUserDefaultUILanguage()
            # 将语言ID转换为标准语言代码 (例如 1033 -> en, 2052 -> zh)
            # 主要语言ID在低10位
            primary_lang_id = lang_id & 0x3FF
            if primary_lang_id == 0x04: # zh - Chinese
                language_code = 'zh'
            elif primary_lang_id == 0x09: # en - English
                language_code = 'en'
            # 可以根据需要添加更多语言ID映射
            # 参考: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-lcid/a9eac961-e77d-41a6-90a5-ce1a8b0cdb9c

        elif platform.system() == "Darwin": # macOS
            # macOS: 优先使用 locale.getlocale()
            language, encoding = locale.getlocale()
            if language:
                language_code = language.split('_')[0].lower()
            else:
                # 备选方案: 读取环境变量
                lang_env = os.environ.get('LANG')
                if lang_env:
                    language_code = lang_env.split('_')[0].lower()

        else: # Linux/Unix
            # Linux/Unix: 优先使用 locale.getlocale()
            language, encoding = locale.getlocale()
            if language:
                language_code = language.split('_')[0].lower()
            else:
                # 备选方案: 读取环境变量 LANG 或 LANGUAGE
                lang_env = os.environ.get('LANG') or os.environ.get('LANGUAGE')
                if lang_env:
                    language_code = lang_env.split('_')[0].lower()

        # 规范化常见的中文代码
        if language_code.startswith('zh'):
            language_code = 'zh'

    except Exception:
        # 如果发生任何错误，回退到默认值 'en'
        pass # 使用默认的 'en'

    return language_code

set_lang()
