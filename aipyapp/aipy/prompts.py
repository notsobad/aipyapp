#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os
import locale
import platform
import inspect
import json
import shutil
import subprocess
import re
from datetime import datetime
from typing import List, TYPE_CHECKING, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import __respath__
from .toolcalls import ToolCallResult

if TYPE_CHECKING:
    from .task import Task

class PromptFeatures:
    """
    灵活的功能开关管理类，支持任意字符串功能名称
    """
    def __init__(self, features: Optional[Dict[str, bool]] = None):
        self.features = features or {}

    def has(self, feature_name: str) -> bool:
        """检查功能是否存在且为true"""
        return self.features.get(feature_name, False)

    def enabled(self, feature_name: str) -> bool:
        """has的别名"""
        return self.has(feature_name)

    def get(self, feature_name: str, default: bool = False) -> bool:
        """获取功能值，支持默认值"""
        return self.features.get(feature_name, default)

    def set(self, feature_name: str, value: bool):
        """设置功能值"""
        self.features[feature_name] = value

    def update(self, features: Dict[str, bool]):
        """批量更新功能"""
        self.features.update(features)

    def to_dict(self) -> Dict[str, bool]:
        """转换为字典"""
        return self.features.copy()

def check_commands(commands):
    """
    检查多个命令是否存在，并获取其版本号。
    :param commands: dict，键为命令名，值为获取版本的参数（如 ["--version"]）
    :return: dict，例如 {"node": "v18.17.1", "bash": "5.1.16", ...}
    """
    result = {}

    for cmd, version_args in commands.items():
        path = shutil.which(cmd)
        if not path:
            result[cmd] = None
        else:
            result[cmd] = path
        continue

        try:
            proc = subprocess.run(
                [cmd] + version_args,
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8'
            )
            # 合并 stdout 和 stderr，然后提取类似 1.2.3 或 v1.2.3 的版本
            output = (proc.stdout or '') + (proc.stderr or '')
            version_match = re.search(r"\bv?\d+(\.\d+){1,2}\b", output)
            version = version_match.group(0) if version_match else output.strip()
            result[cmd] = version
        except Exception as e:
            pass

    return result

class Prompts:
    def __init__(self, template_dir: str = None, features: Optional[Dict]= None):
        if not template_dir:
            template_dir = __respath__ / 'prompts'
        self.template_dir = os.path.abspath(template_dir)
        self.env = Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            loader=FileSystemLoader(self.template_dir),
            #autoescape=select_autoescape(['j2'])
        )
        self._init_env(features)  # 调用 _init_env 方法注册全局变量

    def _init_env(self, features: Optional[Dict[str, bool]] = None):
        # 可以在这里注册全局变量或 filter
        commands_to_check = {
            "node": ["--version"],
            "bash": ["--version"],
            #"powershell": ["-Command", "$PSVersionTable.PSVersion.ToString()"],
            "osascript": ["-e", 'return "AppleScript OK"']
        }
        self.env.globals['commands'] = check_commands(commands_to_check)
        osinfo = {'system': platform.system(), 'platform': platform.platform(), 'locale': locale.getlocale()}
        self.env.globals['os'] = osinfo
        self.env.globals['python_version'] = platform.python_version()
        self.env.filters['tojson'] = lambda x: json.dumps(x, ensure_ascii=False, default=str)

        # 注册默认的 features 对象
        self.env.globals['features'] = PromptFeatures(features or {})

    def get_prompt(self, template_name: str, **kwargs) -> str:
        """
        加载指定模板并用 kwargs 渲染
        :param template_name: 模板文件名（如 'my_prompt.txt'）
        :param kwargs: 用于模板渲染的关键字参数
        :return: 渲染后的字符串
        """
        template_name = f"{template_name}.j2"
        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            raise FileNotFoundError(f"Prompt template not found: {template_name} in {self.template_dir}") from e
        return template.render(**kwargs)

    def get_default_prompt(self, **kwargs) -> str:
        """
        使用 default.jinja 模板，自动补充部分变量后渲染
        :param role: 角色对象，用于加载角色特定的功能开关
        :param kwargs: 用户传入的模板变量
        :return: 渲染后的字符串
        """
        return self.get_prompt('default', **kwargs)

    def get_task_prompt(self, instruction: str, gui: bool = False, parent: Task | None = None, lang: str = None) -> str:
        """
        获取任务提示
        :param instruction: 用户输入的字符串
        :param gui: 是否使用 GUI 模式
        :param parent: 父任务（如果有）
        :return: 渲染后的字符串
        """
        contexts = {}
        contexts['Today'] = datetime.now().strftime('%Y-%m-%d')
        if not gui:
            contexts['TERM'] = os.environ.get('TERM', 'unknown')
        constraints = {"lang": lang}
        return self.get_prompt('task', instruction=instruction, contexts=contexts, constraints=constraints, gui=gui, parent=parent)
    
    def get_toolcall_results_prompt(self, results: List[ToolCallResult]) -> str:
        """
        获取混合结果提示（包含执行和编辑结果）
        :param results: 混合结果字典
        :return: 渲染后的字符串
        """
        return self.get_prompt('toolcall_results', results=results)
    
    def get_chat_prompt(self, instruction: str, task: str) -> str:
        """
        获取聊天提示
        :param instruction: 用户输入的字符串
        :param task: 初始任务
        :return: 渲染后的字符串
        """
        return self.get_prompt('chat', instruction=instruction, initial_task=task)
    
    def get_parse_error_prompt(self, errors: list) -> str:
        """
        获取消息解析错误提示
        :param errors: 错误列表
        :return: 渲染后的字符串
        """
        return self.get_prompt('parse_error', errors=errors)
    
if __name__ == '__main__':
    prompts = Prompts()
    print(prompts.get_default_prompt())
    func = prompts.get_prompt
    print(func.__name__)
    print(inspect.signature(func))
    print(inspect.getdoc(func))
