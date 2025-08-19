#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import time
from typing import Any, List, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from collections import namedtuple
from importlib.resources import read_text

import requests
from pydantic import BaseModel, Field, ValidationError
from loguru import logger

from .. import T, __respkg__, Stoppable, TaskPlugin
from ..exec import BlockExecutor
from .runtime import CliPythonRuntime
from .utils import get_safe_filename, validate_file
from .blocks import CodeBlock, CodeBlocks
from .events import TypedEventBus
from ..display import DisplayPlugin
from .multimodal import MMContent, LLMContext
from .context_manager import ContextManager, ContextConfig
from .toolcalls import ToolCallProcessor, ToolCallResult, EditToolResult
from .response import Response
from .events import BaseEvent
from .llm import ChatHistory, Client, ClientManager
from .role import Role
from .prompts import Prompts
from .types import Traverser, DataMixin

TASK_VERSION = 20250818
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
    plugins: List[TaskPlugin]
    event_bus: TypedEventBus
    mcp: Any
    runner: BlockExecutor
    role: Role
    display: DisplayPlugin | None
    tool_call_processor: ToolCallProcessor
    traverser: Traverser
    client_manager: ClientManager

    def __post_init__(self):
        self._log = logger.bind(src='TaskContext')
        # 创建上下文管理器（从Client移到Task）
        self.runtime = CliPythonRuntime(self)
        self.runner.set_python_runtime(self.runtime)
        context_settings = self.settings.get('context_manager', {})
        self.context_manager = ContextManager(ContextConfig.from_dict(context_settings))
        self.client = self.client_manager.Client(self)
    
        for plugin in self.plugins:
            self.event_bus.add_listener(plugin)
            self.runtime.register_plugin(plugin)
            
        # 注册显示效果插件
        if self.display:
            self.event_bus.add_listener(self.display)

    @property
    def step(self):
        return self.traverser.last
    
    @property
    def gui(self):
        return self.settings.gui
    
    @property
    def max_rounds(self):
        return self.settings.get('max_rounds', MAX_ROUNDS)
    
    def get_block(self, name: str):
        return self.traverser.find_first(lambda step: step.blocks.get(name))

    def emit(self, event_name: str, **kwargs):
        """重写broadcast方法以记录事件"""
        # 调用父类的broadcast方法获取强类型事件
        event = self.event_bus.emit(event_name, **kwargs)
        
        # 记录强类型事件对象到事件记录器
        if self.step is not None:
            self.step.events.append(event)
        return event

    def run_code_block(self, block):
        """运行代码块"""
        self.emit('exec_started', block=block)
        result = self.runner(block)
        self.emit('exec_completed', result=result, block=block)
        return result

    def get_system_prompt(self) -> str:
        params = {}
        if self.mcp:
            params['mcp_tools'] = self.mcp.get_tools_prompt()
        params['util_functions'] = self.runtime.get_builtin_functions()
        params['tool_functions'] = self.runtime.get_plugin_functions()
        params['role'] = self.role
        system_prompt = self.prompts.get_default_prompt(**params)
        return system_prompt
             
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

class StepData(BaseModel):
    instruction: str
    title: str | None = None
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    result: Response | None = None
    chats: ChatHistory = Field(default_factory=ChatHistory)
    events: List[BaseEvent.get_subclasses_union()] = Field(default_factory=list)
    rounds: List[Round] = Field(default_factory=list)
    blocks: CodeBlocks = Field(default_factory=CodeBlocks)

    def add_blocks(self, blocks: List[CodeBlock]):
        self.blocks.add_blocks(blocks)

    def add_round(self, round: Round):
        self.rounds.append(round)

