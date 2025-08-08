#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from functools import wraps
import json

from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.rule import Rule
from rich.console import Console, Group

from aipyapp.display import RichDisplayPlugin, LiveDisplay
from aipyapp import T

def restore_output(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        try:
            return func(self, *args, **kwargs)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
    return wrapper

class DisplayClassic(RichDisplayPlugin):
    """Classic display style"""
    name = "classic"
    version = "1.0.0"
    description = "Classic display style"
    author = "AiPy Team"

    def __init__(self, console: Console, quiet: bool = False):
        super().__init__(console, quiet)
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
        syntax_code = Syntax(block.code, block.lang, line_range=(0, 5), line_numbers=line_numbers, word_wrap=True)
        json_result = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        syntax_result = Syntax(json_result, 'json', line_numbers=False, word_wrap=True)
        group = Group(syntax_code, Rule(), syntax_result)
        panel = Panel(group, title=title or block.name)
        self.console.print(panel)

    def on_exception(self, event):
        """异常事件处理"""
        msg = event.data.get('msg', '')
        exception = event.data.get('exception')
        self.console.print(f"❌ {msg}: {exception}", style="error")

    def on_task_start(self, event):
        """任务开始事件处理"""
        data = event.data
        instruction = data.get('instruction')
        self.console.print(f"🚀 {T('Task processing started')}: {instruction}", style="task.running")

    def on_query_start(self, event):
        """查询开始事件处理"""
        self.console.print(f"➡️ {T('Sending message to LLM')}", style='info')

    def on_round_start(self, event):
        """回合开始事件处理"""
        data = event.data
        instruction = data.get('instruction')
        self.console.print(f"▶️ {T('Instruction processing started')}: {instruction}", style="info")

    def on_stream_start(self, event):
        """流式开始事件处理"""
        if not self.quiet:
            self.live_display = LiveDisplay()
            self.live_display.__enter__()
            self.console.print(f"🔄 {T('Streaming started')}", style='info')
    
    def on_stream_end(self, event):
        """流式结束事件处理"""
        if self.live_display:
            self.live_display.__exit__(None, None, None)
            self.live_display = None

    def on_stream(self, event):
        """LLM 流式响应事件处理"""
        response = event.data
        lines = response.get('lines')
        reason = response.get('reason', False)
        if self.live_display:
            self.live_display.update_display(lines, reason=reason)
                
    def on_response_complete(self, event):
        """LLM 响应完成事件处理"""
        data = event.data
        llm = data.get('llm', '')
        msg = data.get('msg')
        if not msg:
            self.console.print(f"{T('LLM response is empty')}", style="error")
            return
        if msg.role == 'error':
            self.console.print(f"{msg.content}", style="error")
            return
        if msg.reason:
            content = f"{msg.reason}\n\n-----\n\n{msg.content}"
        else:
            content = msg.content
        self.console.print(f"🔸 {T('Completed receiving message')} ({llm}):\n", style="info")
        self.console.print(Markdown(content))

    def on_parse_reply(self, event):
        """消息解析结果事件处理"""
        ret = event.data.get('result')
        if not ret:
            return
            
        # 构建简化的显示信息
        info_parts = []
        
        # 显示代码块数量
        if 'blocks' in ret and ret['blocks']:
            block_count = len(ret['blocks'])
            info_parts.append(f"{block_count}个代码块")
        
        # 显示要执行的代码块名称
        if 'exec_blocks' in ret and ret['exec_blocks']:
            exec_names = [getattr(block, 'name', 'Unknown') for block in ret['exec_blocks']]
            exec_str = ", ".join(exec_names)
            info_parts.append(f"执行: {exec_str}")
        
        # 显示 MCP 工具调用
        if 'call_tool' in ret:
            info_parts.append("MCP工具调用")
        
        # 显示解析错误
        if 'errors' in ret and ret['errors']:
            error_count = len(ret['errors'])
            info_parts.append(f"{error_count}个错误")
        
        # 如果有内容则显示
        if info_parts:
            info = " | ".join(info_parts)
            self.console.print(f"➔  {T('Message parse result')}: {info}", style="info")

    def on_exec(self, event):
        """代码执行开始事件处理"""
        block = event.data.get('block')
        if hasattr(block, 'name'):
            self.console.print(f"⚡ {T('Start executing code block')}: {block.name}", style='info')
        else:
            self.console.print(f"⚡ {T('Start executing code block')}", style='info')
            
    @restore_output
    def on_call_function(self, event):
        """函数调用事件处理"""
        data = event.data
        funcname = data.get('funcname')
        self.console.print(f"⚡ {T('Start calling function')}: {funcname}", style='info')

    def on_exec_result(self, event):
        """代码执行结果事件处理"""
        data = event.data
        result = data.get('result')
        block = data.get('block')
        
        # 显示说明信息
        block_name = getattr(block, 'name', 'Unknown') if block else 'Unknown'
        self.console.print(f"☑️ {T('Execution result')}: {block_name}", style="info")
        
        # JSON格式化和高亮显示结果
        json_result = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        self.console.print_json(json_result, indent=2)

    def on_mcp_call(self, event):
        """工具调用事件处理"""
        self.console.print(f"⚡ {T('Start calling MCP tool')} ...", style='info')
                
    def on_mcp_result(self, event):
        """MCP 工具调用结果事件处理"""
        data = event.data
        result = data.get('result')
        block = data.get('block')
        self.console.print(f"☑️ {T('MCP tool call result')}: {block.name}", style="info")
        json_result = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        self.console.print_json(json_result, style="dim")

    def on_round_end(self, event):
        """任务总结事件处理"""
        summary = event.data['summary']
        usages = summary.get('usages', [])
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

        summary = summary.get('summary')
        self.console.print(f"\n🔸 {T('End processing instruction')} {summary}", style="info")

    def on_upload_result(self, event):
        """云端上传结果事件处理"""
        data = event.data
        status_code = data.get('status_code', 0)
        url = data.get('url', '')
        if url:
            self.console.print(f"🟢 {T('Article uploaded successfully, {}', url)}", style="success")
        else:
            self.console.print(f"🔴 {T('Upload failed (status code: {})', status_code)}", style="error")

    def on_task_end(self, event):
        """任务结束事件处理"""
        path = event.data.get('path', '')
        self.console.print(f"✅ {T('Task completed')}: {path}", style="info")

    def on_runtime_message(self, event):
        """Runtime消息事件处理"""
        data = event.data
        message = data.get('message', '')
        self.console.print(message)

    def on_runtime_input(self, event):
        """Runtime输入事件处理"""
        # 输入事件通常不需要特殊处理，因为input_prompt已经处理了
        pass