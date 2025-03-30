#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

lang = 'zh' #os.environ.get('LANG', 'en_US.UTF-8').split('.')[0].split('_')[0]

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
        'llm_response': 'LLM 响应',
        'env_description': '环境变量名称和意义',
        'description': '描述',
        'unknown_format': '不支持的文件格式',
        'ask_for_packages': '申请安装第三方包',
        'agree_packages': '如果同意且已安装，请输入',
        'ask_for_env': '申请获取环境变量 {}，用途',
        'env_exist': '环境变量 {} 存在，返回给代码使用',
        'input_env': '未找到环境变量 {}，请输入',
        'call_failed': '调用失败',
        'think': '思考',
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
        'llm_response': 'LLM reply',
        'env_description': 'Environment variable name and meaning',
        'description': 'Description',
        'unknown_format': 'Unsupported file format',
        'ask_for_packages': 'Request to install third-party packages',
        'agree_packages': 'If you agree and it’s installed, please enter',
        'ask_for_env': 'Request to obtain environment variable {}, purpose',
        'env_exist': 'Environment variable {} exists, returned for code use',
        'input_env': 'Environment variable {} not found, please enter',
        'call_failed': 'Call failed',
        'think': 'Think',
    }
}

def T(key, *args):
    msg = MESSAGES[lang][key]
    return msg.format(*args) if args else msg
