#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
import requests
from enum import Enum
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.syntax import Syntax
from rich.console import Console
from rich.markdown import Markdown

from . import i18n
from . import utils
from .i18n import T
from .llm import LLM
from .runner import Runner

class MsgType(Enum):
    CODE = "CODE"
    TEXT = "TEXT"

class Agent():
    MAX_TOKENS = 4096
    CERT_PATH = Path('/tmp/aipy_client.crt')

    def __init__(self, settings, console=None):
        self.settings = settings
        self.instruction = None
        self.llm = None
        self.runner = None
        self._console = console
        self.system_prompt = None
        self.max_tokens = None
        self._init()

    def _init(self):
        config = self.settings
        lang = config.get('lang')
        if lang:
            i18n.lang = lang
        self._console = self._console or Console(record=config.get('record', True))
        self.max_tokens = config.get('max_tokens', self.MAX_TOKENS)
        self.system_prompt = config.get('system_prompt')
        self.runner = Runner(self._console, config)
        self.llm = LLM(self._console,config['llm'], self.max_tokens)
        self.use = self.llm.use

        api = config.get('api')
        if api:
            lines = [self.system_prompt]
            for api_name, api_conf in api.items():
                lines.append(f"## {api_name} API")
                envs = api_conf.get('env', {})
                if envs:
                    lines.append(f"### {T('env_description')}")
                    for name, (value, desc) in envs.items():
                        value = value.strip()
                        if not value:
                            continue
                        var_name = name
                        lines.append(f"- {var_name}: {desc}")
                        self.runner.setenv(var_name, value, desc)
                desc = api_conf.get('desc')
                if desc: 
                    lines.append(f"### API {T('description')}\n{desc}")
            self.system_prompt = "\n".join(lines)

    def reset(self, path=None):
        """ 重新读取配置文件和初始化所有对象 """
        self._console.print(f"\n☠️⚠️💀 {T('reset_warning')}")
        yes = utils.confirm(self._console, f"🔥 {T('reset_confirm')}")
        if not yes:
            return
        if path:
            self.path = path
        self._init()

    def clear(self):
        """ 清除上一个任务的所有数据
        - 清除 llm 历史，设置 current llm 为 default
        - 清除 runner 历史，清除 env, 清除全局变量
        """
        #yes = utils.confirm(self._console, "\n☠️⚠️💀 严重警告：这将清除上一个任务的所有数据❗❗❗", "🔥 如果你确定要继续，请输入 'y")
        if True:
            self.llm.clear()
            self.runner.clear()        

    def save(self, path, clear=True):
        path = Path(path)
        if path.suffix == '.svg':
            self._console.save_svg(path, clear=clear)
        elif path.suffix in ('.html', '.htm'):
            self._console.save_html(path, clear=clear)
        else:
            self._console.print(f"{T('unknown_format')}：{path}")

    def render_code(self, logs, language="python", max_lines=3, delay=0.1):
        console = self._console
        display_lines = []

        console.record = False
        with Live(console=console, refresh_per_second=10, vertical_overflow="crop") as live:
            for line in logs:
                display_lines.append(line)
                if len(display_lines) > max_lines:
                    display_lines.pop(0)

                code_block = "\n".join(display_lines)
                syntax = Syntax(code_block, language, theme="monokai", line_numbers=False, word_wrap=True)
                live.update(syntax)
                time.sleep(delay)
        console.record = True
        
    def parse_reply(self, text):
        self._console.print(f"\n📥 {self.llm.last} {T('llm_response')}:\n")
        lines = text.split('\n')
        code_block = []
        in_code_block = False
        in_run_block = False
        start = 0
        end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('```run'): 
                in_code_block = True
                in_run_block = True
                start = i
                continue
            elif line.strip().lower().startswith('```python'):
                in_code_block = True
                start = i
                continue
            elif line.strip().startswith('```') and in_run_block:
                end = i
                break
            if in_code_block and line.find('#RUN') >= 0:
                in_run_block = True

        if start > 0:
            self._console.print(Markdown('\n'.join(lines[:start])))
        if end > 0:
            code_block = lines[start+1:end]
            self.render_code(code_block)
            self._console.print(Markdown('\n'.join(lines[end+1:])))
        else:
            self._console.print(Markdown(text))

        if code_block:
            ret = {'type': MsgType.CODE, 'code': '\n'.join(code_block)}
        else:
            ret = {'type': MsgType.TEXT, 'code': None}
        return ret
        
    def process_code_reply(self, msg, llm=None):
        code_block = msg['code']
        self.box(f"\n⚡ {T('start_execute')}:", code_block, lang='python')
        result = self.runner(code_block)
        result = json.dumps(result, ensure_ascii=False)
        self._console.print(f"✅ {T('execute_result')}:\n", Markdown(f"```json\n{result}\n```"))
        self._console.print(f"\n📤 {T('start_feedback')}")
        feedback_response = self.llm(result, name=llm)
        return feedback_response

    def box(self, title, content, align=None, lang=None):
        if lang:
            content = Syntax(content, lang)
        if align:
            content = Align(content, align=align)
        self._console.print(Panel(content, title=title))

    def __call__(self, instruction, llm=None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self.box(f"[yellow]{T('start_instruction')}", f'[red]{instruction}', align="center")
        system_prompt = None if self.llm.history else self.system_prompt
        if system_prompt:
            self.instruction = instruction
        response = self.llm(instruction, system_prompt=system_prompt, name=llm)
        while response:
            #self._console.print(f"\n📥 {self.llm.last} {T('llm_response')}:\n", Markdown(response))
            msg = self.parse_reply(response)
            if msg['type'] != MsgType.CODE:
                break
            response = self.process_code_reply(msg, llm)
        total_token = self.llm.history.total_tokens
        self._console.print(f"\n⏹ {T('end_instruction')} | Tokens: {total_token}")
        os.write(1, b'\a\a\a')

    def chat(self, prompt):
        system_prompt = None if self.llm.history else self.system_prompt
        response, ok = self.llm(prompt, system_prompt=system_prompt)
        self._console.print(Markdown(response))

    def step(self):
        response = self.llm.get_last_message()
        if not response:
            self._console.print(f"❌ {T('no_context')}")
            return
        self.process_reply(response)

    def publish(self, title=None, author=None, verbose=True):
        url = self.settings.get('publish.url')
        cert = self.settings.get('publish.cert')
        if not (url and cert) or self.settings.get('publish.disable'):
            if verbose: self._console.print(f"[red]{T('publish_disabled')}")
            return False
        title = title or self.instruction
        author = author or os.getlogin()
        meta = {'author': author}
        files = {'content': self._console.export_html(clear=False)}
        data = {'title': title, 'metadata': json.dumps(meta)}

        if not (self.CERT_PATH.exists() and self.CERT_PATH.stat().st_size  > 0):
            self.CERT_PATH.write_text(cert)

        try:
            response = requests.post(url, files=files, data=data, cert=str(self.CERT_PATH), verify=True)
        except Exception as e:
            self._console.print_exception(e)
            return
        
        status_code = response.status_code
        if status_code in (200, 201):
            if verbose: self._console.print(f"[green]{T('upload_success')}:", response.json())
            return response.json()
        else:
            if verbose: self._console.print(f"[red]{T('upload_failed', status_code)}:", response.text)
            return False