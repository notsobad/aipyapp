#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import time
from datetime import datetime
from collections import namedtuple, OrderedDict
from importlib.resources import read_text

import requests
from loguru import logger

from .. import T, __respkg__
from ..exec import BlockExecutor
from .runtime import CliPythonRuntime
from .utils import get_safe_filename
from .blocks import CodeBlocks, CodeBlock
from ..interface import Stoppable, EventBus
from .step_manager import StepManager
from .multimodal import MMContent, LLMContext
from .context_manager import ContextManager, ContextConfig
from .event_recorder import EventRecorder
from .task_state import TaskState

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

class Task(Stoppable, EventBus):
    MAX_ROUNDS = 16

    def __init__(self, context):
        super().__init__()
        self.task_id = uuid.uuid4().hex
        self.log = logger.bind(src='task', id=self.task_id)
        
        self.context = context
        self.settings = context.settings
        self.prompts = context.prompts

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
        
        # 创建上下文管理器（从Client移到Task）
        context_settings = self.settings.get('context_manager', {})
        self.context_manager = ContextManager(ContextConfig.from_dict(context_settings))
        
        # 创建Client时传入context_manager
        self.client = context.client_manager.Client(self, self.context_manager)
        self.role = context.role_manager.current_role
        self.code_blocks = CodeBlocks()
        self.runtime = CliPythonRuntime(self)
        self.runner = BlockExecutor()
        self.runner.set_python_runtime(self.runtime)
        
        # 注册所有可追踪对象到步骤管理器
        self.step_manager = StepManager()
        self.step_manager.register_trackable('messages', self.context_manager)
        self.step_manager.register_trackable('runner', self.runner)
        self.step_manager.register_trackable('blocks', self.code_blocks)

        # 初始化事件记录器
        enable_replay = self.settings.get('enable_replay_recording', True)
        if enable_replay:
            self.event_recorder = EventRecorder(enabled=True)
            # 注册事件记录器到步骤管理器
            self.step_manager.register_trackable('events', self.event_recorder)
        else:
            self.event_recorder = None

        self.init_plugins()
    
    def emit(self, event_name: str, **kwargs):
        """重写broadcast方法以记录事件"""
        # 记录事件到事件记录器
        if self.event_recorder:
            self.event_recorder.record_event(event_name, kwargs.copy())
        
        # 调用父类的broadcast方法
        super().emit(event_name, **kwargs)

    def restore_state(self, task_data):
        """从任务状态加载任务
        
        Args:
            task_data: 任务状态数据（字典格式）或 TaskState 对象
            
        Returns:
            Task: 加载的任务对象
        """
        # 支持传入字典或 TaskState 对象
        if isinstance(task_data, dict):
            task_state = TaskState.from_dict(task_data)
        elif isinstance(task_data, TaskState):
            task_state = task_data
        else:
            raise TastStateError('Invalid task_data type, expected dict or TaskState')
        
        # 使用 TaskState 恢复状态
        task_state.restore_to_task(self)

    def get_status(self):
        return {
            'llm': self.client.name,
            'blocks': len(self.code_blocks),
            'steps': len(self.step_manager),
        }

    def init_plugins(self):
        """初始化插件"""
        plugin_manager = self.context.plugin_manager
        for plugin_name, plugin_data in self.role.plugins.items():
            plugin = plugin_manager.get_plugin(plugin_name, plugin_data)
            if not plugin:
                self.log.warning(f"Plugin {plugin_name} not found")
                continue
            self.add_listener(plugin)
            
        # 注册显示效果插件
        if self.context.display_manager:
            self.display = self.context.display_manager.get_current_plugin()
            self.add_listener(self.display)

    def to_record(self):
        TaskRecord = namedtuple('TaskRecord', ['task_id', 'start_time', 'done_time', 'instruction'])
        start_time = datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S') if self.start_time else '-'
        done_time = datetime.fromtimestamp(self.done_time).strftime('%H:%M:%S') if self.done_time else '-'
        return TaskRecord(
            task_id=self.task_id,
            start_time=start_time,
            done_time=done_time,
            instruction=self.instruction[:32] if self.instruction else '-'
        )
    
    def use(self, name):
        ret = self.client.use(name)
        return ret
        
    def save(self, path):
        self.display.save(path, clear=False, code_format=CONSOLE_WHITE_HTML)

    def save_html(self, path, task):
        if 'chats' in task and isinstance(task['chats'], list) and len(task['chats']) > 0:
            if task['chats'][0]['role'] == 'system':
                task['chats'].pop(0)

        task_json = json.dumps(task, ensure_ascii=False, default=str)
        html_content = CONSOLE_CODE_HTML.replace('{{code}}', task_json)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            self.log.exception('Error saving html')
            self.emit('exception', msg='save_html', exception=e)
        
    def _auto_save(self):
        """自动保存任务状态"""
        # 如果任务目录不存在，则不保存
        if not self.cwd.exists():
            self.log.warning('Task directory not found, skipping save')
            return
        
        try:
            # 创建 TaskState 对象并保存
            task_state = TaskState(self)
            task_state.save_to_file(self.cwd / "task.json")
            
            # 保存 HTML 控制台
            filename = self.cwd / "console.html"
            self.save(filename)
            
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
        self.emit('task_end', path=newname)
        self.context.diagnose.report_code_error(self.runner.history)
        if self.settings.get('share_result'):
            self.sync_to_cloud()
        
    def process_reply(self, markdown):
        ret = self.code_blocks.parse(markdown, parse_mcp=self.mcp)
        self.emit('parse_reply', result=ret)
        if not ret:
            return None

        if 'call_tool' in ret:
            return self.process_mcp_reply(ret['call_tool'])

        errors = ret.get('errors')
        if errors:
            prompt = self.prompts.get_parse_error_prompt(errors)
            ret = self.chat(prompt)
        elif 'exec_blocks' in ret:
            ret = self.process_code_reply(ret['exec_blocks'])
        else:
            ret = None
        return ret

    def process_code_reply(self, exec_blocks):
        results = OrderedDict()
        for block in exec_blocks:
            self.emit('exec', block=block)
            result = self.runner(block)
            results[block.name] = result
            self.emit('exec_result', result=result, block=block)

        msg = self.prompts.get_results_prompt(results)
        return self.chat(msg)

    def process_mcp_reply(self, json_content):
        """处理 MCP 工具调用的回复"""
        block = {'content': json_content, 'language': 'json'}
        self.emit('mcp_call', block=block)

        call_tool = json.loads(json_content)
        result = self.mcp.call_tool(call_tool['name'], call_tool.get('arguments', {}))
        code_block = CodeBlock(
            code=json_content,
            lang='json',
            name=call_tool.get('name', 'MCP Tool Call'),
            version=1,
        )
        self.emit('mcp_result', block=code_block, result=result)
        msg = self.prompts.get_mcp_result_prompt(result)
        return self.chat(msg)

    def _get_summary(self, detail=False):
        data = {}
        context_manager = self.context_manager
        if detail:
            data['usages'] = context_manager.get_usage()

        summary = context_manager.get_summary()
        summary['elapsed_time'] = time.time() - self.start_time
        summarys = "| {rounds} | {time:.3f}s/{elapsed_time:.3f}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        data['summary'] = summarys
        return data

    def chat(self, context: LLMContext, *, system_prompt=None):
        self.emit('query_start')
        msg = self.client(context, system_prompt=system_prompt)
        self.emit('response_complete', llm=self.client.name, msg=msg)
        return msg.content if msg else None

    def _get_system_prompt(self):
        params = {}
        if self.mcp:
            params['mcp_tools'] = self.mcp.get_tools_prompt()
        params['util_functions'] = self.runtime.get_function_list()
        params['tool_functions'] = {}
        params['role'] = self.role
        return self.prompts.get_default_prompt(**params)
    
    def run(self, instruction: str):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        instruction: 用户输入的字符串（可包含@file等多模态标记）
        """
        mmc = MMContent(instruction, base_path=self.context.cwd)
        try:
            content = mmc.content
        except Exception as e:
            raise TaskInputError(T("Invalid input"), e) from e

        if not self.client.has_capability(content):
            raise TaskInputError(T("Current model does not support this content"))

        user_prompt = content
        if not self.start_time:
            self.start_time = time.time()
            self.instruction = instruction
            # 开始事件记录
            self.event_recorder.start_recording()
            if isinstance(content, str):
                user_prompt = self.prompts.get_task_prompt(content, gui=self.gui)
            system_prompt = self._get_system_prompt()
            self.emit('task_start', instruction=instruction, task_id=self.task_id)
        else:
            system_prompt = None
            if isinstance(content, str):
                user_prompt = self.prompts.get_chat_prompt(content, self.instruction)
            # 记录轮次开始事件
            self.emit('round_start', instruction=instruction, step=len(self.step_manager) + 1)

        self.cwd.mkdir(exist_ok=True)
        os.chdir(self.cwd)

        rounds = 1
        max_rounds = self.max_rounds
        self.saved = False
        
        response = self.chat(user_prompt, system_prompt=system_prompt)
        if not response:
            self.log.error('No response from LLM')
            # 使用新的步骤管理器记录失败的步骤
            self.step_manager.create_checkpoint(instruction, 0, '')
            return
        
        while rounds <= max_rounds:
            prev_response = response
            response = self.process_reply(response)
            rounds += 1
            if self.is_stopped():
                self.log.info('Task stopped')
                break
            if not response:
                response = prev_response
                break

        # 使用新的步骤管理器记录步骤
        self.step_manager.create_checkpoint(instruction, rounds, response)
        summary = self._get_summary()
        self.emit('round_end', summary=summary, response=response)
        self._auto_save()
        self.log.info('Round done', rounds=rounds)

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
