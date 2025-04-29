#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown

from .. import event_bus, T

class LineReceiver(list):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    @property
    def content(self):
        return '\n'.join(self)
    
    def feeds(self, data: str):
        self.buffer += data
        new_lines = []

        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.append(line)
            new_lines.append(line)

        return new_lines
    
    def feed(self, data: str):
        line = None
        self.buffer += data
        if '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.append(line)
        return line

class LiveManager:
    def __init__(self, console, name):
        self.live = None
        self.name = name
        self.console = console
        self.lr = None
        self.title = None
        self.response_panel = None
        self.full_response = None

    def __enter__(self):
        self.lr = LineReceiver()
        self.title = f"{self.name} {T("reply")}"
        self.live = Live(auto_refresh=False, vertical_overflow='visible', transient=True)
        self.live.__enter__()
        status = self.console.status(f"[dim white]{self.name} {T("is thinking hard, please wait 6-60 seconds")}...", spinner='runner')
        response_panel = Panel(status, title=self.title, border_style="blue")
        self.live.update(response_panel, refresh=True)
        return self

    def feed(self, content):
        if not content: return
        lines = self.lr.feeds(content)
        if not lines: return
        
        content = '\n'.join(lines)
        event_bus.broadcast('response_stream', {'llm': self.name, 'content': content})

        full_response = self.lr.content
        try:
            md = Markdown(full_response)
            response_panel = Panel(md, title=self.title, border_style="green")
        except Exception:
            text = Text(full_response)
            response_panel = Panel(text, title=self.title, border_style="yellow")
        self.live.update(response_panel, refresh=True)
        self.response_panel = response_panel
        self.full_response = full_response
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lr.buffer:
            self.feed('\n')
        #if self.response_panel: self.console.print(self.response_panel)
        self.live.__exit__(exc_type, exc_val, exc_tb)

class BlockManager:
    def __init__(self, console, name):
        self.name = name
        self.console = console

    def print_code_block(self, lr, tokens, language="python", max_lines=5, delay=0.05):
        console = self.console
        display_lines = []

        console.record = False
        with Live(console=console, refresh_per_second=10, vertical_overflow="crop") as live:
            for token in tokens:
                line = lr.feed(token)
                if not line:
                    continue
                if line.startswith('````'):
                    break

                display_lines.append(line)
                if len(display_lines) > max_lines:
                    display_lines.pop(0)

                code_block = "\n".join(display_lines)
                syntax = Syntax(code_block, language, theme="monokai", line_numbers=False, word_wrap=True)
                live.update(syntax)
                time.sleep(delay)

        console.record = True

    def process(self, tokens):
        block = []
        code_block = None
        lr = LineReceiver()
        for token in tokens:
            line = lr.feed(token)
            if not line: continue

            if line.startswith('````python'):
                if block:
                    self.console.print(Markdown('\n'.join(block)))
                    block = []
                self.print_code_block(lr, tokens)
            else:
                block.append(line)

        if lr.buffer:
            block.append(lr.buffer)
        if block:
            self.console.print(Markdown('\n'.join(block)))

class StreamProcessor:
    def __init__(self, console):
        self.console = console

    def get_processor(self, name):
        return BlockManager(self.console, name)

    def __call__(self, name, tokens):
        self.get_processor(name).process(tokens)
        