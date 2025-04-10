#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
import uuid
import requests
from enum import Enum
from pathlib import Path
from importlib.resources import files

from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.syntax import Syntax
from rich.console import Console
from rich.markdown import Markdown

from . import i18n
from . import utils
from .i18n import T
from .llm import LLM
from .runner import Runner
from .templates import CONSOLE_HTML_FORMAT

class MsgType(Enum):
    CODE = "CODE"
    TEXT = "TEXT"

CERT_PATH = Path('/tmp/aipy_client.crt')

class Agent():
    MAX_TOKENS = 8192

    def __init__(self, settings, console=None):
        self.settings = settings
        self.instruction = None
        self.llm = None
        self.runner = None
        self._console = console
        self.system_prompt = None
        self.max_tokens = None
        self._cwd = None
        self.task_id = None
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
        if config.workdir:
            workdir = Path.cwd() / config.workdir
            workdir.mkdir(parents=True, exist_ok=True)
            os.chdir(workdir)
            self._cwd = workdir
        else:
            self._cwd = Path.cwd()

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

    def save(self, path):
        self._console.save_html(path, clear=False, code_format=CONSOLE_HTML_FORMAT)
        
    def done(self):
        #self._console.save_svg('console.svg', clear=False)
        self._console.save_html('console.html', clear=True, code_format=CONSOLE_HTML_FORMAT)
        task = {'instruction': self.instruction}
        task['llm'] = self.llm.history.json()
        task['runner'] = self.runner.history
        try:
            json.dump(task, open('task.json', 'w'), ensure_ascii=False, indent=4)
        except Exception as e:
            self._console.print_exception()
        self.llm.clear()
        self.runner.clear()
        self.task_id = None
        self.instruction = None
            
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

        if end > 0:
            code_block = lines[start+1:end]
            ret = {'type': MsgType.CODE, 'code': '\n'.join(code_block)}
        else:
            ret = {'type': MsgType.TEXT, 'code': None}
        return ret
        
    def process_code_reply(self, msg, llm=None):
        code_block = msg['code']
        self.box(f"\n⚡ {T('start_execute')}:", code_block, lang='python')
        result = self.runner(code_block)
        result = json.dumps(result, ensure_ascii=False, indent=4)
        self.box(f"\n✅ {T('execute_result')}:\n", result, lang="json")
        status = self._console.status(f"[dim white]{T('start_feedback')}...")
        self._console.print(status)
        feed_back = f"# 最初任务\n{self.instruction}\n\n# 代码执行结果反馈\n{result}"
        feedback_response = self.llm(feed_back, name=llm)
        return feedback_response

    def box(self, title, content, align=None, lang=None):
        if lang:
            content = Syntax(content, lang, line_numbers=True, word_wrap=True)
        if align:
            content = Align(content, align=align)
        self._console.print(Panel(content, title=title))

    def print_summary(self):
        history = self.llm.history
        """
        table = Table(title=T("Task Summary"), show_lines=True)

        table.add_column(T("Round"), justify="center", style="bold cyan", no_wrap=True)
        table.add_column(T("Time(s)"), justify="right")
        table.add_column(T("In Tokens"), justify="right")
        table.add_column(T("Out Tokens"), justify="right")
        table.add_column(T("Total Tokens"), justify="right", style="bold magenta")

        round = 1
        for row in history.get_usage():
            table.add_row(
                str(round),
                str(row["time"]),
                str(row["input_tokens"]),
                str(row["output_tokens"]),
                str(row["total_tokens"]),
            )
            round += 1
        self._console.print("\n")
        self._console.print(table)
        """
        summary = history.get_summary()
        if 'time' in summary:
            summary = "| {rounds} | {time:.3f}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        else:
            summary = ''
        self._console.print(f"\n⏹ [cyan]{T('end_instruction')} {summary}")
    
    def __call__(self, instruction, llm=None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self.box(f"[yellow]{T('start_instruction')}", f'[red]{instruction}', align="center")
        system_prompt = None if self.llm.history else self.system_prompt
        if system_prompt:
            self.task_id = uuid.uuid4().hex
            self.instruction = instruction
            path = self._cwd / self.task_id
            path.mkdir(parents=True, exist_ok=False)
            os.chdir(path)
        response = self.llm(instruction, system_prompt=system_prompt, name=llm)
        while response:
            msg = self.parse_reply(response)
            if msg['type'] != MsgType.CODE:
                break
            response = self.process_code_reply(msg, llm)
        self.print_summary()
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

        if not (CERT_PATH.exists() and CERT_PATH.stat().st_size  > 0):
            CERT_PATH.write_text(cert)

        try:
            response = requests.post(url, files=files, data=data, cert=str(CERT_PATH), verify=True)
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