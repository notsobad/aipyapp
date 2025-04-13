#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from .i18n import T
from .task import Task
from .llm import LLM
from .runner import Runner

class TaskManager:
    def __init__(self, settings, console):
        self.settings = settings
        self.console = console
        self.task = None
        self.envs = {}
        self.config_files = settings._loaded_files
        self.system_prompt = settings.get('system_prompt')
        if settings.workdir:
            workdir = Path.cwd() / settings.workdir
            workdir.mkdir(parents=True, exist_ok=True)
            os.chdir(workdir)
            self._cwd = workdir
        else:
            self._cwd = Path.cwd()
        self._init_api()
        self.runner = Runner(settings, console, envs=self.envs)
        self.llm = LLM(settings, console, system_prompt=self.system_prompt)

    def use(self, name):
        ret = self.llm.use(name)
        self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')

    def done(self):
        if self.task:
            self.task.done()
            self.task = None

    def save(self, path):
        if self.task:  
            self.task.save(path)

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

    def new_task(self, instruction, llm=None, max_rounds=None, system_prompt=None):
        if llm and not self.llm.use(llm):
            return None
        
        system_prompt = system_prompt or self.system_prompt
        max_rounds = max_rounds or self.settings.get('max_rounds')
        task = Task(instruction, system_prompt=system_prompt, max_rounds=max_rounds)
        task.console = self.console
        task.llm = self.llm
        task.runner = self.runner
        return task
    
    def __call__(self, instruction, llm=None, max_rounds=None, system_prompt=None):
        if self.task:
            self.task.run(instruction=instruction, llm=llm, max_rounds=max_rounds)
        else:
            task = self.new_task(instruction, llm=llm, max_rounds=max_rounds, system_prompt=system_prompt)
            self.task = task
            task.run()
