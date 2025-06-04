#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
from collections import deque

from loguru import logger

from .. import T
from .task import Task
from .plugin import PluginManager
from .prompt import SYSTEM_PROMPT
from .diagnose import Diagnose
from .llm import ClientManager
from .config import PLUGINS_DIR, get_mcp, get_tt_api_key, get_tt_aio_api

class TaskManager:
    MAX_TASKS = 16

    def __init__(self, settings, console, gui=False):
        self.settings = settings
        self.console = console
        self.tasks = deque(maxlen=self.MAX_TASKS)
        self.envs = {}
        self.gui = gui
        self.log = logger.bind(src='taskmgr')
        self.config_files = settings._loaded_files
        self.system_prompt = f"{settings.system_prompt}\n{SYSTEM_PROMPT}"
        self.plugin_manager = PluginManager(PLUGINS_DIR)
        self.plugin_manager.load_plugins()
        if settings.workdir:
            workdir = Path.cwd() / settings.workdir
            workdir.mkdir(parents=True, exist_ok=True)
            os.chdir(workdir)
            self._cwd = workdir
        else:
            self._cwd = Path.cwd()
        self.mcp = get_mcp(settings.get('_config_dir'))
        self._init_environ()
        self.tt_api_key = get_tt_api_key(settings)
        self._init_api()
        self.diagnose = Diagnose.create(settings)
        self.client_manager = ClientManager(settings)

    @property
    def workdir(self):
        return str(self._cwd)

    def get_update(self, force=False):
        return self.diagnose.check_update(force)

    def use(self, name):
        ret = self.client_manager.use(name)
        self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')
        return ret

    def _init_environ(self):
        envs = self.settings.get('environ', {})
        for name, value in envs.items():
            os.environ[name] = value

    def _init_api(self):
        api = self.settings.get('api', {})

        # update tt aio api, for map and search
        if self.tt_api_key:
            tt_aio_api = get_tt_aio_api(self.tt_api_key)
            api.update(tt_aio_api)

        lines = [self.system_prompt]
        for api_name, api_conf in api.items():
            lines.append(f"## {api_name} API")
            desc = api_conf.get('desc')
            if desc:
                lines.append(f"### API {T('Description')}\n{desc}")

            envs = api_conf.get('env')
            if not envs:
                continue

            lines.append(f"### {T('Environment variable name and meaning')}")
            for name, (value, desc) in envs.items():
                value = value.strip()
                if not value:
                    continue
                lines.append(f"- {name}: {desc}")
                self.envs[name] = (value, desc)

        self.system_prompt = "\n".join(lines)


    def _update_mcp_prompt(self, prompt):
        """更新 MCP 工具提示信息"""
        mcp_tools = self.mcp.list_tools()
        if not mcp_tools:
            return prompt
        tools_json = json.dumps(mcp_tools, ensure_ascii=False)
        lines = [self.system_prompt]
        lines.append("""\n## MCP工具调用规则：
1. 如果需要调用MCP工具，请以 JSON 格式输出你的决策和调用参数，并且仅返回json，不输出其他内容。
2. 返回 JSON 格式如下：
{"action": "call_tool", "name": "tool_name", "arguments": {"arg_name": "arg_value", ...}}
3. 一次只能返回一个工具，即只能返回一个 JSON 代码块，不能有其它多余内容。
以下是你可用的工具，以 JSON 数组形式提供：
""")
        lines.append(f"```json\n{tools_json}\n```")
        # 更新系统提示
        return "\n".join(lines)

    def new_task(self, system_prompt=None):
        with_mcp = self.settings.get('mcp', {}).get('enable', True)
        system_prompt = system_prompt or self.system_prompt
        if self.mcp and with_mcp:
            self.log.info('Update MCP prompt')
            system_prompt = self._update_mcp_prompt(system_prompt)

        task = Task(self)
        task.client = self.client_manager.Client()
        task.diagnose = self.diagnose
        task.system_prompt = system_prompt
        task.mcp = self.mcp if with_mcp else None
        self.tasks.append(task)
        self.log.info('New task created', task_id=task.task_id)
        return task