class Step(DataMixin):
    __expose__ = {'events', 'blocks', 'result', 'chats', 'instruction', 'start_time', 'rounds'}

    def __init__(self, context: TaskContext, data: StepData):
        self.context = context
        self._log = logger.bind(src='Step')
        self._data = data
    
    @property
    def data(self):
        return self._data
    
    def request(self, context: LLMContext, *, system_prompt=None):
        client = self.context.client
        self.context.emit('request_started', llm=client.name)
        msg = client(context, system_prompt=system_prompt)
        self.context.emit('response_completed', llm=client.name, msg=msg)
        return msg.content if msg else None

    def process(self, markdown):
        response = Response.from_markdown(markdown, parse_mcp=self.context.mcp)
        self.context.emit('parse_reply_completed', response=response)
        results = []
        if not response.errors:
            if response.task_status:
                self.context.emit('task_status', status=response.task_status)

            if response.code_blocks:
                self._data.add_blocks(response.code_blocks)
            
            if response.tool_calls:
                results = self.context.tool_call_processor.process(self.context, response.tool_calls)

        return Round(response=response, toolcall_results=results)
        
    def run(self, user_prompt: LLMContext, system_prompt: str | None = None) -> Response | None:
        rounds = 1
        max_rounds = self.context.max_rounds
        prompt = user_prompt
        while rounds <= max_rounds:
            markdown = self.request(prompt, system_prompt=system_prompt)
            if not markdown:
                self.log.error('No response from LLM')
                break

            round = self.process(markdown)
            self._data.add_round(round)
            if not round.should_continue():
                self._data.result = round.response
                break

            rounds += 1
            prompt = round.get_response_prompt(self.context.prompts)

        self._data.end_time = time.time()
        return self._data.result

    def get_summary(self, detail=False):
        data = {}
        context_manager = self.context.context_manager
        if detail:
            data['usages'] = context_manager.get_usage()

        summary = context_manager.get_summary()
        summary['elapsed_time'] = time.time() - self.start_time
        summarys = "{rounds} | {time:.3f}s/{elapsed_time:.3f}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        data['summary'] = summarys
        return data
    
