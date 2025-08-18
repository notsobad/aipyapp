#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import time
from typing import Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from collections import namedtuple
from importlib.resources import read_text

import requests
from pydantic import BaseModel, Field
from loguru import logger

from .. import T, __respkg__, Stoppable
from ..exec import BlockExecutor
from .runtime import CliPythonRuntime
from .utils import get_safe_filename
from .blocks import CodeBlocks
from .events import TypedEventBus
from .step_manager import StepManager
from .multimodal import MMContent, LLMContext
from .context_manager import ContextManager, ContextConfig
from .task_state import TaskState
from .toolcalls import ToolCallProcessor, ToolCallResult, EditToolResult
from .response import Response
from .events import BaseEvent
from .llm import ChatHistory, Client
from .role import Role
from .prompts import Prompts
from .types import Traverser

MAX_ROUNDS = 16
CONSOLE_WHITE_HTML = read_text(__respkg__, "console_white.html")
CONSOLE_CODE_HTML = read_text(__respkg__, "console_code.html")

class TaskError(Exception):
    """Task 异常"""
    pass

class TaskInputError(TaskError):
    """Task 输入异常"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

class TastStateError(TaskError):
    """Task 状态异常"""
    def __init__(self, message: str, **kwargs):
        self.message = message
        self.data = kwargs
        super().__init__(self.message)

@dataclass
class TaskContext:
    settings: dict
    prompts: Prompts
    cwd: Path
    event_bus: TypedEventBus
    mcp: Any
    runner: BlockExecutor
    client: Client
    role: Role
    display: Any
    tool_call_processor: ToolCallProcessor
    traverser: Traverser
    step: Optional['Step'] = None

    def get_block(self, name: str):
        return self.traverser.find_first(lambda step: step.blocks.get(name))

class Round(BaseModel):
    response: Response = Field(default_factory=Response)
    toolcall_results: List[ToolCallResult] = Field(default_factory=list)

    def should_continue(self):
        """ Should continue? 
        1. Parse error
        2. have toolcall results
        """
        return self.response.errors or self.toolcall_results

    def get_response_prompt(self, prompts: Prompts):
        if self.response.errors:
            return prompts.get_parse_error_prompt(self.response.errors)
        if self.toolcall_results:
            return prompts.get_toolcall_results_prompt(self.toolcall_results)
        return None

class Step(BaseModel):
    instruction: str
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    result: Response | None = None
    chats: ChatHistory = Field(default_factory=ChatHistory)
    events: list[BaseEvent.get_subclasses_union] = Field(default_factory=list)
    rounds: List[Round] = Field(default_factory=list)
    blocks: CodeBlocks = Field(default_factory=CodeBlocks)

    def __init__(self, context: TaskContext, **kwargs):
        super().__init__(**kwargs)
        self._context = context
        self._log = logger.bind(src='Step')

    def model_post_init(self, __context):
        if __context and 'context' in __context:
            self._context = __context

    def __len__(self):
        return len(self.rounds)
    
    @property
    def context(self):
        return self._context

    @property
    def log(self):
        return self._log
    
    def request(self, context: LLMContext, *, system_prompt=None):
        event_bus = self.context.event_bus
        client = self.context.client
        event_bus.emit('request_started', llm=client.name)
        msg = client(context, system_prompt=system_prompt)
        event_bus.emit('response_completed', llm=client.name, msg=msg)
        return msg.content if msg else None

    def process(self, markdown):
        event_bus = self.context.event_bus
        response = Response.from_markdown(markdown, parse_mcp=self.context.mcp)
        event_bus.emit('parse_reply_completed', response=response)
        results = []
        if not response.errors:
            if response.task_status:
                event_bus.emit('task_status', status=response.task_status)

            if response.code_blocks:
                self.blocks.add_blocks(response.code_blocks)
            
            if response.tool_calls:
                results = self.context.tool_call_processor.process(self.context, response.tool_calls)

        return Round(response=response, toolcall_results=results)
        
    def run(self, user_prompt: LLMContext, system_prompt: str | None = None, max_rounds: int | None = None) -> Response | None:
        rounds = 1
        max_rounds = max_rounds or MAX_ROUNDS
        prompt = user_prompt
        while rounds <= max_rounds:
            markdown = self.request(prompt, system_prompt=system_prompt)
            if not markdown:
                self.log.error('No response from LLM')
                break

            round = self.process(markdown)
            self.rounds.append(round)
            if not round.should_continue():
                self.result = round.response
                break

            rounds += 1
            prompt = round.get_response_prompt(self.context.prompts)

        self.end_time = time.time()
        return self.result

class Task(Stoppable):
    MAX_ROUNDS = 16

    def __init__(self, context):
        super().__init__()
        self.task_id = uuid.uuid4().hex
        self.log = logger.bind(src='task', id=self.task_id)
        self._event_bus = TypedEventBus()

        self.context = context
        self.settings = context.settings
        self.prompts = context.prompts

        self.steps: List[Step] = []
        self._current_step: Step | None = None

        self.start_time = None
        self.done_time = None
        self.instruction = None
        self.saved = None
        
        #TODO: 移除 gui 参数
        self.gui = self.settings.gui

        self.cwd = context.cwd / self.task_id
        self.max_rounds = self.settings.get('max_rounds', self.MAX_ROUNDS)
        
        self.mcp = context.mcp
        self.display = None
        self.plugins = {}

        # 创建上下文管理器（从Client移到Task）
        context_settings = self.settings.get('context_manager', {})
        self.context_manager = ContextManager(ContextConfig.from_dict(context_settings))
        
        # 创建Client时传入context_manager
        self.role = context.role_manager.current_role
        self.runtime = CliPythonRuntime(self)
        self.step_manager = StepManager()

        self.init_plugins()
        self._task_context = self.create_task_context(context)

    @property
    def task_context(self):
        return self._task_context
    
    def create_task_context(self, context):
        runner = BlockExecutor()
        runner.set_python_runtime(self.runtime)
        return TaskContext(
            settings=context.settings,
            prompts=context.prompts,
            cwd=self.cwd,
            event_bus=self._event_bus,
            mcp=context.mcp,
            runner=runner,
            client=context.client_manager.Client(self, self.context_manager),
            role=context.role_manager.current_role,
            display=self.display,
            tool_call_processor=ToolCallProcessor(),
            traverser=Traverser(self.steps),
            step=self._current_step,
        )
    
    def emit(self, event_name: str, **kwargs):
        """重写broadcast方法以记录事件"""
        # 调用父类的broadcast方法获取强类型事件
        event = self._event_bus.emit(event_name, **kwargs)
        
        # 记录强类型事件对象到事件记录器
        if self._current_step:
            self._current_step.events.append(event)
        
        return event

    def restore_state(self, task_data: dict | TaskState):
        """从任务状态加载任务
        
        Args:
            task_data: 任务状态数据（字典格式）或 TaskState 对象
            
        Returns:
            Task: 加载的任务对象
        """
        # 支持传入字典或 TaskState 对象
        if isinstance(task_data, dict):
            task_state = TaskState.model_validate(task_data)
        elif isinstance(task_data, TaskState):
            task_state = task_data
        else:
            raise TastStateError('Invalid task_data type, expected dict or TaskState')
        
        # 使用 TaskState 恢复状态
        task_state.restore_to_task(self)

    def get_status(self):
        return {
            'llm': self.task_context.client.name,
            'blocks': sum(len(step.blocks) for step in self.steps),
            'steps': len(self.step_manager),
        }

    def init_plugins(self):
        """初始化插件"""
        plugin_manager = self.context.plugin_manager
        for plugin_name, plugin_data in self.role.plugins.items():
            plugin = plugin_manager.create_task_plugin(plugin_name, plugin_data)
            if not plugin:
                self.log.warning(f"Create task plugin {plugin_name} failed")
                continue
            self._event_bus.add_listener(plugin)
            self.runtime.register_plugin(plugin)
            self.plugins[plugin_name] = plugin
            
        # 注册显示效果插件
        if self.context.display_manager:
            self.display = self.context.display_manager.create_display_plugin()
            self._event_bus.add_listener(self.display)

    def to_record(self):
        TaskRecord = namedtuple('TaskRecord', ['task_id', 'start_time', 'done_time', 'instruction'])
        start_time = datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S') if self.start_time else '-'
        done_time = datetime.fromtimestamp(self.done_time).strftime('%H:%M:%S') if self.done_time else '-'
        return TaskRecord(
            task_id=self.task_id,
            start_time=start_time,
            done_time=done_time,
            instruction=self.title[:32] if self.title else '-'
        )
    
    def use(self, name):
        ret = self.client.use(name)
        return ret
        
    def _auto_save(self):
        """自动保存任务状态"""
        # 如果任务目录不存在，则不保存
        if not self.cwd.exists():
            self.log.warning('Task directory not found, skipping save')
            return
        
        self.done_time = time.time()
        try:
            # 创建 TaskState 对象并保存
            task_state = TaskState.from_task(self)
            task_state.save_to_file(self.cwd / "task.json")
            
            # 保存 HTML 控制台
            filename = self.cwd / "console.html"
            self.display.save(filename, clear=False, code_format=CONSOLE_WHITE_HTML)
            
            self.saved = True
            self.log.info('Task auto saved')
        except Exception as e:
            self.log.exception('Error saving task')
            self.emit('exception', msg='save_task', exception=e)

    def done(self):
        if not self.instruction or not self.start_time:
            self.log.warning('Task not started, skipping save')
            return
        
        os.chdir(self.context.cwd)  # Change back to the original working directory
        curname = self.task_id
        if os.path.exists(curname):
            if not self.saved:
                self.log.warning('Task not saved, trying to save')
                self._auto_save()

            newname = get_safe_filename(self.instruction, extension=None)
            if newname:
                try:
                    os.rename(curname, newname)
                except Exception as e:
                    self.log.exception('Error renaming task directory', curname=curname, newname=newname)
        else:
            newname = None
            self.log.warning('Task directory not found')

        self.log.info('Task done', path=newname)
        self.emit('task_completed', path=newname)
        #self.context.diagnose.report_code_error(self.runner.history)
        if self.settings.get('share_result'):
            self.sync_to_cloud()
        
    def run_code_block(self, block):
        """运行代码块"""
        self.emit('exec_started', block=block)
        result = self.runner(block)
        self.emit('exec_completed', result=result, block=block)
        return result

    def _get_summary(self, detail=False):
        data = {}
        context_manager = self.context_manager
        if detail:
            data['usages'] = context_manager.get_usage()

        summary = context_manager.get_summary()
        summary['elapsed_time'] = time.time() - self.start_time
        summarys = "{rounds} | {time:.3f}s/{elapsed_time:.3f}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        data['summary'] = summarys
        return data

    def _prepare_user_prompt(self, instruction: str, first_run: bool=False) -> LLMContext:
        """处理多模态内容并验证模型能力"""
        mmc = MMContent(instruction, base_path=self.context.cwd)
        try:
            content = mmc.content
        except Exception as e:
            raise TaskInputError(T("Invalid input"), e) from e

        if not self.task_context.client.has_capability(content):
            raise TaskInputError(T("Current model does not support this content"))
        
        if isinstance(content, str):
            if first_run:
                content = self.prompts.get_task_prompt(content, gui=self.gui)
            else:
                content = self.prompts.get_chat_prompt(content, self.instruction)
        return content

    def _prepare_system_prompt(self) -> str:
        params = {}
        if self.context.mcp:
            params['mcp_tools'] = self.context.mcp.get_tools_prompt()
        params['util_functions'] = self.runtime.get_builtin_functions()
        params['tool_functions'] = self.runtime.get_plugin_functions()
        params['role'] = self.role
        system_prompt = self.prompts.get_default_prompt(**params)
        return system_prompt

    def run(self, instruction: str, title: str | None = None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        instruction: 用户输入的字符串（可包含@file等多模态标记）
        """
        first_run = not self.steps
        title = title or instruction
        user_prompt = self._prepare_user_prompt(instruction, first_run)
        system_prompt = self._prepare_system_prompt() if first_run else None
 
        if first_run:
            self.start_time = time.time()
            self.instruction = instruction
            self.emit('task_started', instruction=instruction, task_id=self.task_id, title=title)
        else:
            self.emit('step_started', instruction=instruction, step=len(self.steps) + 1, title=title)

        # We MUST create the task directory here because it could be a resumed task.
        self.cwd.mkdir(exist_ok=True, parents=True)
        os.chdir(self.cwd)

        self.saved = False
        step = Step(instruction=instruction, title=title, context=self.task_context, max_rounds=self.max_rounds)
        self._current_step = step
        self.steps.append(step)
        response = step.run(user_prompt, system_prompt=system_prompt)

        summary = self._get_summary()
        self.emit('step_completed', summary=summary, response=response)
        self._auto_save()
        self.log.info('Step done', rounds=len(step))

    def sync_to_cloud(self):
        """ Sync result
        """
        url = T("https://store.aipy.app/api/work")

        trustoken_apikey = self.settings.get('llm', {}).get('Trustoken', {}).get('api_key')
        if not trustoken_apikey:
            trustoken_apikey = self.settings.get('llm', {}).get('trustoken', {}).get('api_key')
        if not trustoken_apikey:
            return False
        self.log.info('Uploading result to cloud')
        try:
            # Serialize twice to remove the non-compliant JSON type.
            # First, use the json.dumps() `default` to convert the non-compliant JSON type to str.
            # However, NaN/Infinity will remain.
            # Second, use the json.loads() 'parse_constant' to convert NaN/Infinity to str.
            data = json.loads(
                json.dumps({
                    'apikey': trustoken_apikey,
                    'author': os.getlogin(),
                    'instruction': self.instruction,
                    'llm': self.context_manager.json(),
                    'runner': self.runner.history,
                }, ensure_ascii=False, default=str),
                parse_constant=str)
            response = requests.post(url, json=data, verify=True,  timeout=30)
        except Exception as e:
            self.emit('exception', msg='sync_to_cloud', exception=e)
            return False

        url = None
        status_code = response.status_code
        if status_code in (200, 201):
            data = response.json()
            url = data.get('url', '')

        self.emit('upload_result', status_code=status_code, url=url)
        return True

    def delete_step(self, index: int):
        """删除指定索引的步骤 - 使用新的步骤管理器"""
        return self.step_manager.delete_step(index)

    def clear_steps(self):
        """清空所有步骤 - 使用新的步骤管理器"""
        self.step_manager.clear_all()
        return True

    def list_steps(self):
        """列出所有步骤 - 使用新的步骤管理器"""
        return self.step_manager.list_steps()

    def list_code_blocks(self):
        """列出所有代码块"""
        BlockRecord = namedtuple('BlockRecord', ['Index', 'Name', 'Version', 'Language', 'Path', 'Size'])
        
        rows = []
        for index, block in enumerate(self.code_blocks.history):
            # 计算代码大小
            code_size = len(block.code) if block.code else 0
            size_str = f"{code_size} chars"
            
            # 处理路径显示
            path_str = block.path if block.path else '-'
            if path_str != '-' and len(path_str) > 40:
                path_str = '...' + path_str[-37:]
            
            rows.append(BlockRecord(
                Index=index,
                Name=block.name,
                Version=f"v{block.version}",
                Language=block.lang,
                Path=path_str,
                Size=size_str
            ))
        
        return rows

    def get_code_block(self, index):
        """获取指定索引的代码块"""
        if index < 0 or index >= len(self.code_blocks.history):
            return None
        return self.code_blocks.history[index]
