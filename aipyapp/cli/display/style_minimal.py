#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from typing import Any, Dict
from rich.console import Console
from rich.syntax import Syntax

from .base import BaseDisplayPlugin
from ... import T

class DisplayMinimal(BaseDisplayPlugin):
    """Minimal display style"""
    
    def __init__(self, console: Console):
        super().__init__(console)
        self.stream_buffer = ""
        
    def on_task_start(self, content: Any):
        """任务开始事件处理"""
        if isinstance(content, str):
            self.console.print(f"→ {content}")
        else:
            self.console.print("→ Task started")
            
    def on_response_stream(self, response: Dict[str, Any]):
        """LLM 流式响应事件处理"""
        content = response.get('content', '')
        reason = response.get('reason', False)
        
        if reason:
            # Thinking 内容，静默处理
            pass
        else:
            # 普通内容，累积并实时显示
            self.stream_buffer += content
            with self:
                self.update_live(self.stream_buffer)
                
    def on_response_complete(self, response: Dict[str, Any]):
        """LLM 响应完成事件处理"""
        content = response.get('content', '')
        if hasattr(content, 'content'):
            content = content.content
            
        if content:
            self.console.print()
            self.console.print(content)
            
    def on_exec(self, block: Any):
        """代码执行开始事件处理"""
        if hasattr(block, 'name'):
            self.console.print(f"▶ {block.name}")
        else:
            self.console.print("▶ Executing...")
            
    def on_result(self, result: Any):
        """代码执行结果事件处理"""
        if isinstance(result, dict):
            # 检查是否有错误
            if 'traceback' in result:
                self.console.print("✗ Error")
                if result.get('traceback'):
                    self.console.print(result['traceback'])
            else:
                self.console.print("✓ Success")
                if 'output' in result and result['output']:
                    self.console.print(result['output'])
        else:
            self.console.print(f"✓ {result}")
            
    def on_summary(self, summary: str):
        """任务总结事件处理"""
        self.console.print(f"• {summary}")
        
    def on_tool_call(self, block: Any):
        """工具调用事件处理"""
        self.console.print("🔧 Tool call") 