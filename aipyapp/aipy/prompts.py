#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import locale
import platform
import inspect
import json
import shutil
import subprocess
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
            continue

        try:
            proc = subprocess.run(
                [cmd] + version_args,
                capture_output=True,
                text=True,
                timeout=5
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
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), '../res/prompts')
        self.template_dir = os.path.abspath(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            #autoescape=select_autoescape(['j2'])
        )
        self._init_env()  # 调用 _init_env 方法注册全局变量

    def _init_env(self):
        # 可以在这里注册全局变量或 filter
        commands_to_check = {
            "node": ["--version"],
            "bash": ["--version"],
            "powershell": ["-Command", "$PSVersionTable.PSVersion.ToString()"],
            "osascript": ["-e", 'return "AppleScript OK"']
        }
        self.env.globals['commands'] = check_commands(commands_to_check)
        osinfo = {'system': platform.system(), 'platform': platform.platform(), 'locale': locale.getlocale()}
        self.env.globals['os'] = osinfo
        self.env.globals['python_version'] = platform.python_version()
        self.env.filters['tojson'] = lambda x: json.dumps(x, ensure_ascii=False, default=str)

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
        :param kwargs: 用户传入的模板变量
        :return: 渲染后的字符串
        """
        # 自动补充变量
        extra_vars = {}
        all_vars = {**extra_vars, **kwargs}
        return self.get_prompt('default', **all_vars)

if __name__ == '__main__':
    prompts = Prompts()
    print(prompts.get_default_prompt())
    func = prompts.get_prompt
    print(func.__name__)
    print(inspect.signature(func))
    print(inspect.getdoc(func))
