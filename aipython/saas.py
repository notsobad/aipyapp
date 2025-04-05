#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import uuid
from pathlib import Path
import importlib.resources as resources

from dynaconf import Dynaconf
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from .aipy import Agent

__PACKAGE_NAME__ = "aipython"

class InteractiveConsole():
    def __init__(self, ai, console, settings):
        self.ai = ai
        self.history = FileHistory(str(Path.cwd() / settings.history))
        self.session = PromptSession(history=self.history)
        self.console = console
        self.style_main = Style.from_dict({"prompt": "green"})
        self.style_ai = Style.from_dict({"prompt": "cyan"})

    def input_with_possible_multiline(self, prompt_text, is_ai=False):
        prompt_style = self.style_ai if is_ai else self.style_main

        first_line = self.session.prompt([("class:prompt", prompt_text)], style=prompt_style)
        if not first_line.endswith("\\"):
            return first_line
        # Multi-line input
        lines = [first_line.rstrip("\\")]
        while True:
            next_line = self.session.prompt([("class:prompt", "... ")], style=prompt_style)
            if next_line.endswith("\\"):
                lines.append(next_line.rstrip("\\"))
            else:
                lines.append(next_line)
                break
        return "\n".join(lines)

    def run_ai_mode(self, initial_text):
        ai = self.ai
        self.console.print("[进入 AI 模式，开始处理任务，输入 Ctrl+d 或 /done 结束任务]", style="cyan")
        ai(initial_text)
        while True:
            try:
                user_input = self.input_with_possible_multiline(">>> ", is_ai=True).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue

            if user_input.startswith("/"):
                if user_input.startswith("/done"):
                    break
                elif user_input.startswith("/use "):
                    llm = user_input[5:].strip()
                    if llm: ai.use(llm)
                else:
                    self.console.print("[AI 模式] 未知命令", style="cyan")
            else:
                ai(user_input)
        try:
            ai.publish(verbose=False)
        except Exception as e:
            self.console.print(f"[AI 模式] 发布失败: {e}")
            pass
        try:
            ai.save(f'{uuid.uuid4().hex}.html')
        except Exception as e:
            pass
        ai.clear()
        self.console.print("[退出 AI 模式]", style="cyan")

    def run(self):
        self.console.print("请输入需要 AI 处理的任务 (输入 /use llm 切换 LLM)", style="green")
        while True:
            try:
                user_input = self.input_with_possible_multiline(">> ").strip()
                if len(user_input) < 2:
                    continue
                if user_input.startswith("/use "):
                    llm = user_input[5:].strip()
                    if llm: self.ai.use(llm)
                else:
                    self.run_ai_mode(user_input)
            except (EOFError, KeyboardInterrupt):
                break

def main(args):
    console = Console(record=True)
    console.print("[bold cyan]🚀 Python use - AIPython ([red]SaaS mode[/red])")

    path = args.config if args.config else 'aipython.toml'
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    settings = Dynaconf(settings_files=[str(default_config_path), path], envvar_prefix="AIPY", merge_enabled=True)
    try:
        ai = Agent(settings, console=console)
    except Exception as e:
        console.print_exception(e)
        console.print(f"[bold red]Error: {e}")
        return
    
    os.chdir(Path.cwd() / settings.workdir)
    InteractiveConsole(ai, console, settings).run()
