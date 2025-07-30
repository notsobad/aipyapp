#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from typing import Any, Dict, Union

from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.rule import Rule
from rich.console import Console, Group

from .base import BaseDisplayPlugin
from .live_display import LiveDisplay
from ... import T

class DisplayClassic(BaseDisplayPlugin):
    """Classic display style"""
    
    def __init__(self, console: Console):
        super().__init__(console)
        self.live_display = None

    def _box(self, title: str, content: str, align: str = None, lang: str = None):
        """传统的 box 显示方法"""
        if lang:
            content = Syntax(content, lang, line_numbers=True, word_wrap=True)
        else:
            content = Markdown(content)

        if align:
            content = Align(content, align=align)
        
        self.console.print(Panel(content, title=title)) 

    def print_code_result(self, block, result, title=None):
        line_numbers = True if 'traceback' in result else False
        syntax_code = Syntax(block.code, block.lang, line_numbers=line_numbers, word_wrap=True)
        json_result = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        syntax_result = Syntax(json_result, 'json', line_numbers=False, word_wrap=True)
        group = Group(syntax_code, Rule(), syntax_result)
        panel = Panel(group, title=title or block.name)
        self.console.print(panel)

    def on_task_start(self, data: Dict[str, Any]):
        """任务开始事件处理"""
        instruction = data.get('instruction')
        self.console.print(f"[yellow]{T('Task processing started')}: {instruction}")

    def on_query_start(self):
        """查询开始事件处理"""
        self.console.print(f"{T('Sending message to LLM')}...", style='dim white')

    def on_round_start(self, data: Dict[str, Any]):
        """回合开始事件处理"""
        instruction = data.get('instruction')
        self.console.print(f"[yellow]{T('Instruction processing started')}: {instruction}")

    def on_stream_start(self, response: Dict[str, Any]):
        """流式开始事件处理"""
        self.live_display = LiveDisplay()
        self.live_display.__enter__()
    
    def on_stream_end(self, response: Dict[str, Any]):
        """流式结束事件处理"""
        if self.live_display:
            self.live_display.__exit__(None, None, None)
            self.live_display = None

    def on_stream(self, response: Dict[str, Any]):
        """LLM 流式响应事件处理"""
        lines = response.get('lines')
        reason = response.get('reason', False)
        self.live_display.update_display(lines, reason=reason)
                
    def on_response_complete(self, response: Dict[str, Any]):
        """LLM 响应完成事件处理"""
        msg = response.get('content', '')
        if not msg:
            self.console.print(f"[red]{T('LLM response is empty')}[/red]")
            return
        if msg.role == 'error':
            self.console.print(f"[red]{msg.content}[/red]")
            return
        if msg.reason:
            content = f"{msg.reason}\n\n-----\n\n{msg.content}"
        else:
            content = msg.content
        self._box(f"[yellow]{T('Reply')} ({response.get('llm')})", content)

    def on_parse_reply(self, ret: Union[Dict[str, Any], None]):
        """消息解析结果事件处理"""
        if ret:
            json_str = json.dumps(ret, ensure_ascii=False, indent=2, default=str)
            self._box(f"✅ {T('Message parse result')}", json_str, lang="json")

    def on_exec(self, block: Any):
        """代码执行开始事件处理"""
        if hasattr(block, 'name'):
            self.console.print(f"⚡ {T('Start executing code block')}: {block.name}", style='dim white')
        else:
            self.console.print(f"⚡ {T('Start executing code block')}", style='dim white')
            
    def on_exec_result(self, data: Dict[str, Any]):
        """代码执行结果事件处理"""
        result = data.get('result')
        block = data.get('block')
        self.print_code_result(block, result)

    def on_mcp_call(self, block: Any):
        """工具调用事件处理"""
        self.console.print(f"⚡ {T('Start calling MCP tool')} ...", style='dim white')
                
    def on_mcp_result(self, data: Dict[str, Any]):
        """MCP 工具调用结果事件处理"""
        result = data.get('result')
        block = data.get('block')
        self.print_code_result(block, result, title=T("MCP tool call result"))
            
    def on_round_end(self, data: Dict[str, Any]):
        """任务总结事件处理"""
        usages = data.get('usages', [])
        if usages:
            table = Table(title=T("Task Summary"), show_lines=True)

            table.add_column(T("Round"), justify="center", style="bold cyan", no_wrap=True)
            table.add_column(T("Time(s)"), justify="right")
            table.add_column(T("In Tokens"), justify="right")
            table.add_column(T("Out Tokens"), justify="right")
            table.add_column(T("Total Tokens"), justify="right", style="bold magenta")

            round = 1
            for row in usages:
                table.add_row(
                    str(round),
                    str(row["time"]),
                    str(row["input_tokens"]),
                    str(row["output_tokens"]),
                    str(row["total_tokens"]),
                )
                round += 1
            self.console.print("\n")
            self.console.print(table)

        summary = data.get('summary')
        self.console.print(f"\n⏹ [cyan]{T('End processing instruction')} {summary}")