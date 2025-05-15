#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path
import json
from .i18n import T
from .task import Task
from .llm import LLM
from .runner import Runner
from .plugin import PluginManager
from .prompt import SYSTEM_PROMPT
from .diagnose import Diagnose
from .config import PLUGINS_DIR, get_mcp

class TaskManager:
    def __init__(self, settings, console):
        self.settings = settings
        self.console = console
        self.task = None
        self.envs = {}
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
        self._init_api()
        self._init_mcp()
        self.diagnose = Diagnose.create(settings)
        self.runner = Runner(settings, console, envs=self.envs)
        self.llm = LLM(settings, console, system_prompt=self.system_prompt)


    @property
    def workdir(self):
        return str(self._cwd)

    def get_update(self, force=False):
        return self.diagnose.check_update(force)
    
    @property
    def busy(self):
        return self.task is not None

    def use(self, name):
        ret = self.llm.use(name)
        self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')
        return ret

    def done(self):
        if not self.task:
            return
        
        self.diagnose.report_code_error(self.runner.history)
        self.task.done()
        self.task = None

    def save(self, path):
        if self.task:  
            self.task.save(path)

    def _init_environ(self):
        envs = self.settings.get('environ', {})
        for name, value in envs.items():
            os.environ[name] = value

    def _init_api(self):
        api = self.settings.get('api')
        if not api:
            return
        lines = [self.system_prompt]
        for api_name, api_conf in api.items():
            lines.append(f"## {api_name} API")
            desc = api_conf.get('desc')
            if desc: 
                lines.append(f"### API {T('description')}\n{desc}")

            envs = api_conf.get('env')
            if not envs:
                continue

            lines.append(f"### {T('env_description')}")
            for name, (value, desc) in envs.items():
                value = value.strip()
                if not value:
                    continue
                lines.append(f"- {name}: {desc}")
                self.envs[name] = (value, desc)

        self.system_prompt = "\n".join(lines)

    def _init_mcp(self):
        """初始化 MCP 工具提示信息"""
        mcp_tools = self.mcp.list_tools()
        if not mcp_tools:
            return
        
        tools_json = json.dumps(mcp_tools, ensure_ascii=False)
        lines = [self.system_prompt]
        lines.append("""\n# 工具调用
你是一个能够使用外部工具来辅助用户完成任务的智能助手，请判断是否需要使用外部工具来回答用户的问题。如果需要调用工具，请以 JSON 格式输出你的决策和调用参数，并且仅返回json，不输出其他内容，格式如下：
{"action": "call_tool", "name": "tool_name", "arguments": {"arg_name": "arg_value", ...}}
如果不需要使用工具，请直接回复用户。
以下是你可用的工具，以 JSON 数组形式提供：
""")
        lines.append(f"```json\n{tools_json}\n```")
        # 更新系统提示
        self.system_prompt = "\n".join(lines)

    def new_task(self, instruction, llm=None, max_rounds=None, system_prompt=None):
        if llm and not self.llm.use(llm):
            return None
        
        system_prompt = system_prompt or self.system_prompt
        max_rounds = max_rounds or self.settings.get('max_rounds')
        task = Task(instruction, system_prompt=system_prompt, max_rounds=max_rounds, settings=self.settings, mcp=self.mcp)
        task.console = self.console
        task.llm = self.llm
        task.runner = self.runner
        self.task = task
        return task
    
    def __call__(self, instruction, llm=None, max_rounds=None, system_prompt=None):
        if self.task:
            self.task.run(instruction=instruction, llm=llm, max_rounds=max_rounds)
        else:
            task = self.new_task(instruction, llm=llm, max_rounds=max_rounds, system_prompt=system_prompt)
            self.task = task
            task.run()
