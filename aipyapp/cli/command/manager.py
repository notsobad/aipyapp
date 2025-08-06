import shlex
import argparse
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .base import BaseCommand, CommandMode
from .cmd_info import InfoCommand
from .cmd_help import HelpCommand
from .cmd_llm import LLMCommand
from .cmd_role import RoleCommand
from .cmd_task import TaskCommand
from .cmd_mcp import MCPCommand
from .cmd_display import DisplayCommand
from .cmd_context import ContextCommand
from .cmd_steps import StepsCommand
from .cmd_block import BlockCommand

from loguru import logger
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from pathlib import Path

COMMANDS = [
    InfoCommand, LLMCommand, RoleCommand, DisplayCommand, StepsCommand, 
    BlockCommand, ContextCommand, TaskCommand, MCPCommand, HelpCommand
]

@dataclass
class CommandContext:
    """命令执行上下文"""
    task: Any = None
    tm: Any = None
    console: Any = None

class CommandError(Exception):
    """Command error"""
    pass

class CommandInputError(CommandError):
    """Command input error"""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class InvalidCommandError(CommandError):
    """Invalid command error"""
    def __init__(self, command):
        self.command = command
        super().__init__(f"Invalid command: {command}")

class InvalidSubcommandError(CommandError):
    """Invalid subcommand error"""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

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
    
    def create_key_bindings(self):
        """创建键绑定"""
        kb = KeyBindings()
        
        @kb.add('c-f')  # Ctrl+F: 开启文件补齐模式
        def _(event):
            """按Ctrl+F进入文件补齐模式"""
            buffer = event.app.current_buffer
            
            # 插入@符号
            buffer.insert_text('@')
            
            # 创建专门处理@文件引用的补齐器
            file_completer = self._create_file_reference_completer()
            
            # 临时切换到文件引用补齐器
            buffer.completer = file_completer
            
            # 触发补齐
            buffer.start_completion()
            
        @kb.add('escape', eager=True)  # ESC: 恢复默认补齐模式
        def _(event):
            """按ESC恢复默认补齐模式"""
            buffer = event.app.current_buffer
            
            # 直接恢复到CommandManager作为补齐器
            buffer.completer = self
            
            # 关闭当前的补齐窗口
            if buffer.complete_state:
                buffer.cancel_completion()
            
        @kb.add('c-t')  # Ctrl+T: 插入当前时间戳
        def _(event):
            """按Ctrl+T插入当前时间戳"""
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            event.app.current_buffer.insert_text(timestamp)
        
        return kb
    
    def _create_file_reference_completer(self):
        """创建文件引用补齐器"""
        import shlex
        import os
        
        class FileReferenceCompleter(Completer):
            def get_completions(self, document, complete_event):
                # 获取光标前的文本
                text_before_cursor = document.text_before_cursor
                
                # 找到最后一个@符号的位置
                at_pos = text_before_cursor.rfind('@')
                if at_pos == -1:
                    return
                
                # 获取@后面的部分作为搜索前缀
                raw_path = text_before_cursor[at_pos + 1:]
                
                # 处理可能包含引号的路径输入
                try:
                    # 尝试解析引号，如果失败则使用原始输入
                    unquoted_path = shlex.split(raw_path)[0] if raw_path else ''
                except ValueError:
                    # 如果引号不匹配，使用原始输入
                    unquoted_path = raw_path
                
                # 确定搜索目录和文件前缀
                if not unquoted_path or not os.path.isabs(unquoted_path):
                    search_dir = Path.cwd()
                    if unquoted_path:
                        if os.sep in unquoted_path:
                            search_dir = search_dir / os.path.dirname(unquoted_path)
                            search_prefix = os.path.basename(unquoted_path)
                        else:
                            search_prefix = unquoted_path
                    else:
                        search_prefix = ''
                else:
                    search_dir = Path(os.path.dirname(unquoted_path))
                    search_prefix = os.path.basename(unquoted_path)
                
                # 搜索匹配的文件
                try:
                    if search_dir.exists() and search_dir.is_dir():
                        for item in search_dir.iterdir():
                            if item.name.startswith(search_prefix):
                                # 计算需要补全的部分
                                remaining = item.name[len(search_prefix):]
                                if remaining:
                                    # 处理包含空格的文件名
                                    if ' ' in item.name:
                                        # 如果文件名包含空格，用引号包装完整的文件名
                                        quoted_name = shlex.quote(item.name)
                                        # 计算需要替换的部分：从search_prefix开始到文件名结尾
                                        if search_prefix:
                                            # 替换从search_prefix开始的部分
                                            completion_text = quoted_name[len(search_prefix):]
                                        else:
                                            completion_text = quoted_name
                                    else:
                                        completion_text = remaining
                                    
                                    display_text = item.name
                                    if item.is_dir():
                                        display_text += "/"
                                    
                                    yield Completion(completion_text, display=display_text)
                except (OSError, PermissionError):
                    pass
        
        return FileReferenceCompleter()

    def register_command(self, command):
        """Register a command instance"""
        if not isinstance(command, BaseCommand):
            raise ValueError("Command must be an instance of BaseCommand")
        
        if CommandMode.MAIN in command.modes:
            self.commands_main[command.name] = command
        if CommandMode.TASK in command.modes:
            self.commands_task[command.name] = command
            
    def get_completions(self, document, complete_event):
        """获取自动补齐选项"""
        text = document.text_before_cursor
        if not text.startswith('/'):
            return

        text = text[1:]
        try:
            words = shlex.split(text)
        except ValueError as e:
            self.log.error(f"输入解析错误: {e}")
            return

        # 处理主命令补齐
        if self._should_complete_main_command(words, text):
            yield from self._complete_main_commands(words)
            return

        # 获取命令实例和参数
        command_instance, arguments, subcmd = self._get_command_and_arguments(words)
        if not command_instance:
            return

        # 处理子命令补齐
        if self._should_complete_subcommand(words, text, command_instance):
            yield from self._complete_subcommands(words, command_instance)
            return

        # 处理参数补齐
        if arguments is None:
            # 当没有参数时（如只有主命令），不进行参数补齐
            return
        if text.endswith(' '):
            yield from self._complete_after_space(words, arguments, command_instance, subcmd)
        else:
            yield from self._complete_partial_input(words, arguments, command_instance, subcmd)

    def _should_complete_main_command(self, words, text):
        """判断是否应该补齐主命令"""
        return len(words) == 0 or (len(words) == 1 and not text.endswith(' '))

    def _complete_main_commands(self, words):
        """补齐主命令"""
        partial_cmd = words[0] if len(words) > 0 else ''
        yield from self._complete_items(self.commands.values(), partial_cmd)

    def _should_complete_subcommand(self, words, text, command_instance):
        """判断是否应该补齐子命令"""
        return (command_instance.subcommands and 
                (len(words) == 1 or (len(words) == 2 and not text.endswith(' '))))

    def _complete_subcommands(self, words, command_instance):
        """补齐子命令"""
        partial_subcmd = words[1] if len(words) > 1 else ''
        yield from self._complete_items(command_instance.subcommands.values(), partial_subcmd)

    def _get_command_and_arguments(self, words):
        """获取命令实例和参数"""
        cmd = words[0]
        if cmd not in self.commands:
            return None, None, None

        command_instance = self.commands[cmd]
        subcommands = command_instance.subcommands

        if subcommands:
            if len(words) < 2:
                # 当只有主命令时，返回命令实例但不设置子命令和参数
                return command_instance, None, None
            subcmd = words[1]
            if subcmd not in subcommands:
                return None, None, None
            arguments = subcommands[subcmd]['arguments']
        else:
            subcmd = None
            arguments = command_instance.arguments

        return command_instance, arguments, subcmd

    def _complete_after_space(self, words, arguments, command_instance, subcmd):
        """处理以空格结尾的补齐"""
        # 检查选项参数
        for word in [words[-2] if len(words) > 1 else None, words[-1] if len(words) > 0 else None]:
            if word and word.startswith('-'):
                yield from self._complete_option_argument(word, arguments, command_instance, subcmd, start_position=0)
                return

        # 检查位置参数
        for arg_name, arg in arguments.items():
            if not arg_name.startswith('-') and arg['requires_value']:
                choices = command_instance.get_arg_values(arg, subcmd, '')
                if choices:
                    yield from self._complete_items(choices, '')
                    return

        # 显示所有可用参数
        yield from self._complete_items(arguments.values(), '')

    def _complete_partial_input(self, words, arguments, command_instance, subcmd):
        """处理部分输入的补齐"""
        partial_arg = words[-1]
        last_word = words[-2] if len(words) > 1 else None

        # 检查当前输入是否是选项参数
        if partial_arg.startswith('-'):
            yield from self._complete_option_argument(partial_arg, arguments, command_instance, subcmd, 
                                                     start_position=-len(partial_arg))
            return

        # 检查上一个词是否是选项参数
        if last_word and last_word.startswith('-'):
            arg = arguments.get(last_word, None)
            if arg and arg['requires_value']:
                choices = command_instance.get_arg_values(arg, subcmd, partial_arg)
                if choices:
                    yield from self._complete_items(choices, partial_arg)
                return

        # 检查是否是位置参数的输入
        for arg_name, arg in arguments.items():
            if not arg_name.startswith('-') and arg['requires_value']:
                choices = command_instance.get_arg_values(arg, subcmd, partial_arg)
                if choices:
                    yield from self._complete_items(choices, partial_arg)
                    return
        
        # 显示所有可用参数
        yield from self._complete_items(arguments.values(), partial_arg)

    def _complete_option_argument(self, option_name, arguments, command_instance, subcmd, start_position):
        """补齐选项参数"""
        arg = arguments.get(option_name, None)
        if not arg or not arg.get('requires_value'):
            return

        # 尝试通过 get_arg_values 获取选项
        choices = command_instance.get_arg_values(arg, subcmd, '')
        if choices:
            yield from self._complete_items(choices, '')
            return

        # 尝试使用 arg 的 choices
        if 'choices' in arg and arg['choices']:
            choice_names = list(arg['choices'].keys())
            for choice_name in choice_names:
                yield Completion(choice_name, start_position=start_position, 
                               display_meta=f"Option: {choice_name}")

    def _complete_items(self, items, partial, start_pos=None):
        """通用的补齐函数"""
        start_pos = -len(partial) if start_pos is None else start_pos
        for item in items:
            if item.name.startswith(partial):
                yield Completion(
                    item.name,
                    start_position=start_pos,
                    display_meta=item.desc
                )

    def execute(self, user_input: str) -> dict[str, Any]:
        """Execute a command"""
        if not user_input.startswith('/'):
            raise CommandInputError(user_input)
        
        user_input = user_input[1:].strip()
        if not user_input:
            raise CommandInputError(user_input)
        
        args = shlex.split(user_input)
        command = args[0]
        if command not in self.commands:
            raise InvalidCommandError(command)
        
        command_instance = self.commands[command]
        parser = command_instance.parser
        ret = None
        try:
            # Parse remaining arguments (excluding the command name)
            parsed_args = parser.parse_args(args[1:])
            parsed_args.raw_args = args[1:]
            ret = command_instance.execute(parsed_args)
        except SystemExit as e:
            raise CommandError(f"SystemExit: {e}")
        except argparse.ArgumentError as e:
            raise CommandInputError(user_input) from e
        except Exception as e:
            raise CommandError(f"Error: {e}") from e
        
        return {
            'command': command,
            'subcommand': getattr(parsed_args, 'subcommand', None),
            'args': parsed_args,
            'ret': ret,
        }