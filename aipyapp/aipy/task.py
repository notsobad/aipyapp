#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import uuid
import platform
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
from importlib.resources import read_text

from loguru import logger
from rich.panel import Panel
from rich.align import Align
from rich.syntax import Syntax
from rich.markdown import Markdown

from .. import event_bus, Stoppable, T, __resources__
from .utils import get_safe_filename

CONSOLE_HTML_FORMAT = read_text(__resources__, "console_white.tpl")

class MsgType(Enum):
    CODE = auto()
    TEXT = auto()

class Task(Stoppable):
    MAX_ROUNDS = 16

    def __init__(self, instruction, *, system_prompt=None, max_rounds=None):
        super().__init__()
        self.task_id = uuid.uuid4().hex
        self.instruction = instruction
        self.console = None
        self.session = None
        self.runtime = None
        self.runner = None
        self.diagnose = None
        self.max_rounds = max_rounds
        self.system_prompt = system_prompt
        self.pattern = re.compile(
            r"^(`{4})(\w+)\s+([\w\-\.]+)\n(.*?)^\1\s*$",
            re.DOTALL | re.MULTILINE
        )
        self.log = logger.bind(src='task', id=self.task_id)
        self.start_time = datetime.now()
        
    def save(self, path):
       if self.console.record:
           self.console.save_html(path, clear=False, code_format=CONSOLE_HTML_FORMAT)

    def auto_save(self):
        instruction = self.instruction
        task = {'instruction': instruction}
        task['llm'] = self.session.history.json()
        task['envs'] = self.runtime.envs
        task['runner'] = self.runner.history

        filename = f"{self.task_id}.json"
        try:
            json.dump(task, open(filename, 'w'), ensure_ascii=False, indent=4)
        except Exception as e:
            self.log.exception('Error saving task')

        filename = f"{self.task_id}.html"
        self.save(filename)
        self.log.info('Task auto saved')
        
    def done(self):
        curname = f"{self.task_id}.json"
        jsonname = get_safe_filename(self.instruction, extension='.json')
        if jsonname and os.path.exists(curname):
            try:
                os.rename(curname, jsonname)
            except Exception as e:
                self.log.exception('Error renaming task json file')

        curname = f"{self.task_id}.html"
        htmlname = get_safe_filename(self.instruction, extension='.html')
        if htmlname and os.path.exists(curname):
            try:
                os.rename(curname, htmlname)
            except Exception as e:
                self.log.exception('Error renaming task html file')
        self.diagnose.report_code_error(self.runner.history)
        self.log.info('Task done', jsonname=jsonname, htmlname=htmlname)

    def parse_reply(self, markdown):
        code_blocks = {}
        for match in self.pattern.finditer(markdown):
            _, _, name, content = match.groups()
            code_blocks[name] = content.rstrip('\n')

        return code_blocks

    def process_code_reply(self, blocks, llm=None):
        event_bus('exec', blocks)
        code_block = blocks['main']
        self.box(f"\n⚡ {T("Start executing code block")}:", code_block, lang='python')
        result = self.runner(code_block, blocks)
        event_bus('result', result)
        result = json.dumps(result, ensure_ascii=False, indent=4)
        self.box(f"\n✅ {T("Execution result")}:\n", result, lang="json")
        status = self.console.status(f"[dim white]{T("Start sending feedback")}...")
        self.console.print(status)
        feed_back = f"# 最初任务\n{self.instruction}\n\n# 代码执行结果反馈\n{result}"
        return self.session.chat(feed_back, name=llm)

    def box(self, title, content, align=None, lang=None):
        if lang:
            content = Syntax(content, lang, line_numbers=True, word_wrap=True)
        if align:
            content = Align(content, align=align)
        
        self.console.print(Panel(content, title=title))

    def print_summary(self):
        history = self.session.history
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
            summarys = "| {rounds} | {time:.3f}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        else:
            summarys = ''
        event_bus.broadcast('summary', summarys)
        self.console.print(f"\n⏹ [cyan]{T("End processing instruction")} {summarys}")

    def build_user_prompt(self):
        prompt = {'task': self.instruction}
        prompt['python_version'] = platform.python_version()
        prompt['platform'] = platform.platform()
        prompt['today'] = datetime.today().isoformat()
        prompt['work_dir'] = '工作目录为当前目录，默认在当前目录下创建文件'
        if getattr(self.console, 'gui', False):
            prompt['matplotlib'] = "我现在用的是 matplotlib 的 Agg 后端，请默认用 plt.savefig() 保存图片后用 runtime.display() 显示，禁止使用 plt.show()"
            prompt['wxPython'] = "你回复的Markdown 消息中，可以用 ![图片](图片路径) 的格式引用之前创建的图片，会显示在 wx.html2 的 WebView 中"
        else:
            prompt['TERM'] = os.environ.get('TERM')
            prompt['LC_TERMINAL'] = os.environ.get('LC_TERMINAL')
        return prompt

    def run(self, instruction=None, *, llm=None, max_rounds=None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self.log.info('Running task', instruction=instruction or self.instruction)
        self.box(f"[yellow]{T("Start processing instruction")}", f'[red]{instruction or self.instruction}', align="center")
        if not instruction:
            prompt = self.build_user_prompt()
            event_bus('task_start', prompt)
            instruction = json.dumps(prompt, ensure_ascii=False)
            system_prompt = self.system_prompt
        else:
            system_prompt = None
        rounds = 1
        max_rounds = max_rounds or self.max_rounds
        if not max_rounds or max_rounds < 1:
            max_rounds = self.MAX_ROUNDS
        response = self.session.chat(instruction, system_prompt=system_prompt, name=llm)
        while response and rounds <= max_rounds:
            blocks = self.parse_reply(response.content)
            if 'main' not in blocks:
                break
            rounds += 1
            response = self.process_code_reply(blocks, llm)
            if self.is_stopped():
                self.log.info('Task stopped')
                break
        self.print_summary()
        self.auto_save()
        os.write(1, b'\a\a\a')
        self.log.info('Task done')
        
    def chat(self, prompt):
        system_prompt = None if self.session.history else self.system_prompt
        response = self.session.chat(prompt, system_prompt=system_prompt)
        self.console.print(Markdown(response))

    def step(self):
        response = self.session.get_last_message()
        if not response:
            self.console.print(f"❌ {T("No context information found")}")
            return
        self.process_reply(response)
