#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import json
import uuid
from typing import List, Union, TYPE_CHECKING
from pathlib import Path
from collections import namedtuple
from importlib.resources import read_text

import requests
from pydantic import BaseModel, Field, ValidationError
from loguru import logger

from .. import T, __respkg__, Stoppable, TaskPlugin
from ..exec import BlockExecutor
from ..llm import SystemMessage
from .runtime import CliPythonRuntime
from .utils import get_safe_filename, validate_file
from .events import TypedEventBus
from .multimodal import MMContent   
from .context import ContextManager, ContextData
from .toolcalls import ToolCallProcessor
from .chat import MessageStorage, ChatMessage, UserMessage
from .step import Step, StepData
from .blocks import CodeBlocks
from .client import Client

if TYPE_CHECKING:
    from .taskmgr import TaskManager

MAX_ROUNDS = 16
TASK_VERSION = 20250818

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

class TaskData(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    version: int = Field(default=TASK_VERSION, frozen=True)
    steps: List[StepData] = Field(default_factory=list)
    blocks: CodeBlocks = Field(default_factory=CodeBlocks)
    context: ContextData = Field(default_factory=ContextData)
    message_storage: MessageStorage = Field(default_factory=MessageStorage)
    
    def add_step(self, step: StepData):
        self.steps.append(step)

class Task(Stoppable):
    def __init__(self, manager: TaskManager, data: TaskData | None = None):
        super().__init__()
        data = data or TaskData()
        self.task_id = data.id
        self.manager = manager
        self.settings = manager.settings
        self.log = logger.bind(src='task', id=self.task_id)

        # Basic properties
        self.workdir = manager.cwd
        self.event_bus = TypedEventBus()
        self.cwd = self.workdir / self.task_id
        self.gui = manager.settings.gui
        self._saved = False
        self.max_rounds = manager.settings.get('max_rounds', MAX_ROUNDS)
        self.role = manager.role_manager.current_role

        # TaskData Objects
        self.steps: List[Step] = [Step(self, step_data) for step_data in data.steps]
        self.blocks = data.blocks
        self.message_storage = data.message_storage
        self.context = data.context
        self.context_manager = ContextManager(self.message_storage, self.context, manager.settings.get('context_manager'))

        # Display
        if manager.display_manager:
            self.display = manager.display_manager.create_display_plugin()
            self.event_bus.add_listener(self.display)
        else:
            self.display = None

        # Objects for steps
        self.mcp = manager.mcp
        self.prompts = manager.prompts
        self.client_manager = manager.client_manager
        self.runtime = CliPythonRuntime(self)
        self.runner = BlockExecutor()
        self.runner.set_python_runtime(self.runtime)
        self.client = Client(self)
        self.tool_call_processor = ToolCallProcessor()

        # Plugins
        plugins: dict[str, TaskPlugin] = {}
        for plugin_name, plugin_data in self.role.plugins.items():
            plugin = manager.plugin_manager.create_task_plugin(plugin_name, plugin_data)
            if not plugin:
                self.log.warning(f"Create task plugin {plugin_name} failed")
                continue
            self.runtime.register_plugin(plugin)
            self.event_bus.add_listener(plugin)
            plugins[plugin_name] = plugin
        self.plugins = plugins

    def emit(self, event_name: str, **kwargs):
        event = self.event_bus.emit(event_name, **kwargs)
        if self.steps:
            #TODO: fix this
            self.steps[-1]['events'].append(event)
        return event

    def get_system_message(self) -> ChatMessage:
        params = {}
        if self.mcp:
            params['mcp_tools'] = self.mcp.get_tools_prompt()
        params['util_functions'] = self.runtime.get_builtin_functions()
        params['tool_functions'] = self.runtime.get_plugin_functions()
        params['role'] = self.role
        system_prompt = self.prompts.get_default_prompt(**params)
        msg = SystemMessage(content=system_prompt)
        return self.message_storage.store(msg)
    
    def delete_step(self, index: int) -> bool:
        if index < 0 or index >= len(self.steps):
            return False
        self.steps.pop(index)
        return True

    def clear_steps(self):
        self.steps.clear()
        return True
    
    def get_status(self):
        return {
            'llm': self.client.name,
            'blocks': len(self.blocks),
            'steps': len(self.steps),
        }

    def get_task_data(self):
        return TaskData(
            id=self.task_id,
            steps=[step.data for step in self.steps],
            blocks=self.blocks,
            context=self.context,
            message_storage=self.message_storage
        )
    
    @classmethod
    def from_file(cls, path: Union[str, Path], manager: TaskManager) -> 'Task':
        """从文件创建 TaskState 对象"""
        path = Path(path)
        validate_file(path)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
                try:
                    model_context = {'message_storage': MessageStorage.model_validate(data['message_storage'])}
                except:
                    model_context = None

                task_data = TaskData.model_validate(data, context=model_context)
                task = cls(manager, task_data)
                logger.info('Loaded task state from file', path=str(path), task_id=task.task_id)
                return task
        except json.JSONDecodeError as e:
            raise TaskError(f'Invalid JSON file: {e}') from e
        except ValidationError as e:
            raise TaskError(f'Invalid task state: {e.errors()}') from e
        except Exception as e:
            raise TaskError(f'Failed to load task state: {e}') from e
    
    def to_file(self, path: Union[str, Path]) -> None:
        """保存任务状态到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                data = self.get_task_data()
                f.write(data.model_dump_json(indent=2, exclude_none=True))
            self.log.info('Saved task state to file', path=str(path))
        except Exception as e:
            self.log.exception('Failed to save task state', path=str(path))
            raise TaskError(f'Failed to save task state: {e}') from e
        
    def _auto_save(self):
        """自动保存任务状态"""
        # 如果任务目录不存在，则不保存
        cwd = self.cwd
        if not cwd.exists():
            self.log.warning('Task directory not found, skipping save')
            return
        
        try:
            self.to_file(cwd / "task.json")
            
            display = self.display
            if display:
                filename = cwd / "console.html"
                display.save(filename, clear=False, code_format=CONSOLE_WHITE_HTML)
            
            self._saved = True
            self.log.info('Task auto saved')
        except Exception as e:
            self.log.exception('Error saving task')
            self.emit('exception', msg='save_task', exception=e)

    def done(self):
        if not self.steps:
            self.log.warning('Task not started, skipping save')
            return
        
        os.chdir(self.workdir)  # Change back to the original working directory
        curname = self.task_id
        if os.path.exists(curname):
            if not self._saved:
                self.log.warning('Task not saved, trying to save')
                self._auto_save()

            newname = get_safe_filename(self.steps[0]['instruction'], extension=None)
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

    def prepare_user_prompt(self, instruction: str, first_run: bool=False) -> UserMessage:
        """处理多模态内容并验证模型能力"""
        mmc = MMContent(instruction, base_path=self.workdir)
        try:
            message = mmc.message
        except Exception as e:
            raise TaskInputError(T("Invalid input"), e) from e

        content = message.content
        if isinstance(content, str):
            if first_run:
                content = self.prompts.get_task_prompt(content, gui=self.gui)
            else:
                content = self.prompts.get_chat_prompt(content, self.instruction)
            message.content = content
        elif not self.client.has_capability(message):
            raise TaskInputError(T("Current model does not support this content"))

        return message

    def run(self, instruction: str, title: str | None = None):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        instruction: 用户输入的字符串（可包含@file等多模态标记）
        """
        first_run = not self.steps
        user_message = self.prepare_user_prompt(instruction, first_run)
        if first_run:
            self.context_manager.add_message(self.get_system_message())

        # We MUST create the task directory here because it could be a resumed task.
        self.cwd.mkdir(exist_ok=True, parents=True)
        os.chdir(self.cwd)
        self._saved = False

        step = Step(self, StepData(instruction=instruction, title=title))
        self.steps.append(step)
        self.emit('step_started', instruction=instruction, step=len(self.steps) + 1, title=title)
        response = step.run(user_message)
        self.emit('step_completed', summary=step.get_summary(), response=response)

        self._auto_save()
        self.log.info('Step done', rounds=len(step['rounds']))

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