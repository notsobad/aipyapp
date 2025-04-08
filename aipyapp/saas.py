#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
import importlib.resources as resources

from dynaconf import Dynaconf
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from .aipy import Agent
from .aipy.i18n import T
from .aipy.config import ConfigManager
__PACKAGE_NAME__ = "aipyapp"

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

    def run_ai_task(self, task):
        try:
            self.ai(task)
        except Exception as e:
            self.console.print(f"[bold red]Error: {e}")

    def run_ai_mode(self, initial_text):
        ai = self.ai
        self.console.print(f"{T('ai_mode_enter')}", style="cyan")
        self.run_ai_task(initial_text)
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
                    self.console.print(f"{T('ai_mode_unknown_command')}", style="cyan")
            else:
                self.run_ai_task(user_input)
        try:
            ai.publish(verbose=False)
        except Exception as e:
            pass
        try:
            ai.done()
        except Exception as e:
            self.console.print_exception()
            pass
        self.console.print(f"{T('ai_mode_exit')}", style="cyan")

    def run(self):
        names = self.ai.llm.names
        self.console.print(f"{T('banner1')}", style="green")
        self.console.print(f"[cyan]{T('default')}: [green]{names['default']}，[cyan]{T('available')}: [yellow]{' '.join(names['available'])}")
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
    console.print("[bold cyan]🚀 Python use - AIPython ([red]Task mode[/red])")

    path = args.config if args.config else 'aipython.toml'
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    conf = ConfigManager(default_config_path, path)
    conf.check_config()
    settings = conf.get_config()

    try:
        ai = Agent(settings, console=console)
    except Exception as e:
        console.print_exception(e)
        console.print(f"[bold red]Error: {e}")
        return
    
    if not ai.llm:
        console.print(f"[bold red]{T('no_available_llm')}")
        return
  
    InteractiveConsole(ai, console, settings).run()