class TaskData(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    version: int = Field(default=TASK_VERSION, frozen=True)
    steps: List[StepData] = Field(default_factory=list)

    def add_step(self, step: StepData):
        self.steps.append(step)

class Task(Stoppable):
    def __init__(self, context: 'MainContext', data: TaskData | None = None):
        super().__init__()
        self._id = uuid.uuid4().hex
        self._steps: List[Step] = []
        self._workdir = context.cwd
        self._cwd = self._workdir / self.task_id
        self._log = logger.bind(src='task', id=self.task_id)
        self._main_context = context
        self._task_context = self.create_task_context(context)

        if data:
            # Rebuild steps from data
            self._log.info(f'Rebuilding steps from task {data.id}', steps=len(data.steps))
            for step_data in data.steps:
                step = Step(self._task_context, step_data)
                self._steps.append(step)

    @property
    def log(self):
        return self._log
    
    @property
    def task_id(self):
        return self._id
    
    @property
    def task_context(self):
        return self._task_context
    
    @property
    def main_context(self):
        return self._main_context
    
    @property
    def steps(self):
        return self._steps
    
    def create_task_context(self, context):
        if context.display_manager:
            display = context.display_manager.create_display_plugin()
        else:
            display = None

        role = context.role_manager.current_role
        plugins: List[TaskPlugin] = []
        for plugin_name, plugin_data in role.plugins.items():
            plugin = context.plugin_manager.create_task_plugin(plugin_name, plugin_data)
            if not plugin:
                self.log.warning(f"Create task plugin {plugin_name} failed")
                continue
            plugins.append(plugin)

        return TaskContext(
            settings=context.settings,
            prompts=context.prompts,
            plugins=plugins,
            event_bus=TypedEventBus(),
            mcp=context.mcp,
            runner=BlockExecutor(),
            role=context.role_manager.current_role,
            display=display,
            tool_call_processor=ToolCallProcessor(),
            traverser=Traverser(self._steps),
            client_manager=context.client_manager,
        )

    def get_status(self):
        return {
            'llm': self.task_context.client.name,
            'blocks': sum(len(step.blocks) for step in self._steps),
            'steps': len(self._steps),
        }

    @classmethod
    def from_file(cls, path: Union[str, Path], context: 'MainContext') -> 'Task':
        """从文件创建 TaskState 对象"""
        path = Path(path)
        validate_file(path)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    json_content = f.read()
                    task_data = TaskData.model_validate_json(json_content)
                except ValidationError as e:
                    raise TaskError(f'Invalid task state: {e.errors()}') from e
                task = cls(context, task_data)
                logger.info('Loaded task state from file', path=str(path), task_id=task.task_id)
                return task
        except json.JSONDecodeError as e:
            raise TaskError(f'Invalid JSON file: {e}') from e
        except Exception as e:
            raise TaskError(f'Failed to load task state: {e}') from e
    
    def to_file(self, path: Union[str, Path]) -> None:
        """保存任务状态到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                steps_data = [step.data for step in self._steps]
                data = TaskData(steps=steps_data, id=self.task_id)
                f.write(data.model_dump_json(indent=2, exclude_none=True))
            self.log.info('Saved task state to file', path=str(path))
        except Exception as e:
            self.log.exception('Failed to save task state', path=str(path))
            raise TaskError(f'Failed to save task state: {e}') from e
        
    def _auto_save(self):
        """自动保存任务状态"""
        # 如果任务目录不存在，则不保存
        cwd = self._cwd
        if not cwd.exists():
            self.log.warning('Task directory not found, skipping save')
            return
        
        try:
            self.to_file(cwd / "task.json")
            
            display = self.task_context.display
            if display:
                filename = cwd / "console.html"
                display.save(filename, clear=False, code_format=CONSOLE_WHITE_HTML)
            
            self._saved = True
            self.log.info('Task auto saved')
        except Exception as e:
            self.log.exception('Error saving task')
            self.task_context.emit('exception', msg='save_task', exception=e)

    def done(self):
        if not self._steps:
            self.log.warning('Task not started, skipping save')
            return
        
        os.chdir(self._workdir)  # Change back to the original working directory
        curname = self.task_id
        if os.path.exists(curname):
            if not self._saved:
                self.log.warning('Task not saved, trying to save')
                self._auto_save()

            newname = get_safe_filename(self._steps[0].instruction, extension=None)
            if newname:
                try:
                    os.rename(curname, newname)
                except Exception as e:
                    self.log.exception('Error renaming task directory', curname=curname, newname=newname)
        else:
            newname = None
            self.log.warning('Task directory not found')

        self.log.info('Task done', path=newname)
        self.task_context.emit('task_completed', path=newname)
        #self.context.diagnose.report_code_error(self.runner.history)
        if self.task_context.settings.get('share_result'):
            self.sync_to_cloud()

    def _prepare_user_prompt(self, instruction: str, first_run: bool=False) -> LLMContext:
        """处理多模态内容并验证模型能力"""
        mmc = MMContent(instruction, base_path=self._workdir)
        try:
            content = mmc.content
        except Exception as e:
            raise TaskInputError(T("Invalid input"), e) from e

        if not self.task_context.client.has_capability(content):
            raise TaskInputError(T("Current model does not support this content"))
        
        if isinstance(content, str):
            if first_run:
                content = self.task_context.prompts.get_task_prompt(content, gui=self.task_context.gui)
            else:
                content = self.task_context.prompts.get_chat_prompt(content, self.instruction)
        return content

    def run(self, instruction: str, title: str | None = None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        instruction: 用户输入的字符串（可包含@file等多模态标记）
        """
        first_run = not self._steps
        user_prompt = self._prepare_user_prompt(instruction, first_run)
        system_prompt = self.task_context.get_system_prompt() if first_run else None

        # We MUST create the task directory here because it could be a resumed task.
        self._cwd.mkdir(exist_ok=True, parents=True)
        os.chdir(self._cwd)
        self._saved = False

        step_data = StepData(instruction=instruction, title=title)
        step = Step(self.task_context, step_data)
        self._steps.append(step)
        self.task_context.emit('step_started', instruction=instruction, step=len(self._steps) + 1, title=title)
        response = step.run(user_prompt, system_prompt=system_prompt)
        self.task_context.emit('step_completed', summary=step.get_summary(), response=response)

        self._auto_save()
        self.log.info('Step done', rounds=len(step.rounds))

    def sync_to_cloud(self):
        """ Sync result
        """
        url = T("https://store.aipy.app/api/work")

        trustoken_apikey = self.task_context.settings.get('llm', {}).get('Trustoken', {}).get('api_key')
        if not trustoken_apikey:
            trustoken_apikey = self.task_context.settings.get('llm', {}).get('trustoken', {}).get('api_key')
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
                    'llm': self.task_context.context_manager.json(),
                    'runner': self.task_context.runner.history,
                }, ensure_ascii=False, default=str),
                parse_constant=str)
            response = requests.post(url, json=data, verify=True,  timeout=30)
        except Exception as e:
            self.task_context.emit('exception', msg='sync_to_cloud', exception=e)
            return False

        url = None
        status_code = response.status_code
        if status_code in (200, 201):
            data = response.json()
            url = data.get('url', '')

        self.task_context.emit('upload_result', status_code=status_code, url=url)
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
