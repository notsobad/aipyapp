#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LLM 响应解析模块 - 专注于纯解析，不包含业务验证"""

import re
import json
from typing import List, Dict, Any, Tuple, Literal
from enum import Enum
from uuid import uuid4

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError, Field

from .types import Errors
from .blocks import CodeBlock
from .toolcalls import ToolCall
from .libmcp import extract_call_tool_str, extra_call_tool_blocks
from .chat import ChatMessage

FRONT_MATTER_PATTERN = r"^\s*---\s*\n(.*?)\n---\s*"

BLOCK_PATTERN = re.compile(
    r'<!--\s*Block-Start:\s*(\{.*?\})\s*-->\s*(?P<ticks>`{3,})(\w+)?\s*\n(.*?)\n(?P=ticks)\s*<!--\s*Block-End:\s*(\{.*?\})\s*-->',
    re.DOTALL
)
TOOLCALL_PATTERN = re.compile(r'<!--\s*ToolCall:\s*(\{.*?\})\s*-->')

class ParseErrorType(Enum):
    """解析错误类型"""
    JSON_DECODE_ERROR = "json_decode_error"
    INVALID_FORMAT = "invalid_format"
    PYDANTIC_VALIDATION_ERROR = "pydantic_validation_error"


class ParseError(BaseModel):
    """解析错误"""
    error_type: ParseErrorType
    message: str
    raw_content: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)
    
    def __str__(self):
        return f"[{self.error_type.value}] {self.message}"

class TaskCompleted(BaseModel):
    """任务完成"""
    completed: Literal[True] = Field(description="Task completed")
    confidence: float = Field(description="Confidence in the quality of the completion")

class TaskCannotContinue(BaseModel):
    """任务无法继续"""
    completed: Literal[False] = Field(description="Task cannot continue")
    status: Literal['refused', 'need_info', 'failed'] = Field(description="Status of the task")
    reason: str | None = Field(default=None, description="Reason for the task status")
    suggestion: str | None = Field(default=None, description="Suggestion to resolve the issue")

class FrontMatter(BaseModel):
    """Front Matter 数据"""
    task_status: TaskCompleted | TaskCannotContinue = Field(description="Task status")

