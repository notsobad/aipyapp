import shlex
import argparse
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .base import BaseCommand, CommandMode
from .cmd_info import InfoCommand
from .cmd_help import HelpCommand
from .cmd_llm import LLMCommand
from .cmd_use import UseCommand
from .cmd_env import EnvCommand
from .cmd_task import TaskCommand
from .cmd_mcp import MCPCommand
from .cmd_tools import ToolsCommand
from .cmd_display import DisplayCommand
from .cmd_context import ContextCommand

from loguru import logger
from rich import print
from prompt_toolkit.completion import Completer, Completion

COMMANDS = [
    InfoCommand, UseCommand, EnvCommand, LLMCommand, ContextCommand,
    TaskCommand, MCPCommand, ToolsCommand, DisplayCommand, HelpCommand
]

@dataclass
class CommandContext:
    """命令执行上下文"""
    task: Any = None
    tm: Any = None
    console: Any = None

class CommandManager(Completer):
    def __init__(self, tm, console):
        self.tm = tm
        self.task = None
        self.console = console
        self.mode = CommandMode.MAIN
        self.commands_main = OrderedDict()
        self.commands_task = OrderedDict()
        self.commands = self.commands_main
        self.log = logger.bind(src="CommandManager")
        self.init()
        
    @property
    def context(self):
        return CommandContext(task=self.task, tm=self.tm, console=self.console)
    
    def init(self):
        """Initialize all registered commands"""
        commands = []
        for command_class in COMMANDS:
            command = command_class(self)
            self.register_command(command)
            commands.append(command)
        
        for command in commands:
            command.init()
        self.log.info(f"Initialized {len(commands)} commands")

    def is_task_mode(self):
        return self.mode == CommandMode.TASK
    
    def is_main_mode(self):
        return self.mode == CommandMode.MAIN
    
    def set_task_mode(self, task):
        self.task = task
        self.mode = CommandMode.TASK
        self.commands = self.commands_task

    def set_main_mode(self):
        self.mode = CommandMode.MAIN
        self.task = None
        self.commands = self.commands_main

    def register_command(self, command):
        """Register a command instance"""
        if not isinstance(command, BaseCommand):
            raise ValueError("Command must be an instance of BaseCommand")
        
        if CommandMode.MAIN in command.modes:
            self.commands_main[command.name] = command
        if CommandMode.TASK in command.modes:
            self.commands_task[command.name] = command
            
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith('/'):
            return

        text = text[1:]
        try:
            words = shlex.split(text)
        except ValueError as e:
            self.log.error(f"输入解析错误: {e}")
            return
        
        # 提取公共补全函数
        def complete_items(items, partial, start_pos=None):
            start_pos = -len(partial) if start_pos is None else start_pos
            for item in items:
                if item.name.startswith(partial):
                    yield Completion(
                        item.name,
                        start_position=start_pos,
                        display_meta=item.desc
                    )

        if len(words) == 0 or (len(words) == 1 and not text.endswith(' ')):
            # 补全主命令
            partial_cmd = words[0] if len(words) > 0 else ''
            yield from complete_items(self.commands.values(), partial_cmd)
            return

        cmd = words[0]
        if cmd not in self.commands:
            return

        command_instance = self.commands[cmd]
        subcommands = command_instance.subcommands

        # 补全子命令
        if subcommands:
            if len(words) == 1 or (len(words) == 2 and not text.endswith(' ')):
                partial_subcmd = words[1] if len(words) > 1 else ''
                yield from complete_items(subcommands.values(), partial_subcmd)
                return

            subcmd = words[1]
            if subcmd not in subcommands:
                return
            arguments = subcommands[subcmd]['arguments']
        else:
            subcmd = None
            arguments = command_instance.arguments

        if text.endswith(' '):
            # 检查上一个词是否是选项参数
            if len(words) > 1:
                last_word = words[-2]  # 最后一个词是空格，所以上一个词是 -2
                if last_word.startswith('-'):
                    # 如果上一个词是选项参数，显示该选项参数的补齐选项
                    arg = arguments.get(last_word, None)
                    if arg and arg['requires_value']:
                        choices = command_instance.get_arg_values(arg, subcmd)
                        if choices:
                            yield from complete_items(choices, '')
                            return
                        # 如果没有通过 get_arg_values 获取到选项，尝试使用 arg 的 choices
                        if 'choices' in arg and arg['choices']:
                            # choices 是一个 OrderedDict，需要提取键名
                            choice_names = list(arg['choices'].keys())
                            for choice_name in choice_names:
                                yield Completion(choice_name, start_position=0, display_meta=f"Strategy: {choice_name}")
                            return
                    # 如果选项参数不需要值，不显示任何补齐选项
                    return
            # 检查最后一个词是否是选项参数（当用户输入以空格结尾时）
            if len(words) > 0:
                last_word = words[-1]
                if last_word.startswith('-'):
                    # 如果最后一个词是选项参数，显示该选项参数的补齐选项
                    arg = arguments.get(last_word, None)
                    if arg and arg['requires_value']:
                        choices = command_instance.get_arg_values(arg, subcmd)
                        if choices:
                            yield from complete_items(choices, '')
                            return
                        # 如果没有通过 get_arg_values 获取到选项，尝试使用 arg 的 choices
                        if 'choices' in arg and arg['choices']:
                            # choices 是一个 OrderedDict，需要提取键名
                            choice_names = list(arg['choices'].keys())
                            for choice_name in choice_names:
                                yield Completion(choice_name, start_position=0, display_meta=f"Strategy: {choice_name}")
                            return
                    # 如果选项参数不需要值，不显示任何补齐选项
                    return
            
            # 当以空格结尾时，检查是否有位置参数需要值
            for arg_name, arg in arguments.items():
                # 只处理位置参数（不以 -- 或 - 开头）且需要值的情况
                if not arg_name.startswith('-') and arg['requires_value']:
                    choices = command_instance.get_arg_values(arg, subcmd)
                    if choices:
                        yield from complete_items(choices, '')
                        return
            # 如果没有位置参数需要值，显示所有可用的参数
            yield from complete_items(arguments.values(), '')
            return
        else:
            partial_arg = words[-1]
            last_word = words[-2]

            # 检查当前输入是否是选项参数
            if partial_arg.startswith('-'):
                # 如果当前输入是选项参数，显示该选项参数的补齐选项
                arg = arguments.get(partial_arg, None)
                if arg and arg.get('requires_value'):
                    choices = command_instance.get_arg_values(arg, subcmd)
                    if choices:
                        yield from complete_items(choices, '')
                        return
                    # 如果没有通过 get_arg_values 获取到选项，尝试使用 arg 的 choices
                    if 'choices' in arg and arg['choices']:
                        # choices 是一个 OrderedDict，需要提取键名
                        choice_names = list(arg['choices'].keys())
                        for choice_name in choice_names:
                            yield Completion(choice_name, start_position=-len(partial_arg), display_meta=f"Strategy: {choice_name}")
                        return

            # 检查上一个词是否是选项参数
            arg = arguments.get(last_word, None)
            if arg and arg['requires_value']:
                choices = command_instance.get_arg_values(arg, subcmd)
                if choices:
                    yield from complete_items(choices, partial_arg)
                return

        yield from complete_items(arguments.values(), partial_arg)

    def execute(self, user_input):
        """Execute a command"""
        if not user_input.startswith('/'):
            return
        
        user_input = user_input[1:].strip()
        if not user_input:
            return
        
        args = shlex.split(user_input)
        command = args[0]
        if command not in self.commands:
            print(f"Unknown command: {command}")
            return
        
        command_instance = self.commands[command]
        parser = command_instance.parser
        try:
            # Parse remaining arguments (excluding the command name)
            parsed_args = parser.parse_args(args[1:])
            parsed_args.raw_args = args[1:]
            command_instance.execute(parsed_args)
        except SystemExit:
            pass
        except argparse.ArgumentError as e:
            print(f"Argument error: {e}")
        except Exception as e:
            print(f"Error: {e}")