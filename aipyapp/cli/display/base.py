#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import Any, Dict, Union
from rich.console import Console

from ... import T

class BaseDisplayPlugin(ABC):
    """显示效果插件基类"""
    
    def __init__(self, console: Console):
        self.console = console

    @abstractmethod
    def on_task_start(self, content: Any):
        """任务开始事件处理"""
        pass
        
    @abstractmethod
    def on_query_start(self):
        """查询开始事件处理"""
        pass
        
    @abstractmethod
    def on_round_start(self, content: Any):
        """回合开始事件处理"""
        pass
        
    @abstractmethod
    def on_round_end(self, content: Any):
        """回合结束事件处理"""
        pass
        
    @abstractmethod
    def on_stream_start(self, response: Dict[str, Any]):
        """流式开始事件处理"""
        pass
        
    @abstractmethod
    def on_stream_end(self, response: Dict[str, Any]):
        """流式结束事件处理"""
        pass
        
    @abstractmethod
    def on_stream(self, response: Dict[str, Any]):
        """LLM 流式响应事件处理"""
        pass
        
    @abstractmethod
    def on_response_complete(self, response: Dict[str, Any]):
        """LLM 响应完成事件处理"""
        pass
        
    @abstractmethod
    def on_parse_reply(self, ret: Union[Dict[str, Any], None]):
        """消息解析结果事件处理"""
        pass
        
    @abstractmethod
    def on_exec(self, block: Any):
        """代码执行开始事件处理"""
        pass
        
    @abstractmethod
    def on_exec_result(self, result: Any):
        """代码执行结果事件处理"""
        pass
        
    @abstractmethod
    def on_mcp_result(self, data: Dict[str, Any]):
        """MCP 工具调用结果事件处理"""
        pass
        
    @abstractmethod
    def on_mcp_call(self, block: Any):
        """工具调用事件处理"""
        pass 