class Response(BaseModel):
    """响应对象 - 封装解析结果"""
    message: ChatMessage = Field(default_factory=ChatMessage)
    content_pos: int | None = Field(default=None, description="Content position")
    task_status: TaskCompleted | TaskCannotContinue | None = Field(default=None, description="Task status")
    code_blocks: List[CodeBlock] | None = Field(default=None, description="Code blocks")
    tool_calls: List[ToolCall] | None = Field(default=None, description="Tool calls")
    errors: Errors | None = Field(default=None, description="Errors")
    
    @property
    def log(self):
        return self._log
    
    def should_continue(self) -> bool:
        return self.errors or self.tool_calls
    
    def model_post_init(self, __context: Any):
        self._log = logger.bind(src='Response')

    def __bool__(self):
        return bool(self.code_blocks) or bool(self.tool_calls)
    
    def _add_tool_calls(self, tool_calls: List[ToolCall]):
        if not tool_calls:
            return
        if self.tool_calls:
            self.tool_calls.extend(tool_calls)
        else:
            self.tool_calls = tool_calls

    @classmethod
    def from_message(cls, message: ChatMessage, parse_mcp: bool = False) -> 'Response':
        """
        内部解析方法
        
        Args:
            markdown_text: 要解析的 Markdown 文本
            parse_mcp: 是否解析 MCP 调用
        """
        self = cls(message=message)
        markdown = message.content
        errors = Errors()
        self._parse_front_matter(markdown)
        if self.content_pos:
            markdown = markdown[self.content_pos:]

        errors.extend(self._parse_code_blocks(markdown))
        
        # 解析工具调用
        errors.extend(self._parse_tool_calls(markdown))
        
        # 解析 MCP 调用（如果需要）
        if parse_mcp:
            errors.extend(self._parse_mcp_calls(markdown))
        
        if errors:
            self.errors = errors
        return self
    
    def _parse_code_blocks(self, markdown: str) -> Errors:
        """解析代码块"""
        errors = Errors()
        code_blocks = []
        for match in BLOCK_PATTERN.finditer(markdown):
            start_json, _, lang, content, end_json = match.groups()
            
            # 解析开始标签
            try:
                start_meta = json.loads(start_json)
            except json.JSONDecodeError as e:
                errors.add(
                    "Invalid JSON in Block-Start",
                    json_str=start_json,
                    exception=str(e),
                    position="Block-Start",
                    error_type=ParseErrorType.JSON_DECODE_ERROR,
                )
                continue
            
            # 解析结束标签
            try:
                end_meta = json.loads(end_json)
            except json.JSONDecodeError as e:
                errors.add(
                    "Invalid JSON in Block-End",
                    json_str=end_json,
                    exception=str(e),
                    position="Block-End",
                    error_type=ParseErrorType.JSON_DECODE_ERROR,
                )
                continue
            
            # 检查名称是否一致
            start_name = start_meta.get("name")
            end_name = end_meta.get("name")
            
            if not start_name or start_name != end_name:
                errors.add(
                    "Block-Start and Block-End name mismatch",
                    start_name=start_name,
                    end_name=end_name,
                    error_type=ParseErrorType.INVALID_FORMAT,
                )
                continue
            
            # 创建 CodeBlock 对象，让 Pydantic 处理验证
            try:
                code_block = CodeBlock(
                    name=start_name,
                    lang=lang or "markdown",
                    code=content,
                    path=start_meta.get("path")
                )
                code_blocks.append(code_block)
            except ValidationError as e:
                errors.add(
                    "Failed to create CodeBlock",
                    exception=str(e),
                    error_type=ParseErrorType.PYDANTIC_VALIDATION_ERROR,
                )

        if code_blocks:
            self.code_blocks = code_blocks
        return errors
    
    def _parse_tool_calls(self, markdown: str) -> Errors:
        """解析工具调用"""
        errors = Errors()
        tool_calls = []
        for match in TOOLCALL_PATTERN.finditer(markdown):
            json_str = match.group(1)
            
            # 直接使用 Pydantic 解析，让它处理所有验证
            try:
                tool_call = ToolCall.model_validate_json(json_str)
                tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                errors.add(
                    "Invalid JSON in ToolCall",
                    json_str=json_str,
                    exception=str(e),
                    error_type=ParseErrorType.JSON_DECODE_ERROR,
                )
            except ValidationError as e:
                errors.add(
                    "Invalid ToolCall data",
                    json_str=json_str,
                    exception=str(e),
                    error_type=ParseErrorType.PYDANTIC_VALIDATION_ERROR,
                )
        self._add_tool_calls(tool_calls)
        return errors
    
    def _parse_mcp_calls(self, markdown: str) -> Errors:
        """解析 MCP 调用"""
        errors = Errors()
        tool_calls = []
        mcp_calls = extra_call_tool_blocks(self.code_blocks)
        if not mcp_calls:
            mcp_calls = extract_call_tool_str(markdown)

        if not mcp_calls:
            return errors
        
        for idx, call in enumerate(mcp_calls, start=1):
            try:
                # 将原始 MCP 调用包装为符合 ToolCall 模型的结构
                # 期望形如：
                # {
                #   "id": "<unique>",
                #   "name": "MCP",
                #   "arguments": {
                #       "action": "call_tool",
                #       "name": "server.tool",
                #       "arguments": {...}
                #   }
                # }
                wrapped = {
                    "id": f"mcp-{idx}-{uuid4().hex[:8]}",
                    "name": "MCP",
                    "arguments": call,
                }
                mcp_call = ToolCall.model_validate(wrapped)
                tool_calls.append(mcp_call)
            except ValidationError as e:
                errors.add(
                    "Invalid MCPToolCall data",
                    data=call,
                    exception=str(e),
                    error_type=ParseErrorType.PYDANTIC_VALIDATION_ERROR,
                )
        self._add_tool_calls(tool_calls)
        return errors
    
    def _parse_front_matter(self, md_text: str) -> Errors:
        """
        解析 Markdown 字符串，提取 YAML front matter 和正文内容。

        参数：
            md_text: 包含 YAML front matter 和 Markdown 内容的字符串

        返回：
            (errors, content)：
            - errors 是解析错误，若无 front matter 则为空字典
            - content 是去除 front matter 后的 Markdown 正文字符串
        """
        errors = Errors()
        yaml_dict = None
        match = re.match(FRONT_MATTER_PATTERN, md_text, re.DOTALL)
        if match:
            yaml_str = match.group(1)
            try:
                yaml_dict = yaml.safe_load(yaml_str)
                self.log.info('Front matter', yaml_dict=yaml_dict)
            except yaml.YAMLError:
                self.log.error('Invalid front matter', yaml_str=yaml_str)
                errors.add(
                    "Invalid front matter",
                    yaml_str=yaml_str,
                    error_type=ParseErrorType.INVALID_FORMAT,
                )
            self.content_pos = match.end()

        if yaml_dict:
            try:
                self.task_status = FrontMatter.model_validate({'task_status': yaml_dict}).task_status
            except ValidationError as e:
                self.log.error('Invalid front matter', yaml_dict=yaml_dict, exception=str(e), errors=e.errors())
                errors.add(
                    "Invalid front matter",
                    yaml_dict=yaml_dict,
                    exception=str(e),
                    errors = e.errors(),
                    error_type=ParseErrorType.PYDANTIC_VALIDATION_ERROR,
                )

        return errors