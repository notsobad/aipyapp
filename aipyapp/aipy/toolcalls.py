#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""工具调用系统模块"""

from enum import Enum
from typing import Union, List, Dict, Any, Optional

from loguru import logger
from pydantic import BaseModel, model_validator, Field

from .types import Error

class ToolName(str, Enum):
    """Tool name"""
    EDIT = "Edit"
    EXEC = "Exec"
    MCP = "MCP"

class ToolResult(BaseModel):
    """Tool result"""
    error: Error | None = Field(title="Tool error", default=None)
    result: Dict[str, Any] | None = Field(title="Tool result", default=None)

    def to_json(self):
        return self.model_dump_json(exclude_none=True, exclude_unset=True)

class ExecToolArgs(BaseModel):
    """Exec tool arguments"""
    name: str = Field(title="Code block name to execute", min_length=1, strip_whitespace=True)

class ExecToolResult(ToolResult):
    """Exec tool result"""
    block_name: str = Field(title="Code block name executed", min_length=1, strip_whitespace=True)

class EditToolArgs(BaseModel):
    """Edit tool arguments"""
    name: str = Field(title="Code block name to edit", min_length=1, strip_whitespace=True)
    old: str = Field(title="Code to replace", min_length=1)
    new: str = Field(title="Replacement code")
    replace_all: Optional[bool] = Field(False, title="Replace all occurrences")

class EditToolResult(ToolResult):
    """Edit tool result"""
    block_name: str = Field(title="Code block name edited", min_length=1, strip_whitespace=True)
    success: bool = Field(title="Edit success", default=False)
    new_version: Optional[int] = Field(None, title="New version number of the code block")

class MCPToolArgs(BaseModel):
    """MCP tool arguments"""
    model_config = {
        'extra': 'allow'
    }

class MCPToolResult(ToolResult):
    """MCP tool result"""
    result: Dict[str, Any] = Field(default_factory=dict)

class ToolCall(BaseModel):
    """Tool call"""
    name: ToolName
    arguments: Union[ExecToolArgs, EditToolArgs, MCPToolArgs]

    @model_validator(mode='before')
    @classmethod
    def alias_name(cls, values: Dict[str, Any]):
        if isinstance(values, dict):
            if "name" not in values and "action" in values:
                values["name"] = values.pop("action")
        return values
       
    def __str__(self):
        return f"ToolCall(name='{self.name}', args={self.arguments})"
    
    def __repr__(self):
        return self.__str__()

class ToolCallResult(BaseModel):
    """Tool call result"""
    tool_name: ToolName
    result: Union[ExecToolResult, EditToolResult, MCPToolResult] = Field(title="Tool result")

class ToolCallProcessor:
    """工具调用处理器 - 高级接口"""
    
    def __init__(self, task):
        self.task = task
        self.log = logger.bind(src='ToolCallProcessor')
    
    def process(self, tool_calls: List[ToolCall]) -> List[ToolCallResult]:
        """
        处理工具调用列表
        
        Args:
            tool_calls: ToolCall 对象列表
            
        Returns:
            List[ToolCallResult]: 包含所有执行结果的列表
        """
        results = []
        failed_blocks = set()  # 记录编辑失败的代码块
        
        for tool_call in tool_calls:
            name = tool_call.name
            if name == ToolName.EXEC:
                # 如果这个代码块之前编辑失败，跳过执行
                block_name = tool_call.arguments.name
                if block_name in failed_blocks:
                    error = Error.new(
                        'Execution skipped: previous edit of the block failed',
                        block_name=block_name
                    )
                    results.append(ToolCallResult(
                        tool_name=name,
                        error=error
                    ))
                    continue
            
            # 执行工具调用
            result = self.call_tool(tool_call)
            results.append(result)
            
            # 如果是编辑失败，记录失败的代码块
            if name == ToolName.EDIT and result.result.error:
                failed_blocks.add(tool_call.arguments.name)
        
        return results

    def call_tool(self, tool_call: ToolCall) -> ToolCallResult:
        """
        执行工具调用
        
        Args:
            tool_call: ToolCall 对象
            
        Returns:
            ToolResult: 执行结果
        """
        self.task.emit('tool_call_started', tool_call=tool_call)
        if tool_call.name == ToolName.EXEC:
            result = self._call_exec(tool_call)
        elif tool_call.name == ToolName.EDIT:
            result = self._call_edit(tool_call)
        elif tool_call.name == ToolName.MCP:
            result = self._call_mcp(tool_call)
        else:
            result = ToolResult(error=Error('Unknown tool'))

        toolcall_result = ToolCallResult(
            tool_name=tool_call.name,
            result=result
        )
        self.task.emit('tool_call_completed', result=toolcall_result)
        return toolcall_result
           
    def _call_edit(self, tool_call: ToolCall) -> EditToolResult:
        """执行 Edit 工具"""
        task = self.task
        args = tool_call.arguments
        
        error = task.code_blocks.edit_block(args.name, args.old, args.new, args.replace_all)
        if not error:
            success = True
            new_version = task.code_blocks.get(args.name).version
        else:
            success = False
            new_version = None
        result = EditToolResult(
            block_name=args.name,
            success=success,
            new_version=new_version
        )
        return result
    
    def run_code_block(self, block_name: str) -> ExecToolResult:
        """执行代码块"""
        tool_call = ToolCall(
            name=ToolName.EXEC,
            arguments=ExecToolArgs(name=block_name)
        )
        return self.call_tool(tool_call)
    
    def _call_exec(self, tool_call: ToolCall) -> ExecToolResult:
        """执行 Exec 工具"""
        args = tool_call.arguments
        block_name = args.name
        
        # 获取代码块
        block = self.task.code_blocks.get(block_name)
        if not block:
            return ExecToolResult(
                block_name=block_name,
                error=Error.new("Code block not found")
            )
        
        # 执行代码块
        try:
            result = self.task.runner(block)
            return ExecToolResult(
                block_name=block_name,
                result=result
            )
        except Exception as e:
            self.log.exception(f"Execution failed with exception: {e}")
            return ExecToolResult(
                block_name=block_name,
                error=Error.new("Execution failed with exception", exception=str(e))
            )
    
    def _call_mcp(self, tool_call: ToolCall) -> MCPToolResult:
        """执行 MCP 工具"""
        result = self.task.mcp.call_tool(tool_call.name, tool_call.arguments)
        return MCPToolResult(
            result=result
        )