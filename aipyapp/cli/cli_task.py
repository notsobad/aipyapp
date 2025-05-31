#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from enum import Enum, auto
from collections import OrderedDict

from rich import print
from rich.console import Console
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter

from ..aipy import TaskManager, ConfigManager, CONFIG_DIR
from .. import T, set_lang, __version__
from ..config import LLMConfig
from ..aipy.wizard import config_llm

class CommandType(Enum):
    CMD_DONE = auto()
    CMD_USE = auto()
    CMD_EXIT = auto()
    CMD_INVALID = auto()
    CMD_TEXT = auto()
    CMD_INFO = auto()
    CMD_MCP = auto()

def parse_command(input_str, llms=set()):
    lower = input_str.lower()

    if lower in ("/done", "done"):
        return CommandType.CMD_DONE, None
    if lower in ("/info", "info"):
        return CommandType.CMD_INFO, None
    if lower in ("/exit", "exit"):
        return CommandType.CMD_EXIT, None
    if lower in llms:
        return CommandType.CMD_USE, input_str
    
    if lower.startswith("/use "):
        arg = input_str[5:].strip()
        if arg in llms:
            return CommandType.CMD_USE, arg
        else:
            return CommandType.CMD_INVALID, arg

    if lower.startswith("use "):
        arg = input_str[4:].strip()
        if arg in llms:
            return CommandType.CMD_USE, arg
    
    if lower.startswith("/mcp"):
        args = input_str[4:].strip().split(" ")
        return CommandType.CMD_MCP, args
               
    return CommandType.CMD_TEXT, input_str

def show_info(info):
    info['Python'] = sys.executable
    info['Python version'] = sys.version
    info['Base Prefix'] = sys.base_prefix
    table = Table(title=T("System information"), show_lines=True)

    table.add_column("参数", justify="center", style="bold cyan", no_wrap=True)
    table.add_column("值", justify="right", style="bold magenta")

    for key, value in info.items():
        table.add_row(
            key,
            value,
        )
    print(table)

def process_mcp_ret(console, arg, ret):
    if ret.get("status", "success") == "success":
        #console.print(f"[green]{T('mcp_success')}: {ret.get('message', '')}[/green]")
        mcp_status = 'enabled' if ret.get("globally_enabled") else 'disabled'
        console.print(f"[green]{T('MCP server status: {}').format(T(mcp_status))}[/green]")
        mcp_servers = ret.get("servers", [])
        if mcp_status == 'enabled':
            for server_name, info in mcp_servers.items():
                server_status = 'enabled' if info.get("enabled", False) else 'disabled'
                console.print(
                    "[", T(server_status), "]",
                    server_name, info.get("tools_count"), "tools"
                )
    else:
        #console.print(f"[red]{T('mcp_error')}: {ret.get('message', '')}[/red]")
        console.print("操作失败", ret.get("message", ''))

class InteractiveConsole():
    def __init__(self, tm, console, settings):
        self.tm = tm
        self.names = tm.client_manager.names
        completer = WordCompleter(['/use', 'use', '/done','done', '/info', 'info', '/mcp'] + list(self.names['enabled']), ignore_case=True)
        self.history = FileHistory(str(CONFIG_DIR / ".history"))
        self.session = PromptSession(history=self.history, completer=completer)
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

    def run_task(self, task, instruction):
        try:
            task.run(instruction)
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception as e:
            self.console.print_exception()

    def start_task_mode(self, task, instruction):
        self.console.print(f"{T('Enter AI mode, start processing tasks, enter Ctrl+d or /done to end the task')}", style="cyan")
        self.run_task(task, instruction)
        while True:
            try:
                user_input = self.input_with_possible_multiline(">>> ", is_ai=True).strip()
                if len(user_input) < 2: continue
            except (EOFError, KeyboardInterrupt):
                break

            cmd, arg = parse_command(user_input, self.names['enabled'])
            if cmd == CommandType.CMD_TEXT:
                self.run_task(task, arg)
            elif cmd == CommandType.CMD_DONE:
                break
            elif cmd == CommandType.CMD_USE:
                ret = task.use(arg)
                self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')
            elif cmd == CommandType.CMD_INVALID:
                self.console.print(f'[red]Error: {arg}[/red]')

        try:
            task.done()
        except Exception as e:
            self.console.print_exception()
        self.console.print(f"[{T('Exit AI mode')}]", style="cyan")

    def info(self):
        info = OrderedDict()
        info['Config dir'] = str(CONFIG_DIR)
        info['Work dir'] = str(self.tm.workdir)
        info['Current LLM'] = repr(self.tm.client_manager.current)
        show_info(info)

    def run(self):
        self.console.print(f"{T('Please enter the task to be processed by AI (enter /use <following LLM> to switch, enter /info to view system information)')}", style="green")
        self.console.print(f"[cyan]{T('Default')}: [green]{self.names['default']}，[cyan]{T('Enabled')}: [yellow]{' '.join(self.names['enabled'])}")
        self.info()
        tm = self.tm
        while True:
            try:
                user_input = self.input_with_possible_multiline(">> ").strip()
                if len(user_input) < 2:
                    continue

                cmd, arg = parse_command(user_input, self.names['enabled'])
                if cmd == CommandType.CMD_TEXT:
                    task = tm.new_task()
                    self.start_task_mode(task, arg)
                elif cmd == CommandType.CMD_USE:
                    ret = tm.client_manager.use(arg)
                    self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')
                elif cmd == CommandType.CMD_INFO:
                    self.info()
                elif cmd == CommandType.CMD_EXIT:
                    break
                elif cmd == CommandType.CMD_MCP:
                    if tm.mcp:
                        ret = tm.mcp.process_command(arg)
                        process_mcp_ret(self.console, arg, ret)
                    else:
                        self.console.print("MCP config not found")
                elif cmd == CommandType.CMD_INVALID:
                    self.console.print('[red]Error[/red]')
            except (EOFError, KeyboardInterrupt):
                break

def main(args):
    console = Console(record=True)
    console.print(f"[bold cyan]🚀 Python use - AIPython ({__version__}) [[green]https://aipy.app[/green]]")
    conf = ConfigManager(args.config_dir)
    settings = conf.get_config()
    lang = settings.get('lang')
    if lang: set_lang(lang)
    llm_config = LLMConfig(CONFIG_DIR / "config")
    if conf.check_config(gui=True) == 'TrustToken':
        if llm_config.need_config():
            console.print(f"[yellow]{T('Starting LLM Provider Configuration Wizard')}[/yellow]")
            try:
                config = config_llm(llm_config)
            except KeyboardInterrupt:
                console.print(f"[yellow]{T('User cancelled configuration')}[/yellow]")
                return
            if not config:
                return
        settings["llm"] = llm_config.config

    if args.fetch_config:
        conf.fetch_config()
        return

    settings.gui = False
    settings.debug = args.debug
    
    try:
        tm = TaskManager(settings, console=console)
    except Exception as e:
        console.print_exception()
        return

    update = tm.get_update()
    if update and update.get('has_update'):
        console.print(f"[bold red]🔔 号外❗ {T('Update available')}: {update.get('latest_version')}")
   
    if not tm.client_manager:
        console.print(f"[bold red]{T('No available LLM, please check the configuration file')}")
        return
    
    if args.cmd:
        tm.new_task().run(args.cmd)
        return
    InteractiveConsole(tm, console, settings).run()
