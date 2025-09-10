#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any, Dict
from datetime import datetime

from aipyapp.aipy.events import TypedEvent
from aipyapp.display import RichDisplayPlugin

class DisplayAgent(RichDisplayPlugin):
    """Agent模式显示插件 - 捕获所有输出用于API返回"""
    name = "agent"
    version = "1.0.0"
    description = "Agent display style"
    author = "AiPy Team"

    def __init__(self, console, quiet: bool = True):
        super().__init__(console, quiet)
        # 捕获的输出数据
        self.captured_data = {
            'messages': [],
            'results': [],
            'errors': [],
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'metadata': {}
        }
        
    def _add_message(self, message_type: str, content: Any, timestamp: str = None):
        """添加消息到捕获数据"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
            
        self.captured_data['messages'].append({
            'type': message_type,
            'content': content,
            'timestamp': timestamp
        })
    
    def get_captured_data(self) -> Dict:
        """获取捕获的数据"""
        return self.captured_data.copy()
    
    def clear_captured_data(self):
        """清空捕获的数据"""
        self.captured_data = {
            'messages': [],
            'results': [],
            'errors': [],
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'metadata': {}
        }

    # 重写父类方法，捕获输出而不显示
    def print(self, message: str, style: str = None):
        """捕获打印消息"""
        self._add_message('print', {'message': message, 'style': style})
    
    def input(self, prompt: str) -> str:
        """Agent模式不支持交互输入"""
        self._add_message('input_request', {'prompt': prompt})
        return ''
    
    def confirm(self, prompt, default="n", auto=None):
        """Agent模式自动确认"""
        self._add_message('confirm', {'prompt': prompt, 'default': default, 'auto_response': auto})
        return auto if auto is not None else (default == "y")

    # 事件处理方法
    def on_task_started(self, event: TypedEvent):
        """任务开始"""
        instruction = event.typed_event.instruction
        task_id = event.typed_event.task_id
        self._add_message('task_started', {
            'instruction': instruction,
            'task_id': task_id
        })
        self.captured_data['status'] = 'running'
        self.captured_data['metadata']['instruction'] = instruction
        
    def on_response_completed(self, event: TypedEvent):
        """LLM响应完成"""
        llm = event.typed_event.llm
        msg = event.typed_event.msg
        message_content = msg.content if (msg and hasattr(msg, 'content')) else str(msg) if msg else 'No response'
        
        self._add_message('llm_response', {
            'llm': llm,
            'message': message_content
        })
        
    def on_exec_completed(self, event: TypedEvent):
        """代码执行结果"""
        block = event.typed_event.block
        result = event.typed_event.result
        
        result_data = {
            'block_name': block.name if (block and hasattr(block, 'name')) else 'unknown',
            'language': block.lang if (block and hasattr(block, 'lang')) else 'unknown',
            'result': result
        }
        self._add_message('exec_completed', result_data)
        self.captured_data['results'].append(result_data)

    def on_task_completed(self, event: TypedEvent):
        """任务结束"""
        self.captured_data['status'] = 'completed'
        self.captured_data['end_time'] = datetime.now().isoformat()
        self._add_message('task_completed', {
            'path': event.typed_event.path
        })

    def on_exception(self, event: TypedEvent):
        """异常处理"""
        error_data = {
            'message': event.typed_event.msg,
            'exception': str(event.typed_event.exception) if event.typed_event.exception else None
        }
        self._add_message('error', error_data)
        self.captured_data['errors'].append(error_data)
        self.captured_data['status'] = 'error'

    def on_stream(self, event: TypedEvent):
        """流式响应"""
        self._add_message('stream', {
            'llm': event.typed_event.llm,
            'lines': event.typed_event.lines,
            'reason': event.typed_event.reason
        })

    def on_parse_reply_completed(self, event: TypedEvent):
        """解析回复"""
        self._add_message('parse_reply_completed', {
            'response': event.typed_event.response
        })

    def on_tool_call_completed(self, event: TypedEvent):
        """MCP工具调用结果"""
        result = event.typed_event.result
        self._add_message('tool_call_completed', {
            'tool_name': result.tool_name.value if hasattr(result, 'tool_name') else 'unknown',
            'result': result.result if hasattr(result, 'result') else result
        })

    def on_upload_result(self, event: TypedEvent):
        """云端上传结果"""
        self._add_message('upload_result', {
            'status_code': event.typed_event.status_code,
            'url': event.typed_event.url
        })

    def on_request_started(self, event: TypedEvent):
        """查询开始"""
        self._add_message('request_started', {
            'timestamp': datetime.now().isoformat()
        })

    def on_step_started(self, event: TypedEvent):
        """回合开始"""
        self._add_message('step_started', {
            'instruction': event.typed_event.instruction,
            'title': event.typed_event.title
        })

    def on_step_completed(self, event: TypedEvent):
        """回合结束"""
        self._add_message('step_completed', {
            'summary': event.typed_event.summary,
            'response': str(event.typed_event.response) if event.typed_event.response else ''
        })

    def on_exec_started(self, event: TypedEvent):
        """代码执行开始"""
        block = event.typed_event.block
        self._add_message('exec_started', {
            'block_name': block.name if (block and hasattr(block, 'name')) else 'unknown',
            'language': block.lang if (block and hasattr(block, 'lang')) else 'unknown',
            'code': block.code if (block and hasattr(block, 'code')) else 'No code'
        })
        
    def on_edit_started(self, event: TypedEvent):
        """代码编辑开始"""
        self._add_message('edit_started', {
            'block_name': event.typed_event.block_name,
            'old_str': event.typed_event.old,
            'new_str': event.typed_event.new,
            'replace_all': event.typed_event.replace_all
        })
        
    def on_edit_completed(self, event: TypedEvent):
        """代码编辑结果"""
        self._add_message('edit_completed', {
            'success': event.typed_event.success,
            'block_name': event.typed_event.block_name,
            'new_version': event.typed_event.new_version
        })

    def on_tool_call_started(self, event: TypedEvent):
        """MCP工具调用"""
        tool_call = event.typed_event.tool_call
        self._add_message('tool_call_started', {
            'tool_name': tool_call.name.value if hasattr(tool_call, 'name') else 'unknown',
            'arguments': tool_call.arguments.model_dump() if hasattr(tool_call, 'arguments') else {}
        })