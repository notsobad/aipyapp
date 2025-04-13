#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import uuid
import platform
from pathlib import Path
from datetime import date
from enum import Enum, auto

import requests
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown

from .i18n import T
from .templates import CONSOLE_HTML_FORMAT

CERT_PATH = Path('/tmp/aipy_client.crt')

class MsgType(Enum):
    CODE = auto()
    TEXT = auto()

class Task:
    MAX_ROUNDS = 16

    def __init__(self, instruction, *, system_prompt=None, max_rounds=None):
        self.task_id = uuid.uuid4().hex
        self.instruction = instruction
        self.console = None
        self.llm = None
        self.runner = None
        self.max_rounds = max_rounds
        self.workdir = Path.cwd()
        self.cwd = self.workdir / self.task_id
        self.system_prompt = system_prompt
        self.pattern = re.compile(
            r"^(`{4})(\w+)\s+([\w\-\.]+)\n(.*?)^\1\s*$",
            re.DOTALL | re.MULTILINE
        )

    def save(self, path):
       path = str(self.workdir / path)
       self._console.save_html(path, clear=False, code_format=CONSOLE_HTML_FORMAT)

    def done(self):
        self.console.save_html('console.html', clear=True, code_format=CONSOLE_HTML_FORMAT)
        task = {'instruction': self.instruction}
        task['llm'] = self.llm.history.json()
        task['runner'] = self.runner.history
        try:
            json.dump(task, open('task.json', 'w'), ensure_ascii=False, indent=4)
        except Exception as e:
            self.console.print_exception()
        os.chdir(self.workdir)
        self.llm.clear()
        self.runner.clear()
        self.task_id = None
        self.instruction = None

    def parse_reply(self, markdown):
        code_blocks = {}
        for match in self.pattern.finditer(markdown):
            _, _, name, content = match.groups()
            code_blocks[name] = content.rstrip('\n')

        return code_blocks

    def process_code_reply(self, blocks, llm=None):
        code_block = blocks['main']
        self.box(f"\n⚡ {T('start_execute')}:", code_block, lang='python')
        result = self.runner(code_block, blocks)
        result = json.dumps(result, ensure_ascii=False, indent=4)
        self.box(f"\n✅ {T('execute_result')}:\n", result, lang="json")
        status = self.console.status(f"[dim white]{T('start_feedback')}...")
        self.console.print(status)
        feed_back = f"# 最初任务\n{self.instruction}\n\n# 代码执行结果反馈\n{result}"
        feedback_response = self.llm(feed_back, name=llm)
        return feedback_response

    def box(self, title, content, align=None, lang=None):
        if hasattr(self.console, 'gui'):
            # Using Mocked console. Dont use Panel
            self.console.print(f"\n{title}")
            self.console.print(content)
            return

        if lang:
            content = Syntax(content, lang, line_numbers=True, word_wrap=True)
        if align:
            content = Align(content, align=align)
        
        self.console.print(Panel(content, title=title))

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
        self.console.print(f"\n⏹ [cyan]{T('end_instruction')} {summary}")

    def build_user_prompt(self):
        prompt = {'task': self.instruction}
        prompt['python_version'] = platform.python_version()
        prompt['platform'] = platform.platform()
        prompt['today'] = date.today().isoformat()
        prompt['TERM'] = os.environ.get('TERM')
        prompt['LC_TERMINAL'] = os.environ.get('LC_TERMINAL')
        return json.dumps(prompt, ensure_ascii=False)

    def run(self, instruction=None, *, llm=None, max_rounds=None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self.box(f"[yellow]{T('start_instruction')}", f'[red]{instruction or self.instruction}', align="center")
        if not instruction:
            instruction = self.build_user_prompt()
            system_prompt = self.system_prompt
            self.cwd.mkdir(parents=True, exist_ok=False)
            os.chdir(self.cwd)
        else:
            system_prompt = None
        rounds = 1
        max_rounds = max_rounds or self.max_rounds
        if not max_rounds or max_rounds < 1:
            max_rounds = self.MAX_ROUNDS
        response = self.llm(instruction, system_prompt=system_prompt, name=llm)
        while response and rounds <= max_rounds:
            blocks = self.parse_reply(response)
            if 'main' not in blocks:
                break
            rounds += 1
            response = self.process_code_reply(blocks, llm)
        self.print_summary()
        os.write(1, b'\a\a\a')

    def chat(self, prompt):
        system_prompt = None if self.llm.history else self.system_prompt
        response, ok = self.llm(prompt, system_prompt=system_prompt)
        self.console.print(Markdown(response))

    def step(self):
        response = self.llm.get_last_message()
        if not response:
            self.console.print(f"❌ {T('no_context')}")
            return
        self.process_reply(response)

    def publish(self, title=None, author=None, verbose=True):
        url = self.settings.get('publish.url')
        cert = self.settings.get('publish.cert')
        if not (url and cert) or self.settings.get('publish.disable'):
            if verbose: self.console.print(f"[red]{T('publish_disabled')}")
            return False
        title = title or self.instruction
        author = author or os.getlogin()
        meta = {'author': author}
        files = {'content': self.console.export_html(clear=False)}
        data = {'title': title, 'metadata': json.dumps(meta)}

        if not (CERT_PATH.exists() and CERT_PATH.stat().st_size  > 0):
            CERT_PATH.write_text(cert)

        try:
            response = requests.post(url, files=files, data=data, cert=str(CERT_PATH), verify=True)
        except Exception as e:
            self.console.print_exception(e)
            return
        
        status_code = response.status_code
        if status_code in (200, 201):
            if verbose: self.console.print(f"[green]{T('upload_success')}:", response.json())
            return response.json()
        else:
            if verbose: self.console.print(f"[red]{T('upload_failed', status_code)}:", response.text)
            return False