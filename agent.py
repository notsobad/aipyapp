#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import tomllib
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

import utils
from llm import LLM
from runner import Runner

class MsgType(Enum):
    CODE = "代码"
    TEXT = "文本"

class Agent(object):
    MAX_TOKENS = 4096

    def __init__(self, path):
        self.llm = None
        self.runner = None
        self._console = None
        self.path = path
        self.system_prompt = None
        self.max_tokens = None
        self._init()

    def load_config(self):
        config = tomllib.load(open(self.path, 'rb'))
        if 'llm' not in config or not config['llm']:
            raise ValueError("Invalid config file (no llm provider)")
        return config
    
    def _init(self):
        config = self.load_config()
        config_agent = config.get('agent', {})
        self._console = Console(record=config_agent.get('record', True))
        self.max_tokens = config_agent.get('max_tokens', self.MAX_TOKENS)
        self.system_prompt = config_agent.get('system_prompt')
        self.runner = Runner(self._console)
        self.llm = LLM(config['llm'], self.max_tokens)
        self.use = self.llm.use

        api = config.get('api')
        if api:
            lines = [self.system_prompt]
            for api_name, api_conf in api.items():
                lines.append(f"## {api_name} API")
                envs = api_conf.get('env', {})
                if envs:
                    lines.append("### 环境变量名称和意义")
                    for name, (value, desc) in envs.items():
                        value = value.strip()
                        if not value:
                            continue
                        var_name = name
                        lines.append(f"- {var_name}: {desc}")
                        self.runner.setenv(var_name, value, desc)
                desc = api_conf.get('desc')
                if desc: 
                    lines.append(f"### API 描述\n{desc}")
            self.system_prompt = "\n".join(lines)

    def reset(self, path=None):
        """ 重新读取配置文件和初始化所有对象 """
        yes = utils.confirm(self._console, "\n☠️⚠️💀 严重警告：这将重新初始化❗❗❗", "🔥 如果你确定要继续，请输入 'y")
        if not yes:
            return
        if path:
            self.path = path
        self._init()

    def clear(self):
        """ 清除上一个任务的所有数据
        - console 历史
        - 清除 llm 历史，设置 current llm 为 default
        - 清除 runner 历史，清除 env, 清除全局变量
        """
        #yes = utils.confirm(self._console, "\n☠️⚠️💀 严重警告：这将清除上一个任务的所有数据❗❗❗", "🔥 如果你确定要继续，请输入 'y")
        if True:
            self.llm.clear()
            self.runner.clear()        
            self._console._record_buffer.clear()

    def save(self, path, clear=False):
        path = Path(path)
        if path.suffix == '.svg':
            self._console.save_svg(path, clear=clear)
        elif path.suffix in ('.html', '.htm'):
            self._console.save_html(path, clear=clear)
        else:
            self._console.print(f"不支持的文件格式：{path}")

    def parse_reply(self, text):
        lines = text.split('\n')
        code_block = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith('```run'):
                in_code_block = True
                continue
            elif line.strip().startswith('```') and in_code_block:
                break
            if in_code_block:
                code_block.append(line)
        
        if code_block:
            ret = {'type': MsgType.CODE, 'code': '\n'.join(code_block)}
        else:
            ret = {'type': MsgType.TEXT, 'code': None}
        return ret
        
    def process_code_reply(self, msg):
        code_block = msg['code']
        self._console.print(f"\n⚡ 开始执行代码块:", Markdown(f"```python\n{code_block}\n```"))
        result = self.runner(code_block)
        result = json.dumps(result, ensure_ascii=False)
        self._console.print("✅ 执行结果:\n", Markdown(f"```json\n{result}\n```"))
        self._console.print("\n📤 开始反馈结果")
        feedback_response = self.llm(result)
        return feedback_response

    def __call__(self, instruction, api=None, llm=None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self._console.print("▶ [yellow]开始处理指令:", f'[red]{instruction}\n')
        system_prompt = None if self.llm.history else self.system_prompt
        response = self.llm(instruction, system_prompt=system_prompt, name=llm)
        while response:
            self._console.print("\n📥 LLM 响应:\n", Markdown(response))
            msg = self.parse_reply(response)
            if msg['type'] != MsgType.CODE:
                break
            response = self.process_code_reply(msg)
        self._console.print("\n⏹ 结束处理指令")

    def chat(self, prompt):
        system_prompt = None if self.llm.history else self.system_prompt
        response, ok = self.llm(prompt, system_prompt=system_prompt)
        self._console.print(Markdown(response))

    def step(self):
        response = self.llm.get_last_message()
        if not response:
            self._console.print("❌ 未找到上下文信息")
            return
        self.process_reply(response)
