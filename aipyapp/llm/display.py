#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from loguru import logger
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

from .. import event_bus, T

class LineReceiver(list):
    def __init__(self):
        super().__init__()
        self.buffer = ""

    @property
    def content(self):
        return '\n'.join(self)
    
    def feed(self, data: str):
        self.buffer += data
        new_lines = []

        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.append(line)
            new_lines.append(line)

        return new_lines

class LiveManager:
    def __init__(self, console, name):
        self.live = None
        self.name = name
        self.console = console
        self.lr = LineReceiver()
        self.title = f"{self.name} {T("reply")}"
        self.response_panel = None
        self.full_response = None

    def __enter__(self):
        console = self.console if self.console.quiet else None
        self.live = Live(console=console, auto_refresh=False, vertical_overflow='visible', transient=True)
        self.live.__enter__()
        status = self.console.status(f"[dim white]{self.name} {T("is thinking hard, please wait 6-60 seconds")}...", spinner='runner')
        response_panel = Panel(status, title=self.title, border_style="blue")
        self.live.update(response_panel, refresh=True)
        return self

    def process_chunk(self, content):
        if not content: return
        lines = self.lr.feed(content)
        if not lines: return
        
        content = '\n'.join(lines)
        event_bus.broadcast('response_stream', {'llm': self.name, 'content': content})
        if hasattr(self.console, 'gui'):
            self.console.print(content, end="", highlight=False)

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
            self.process_chunk('\n')
        self.live.__exit__(exc_type, exc_val, exc_tb)
