#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale

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
        'thinking': '正在努力思考中，请稍等6-60秒',
        'no_available_llm': '没有可用的 LLM，请检查配置文件',
        'banner1_python': "请用 ai('任务') 输入需要 AI 处理的任务 (输入 ai.use(llm) 切换 下述 LLM：",
        'banner1': "请输入需要 AI 处理的任务 (输入 /use llm 切换 下述LLM)",
        'default': '默认',
        'available': '可用',
        'ai_mode_enter': '进入 AI 模式，开始处理任务，输入 Ctrl+d 或 /done 结束任务',
        'ai_mode_exit': "[退出 AI 模式]",
        'ai_mode_unknown_command': "[AI 模式] 未知命令",
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
        'banner1': "Please enter the task to be processed by AI (enter /use llm to switch to the following LLM)",
        'default': 'Default',
        'available': 'Available',
        'ai_mode_enter': 'Enter AI mode, start processing tasks, enter Ctrl+d or /done to end the task',
        'ai_mode_exit': "[Exit AI mode]",
        'ai_mode_unknown_command': "[AI mode] Unknown command",
    }
}

lang = 'en'
language, _ = locale.getlocale()
if language:
    language = language.lower()
    if language.find('china') >=0 or language.find('chinese') >= 0 or language.find('zh_') >= 0:
        lang = 'zh'

def T(key, *args):
    msg = MESSAGES[lang][key]
    return msg.format(*args) if args else msg
