"""
新版命令管理器 - 基于重构架构
渐进式迁移：先创建新版本，逐步替换旧版本
"""

from typing import Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from prompt_toolkit.completion import Completer

from aipyapp import __pkgpath__
from .manager_refactored import CommandManager as NewCommandManager, CommandContext
from .adapter import LegacyCommandAdapter
from .base_refactored import CommandMode

# 导入现有命令
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
from .cmd_plugin import Command as PluginCommand
from .cmd_custom import CustomCommand
from .custom_command_manager import CustomCommandManager
from .markdown_command import MarkdownCommand

# 导入必要的异常和结果类
from .manager import CommandError, CommandInputError, CommandArgumentError, InvalidCommandError
from .result import CommandResult, TaskModeResult

# 内置命令列表
BUILTIN_COMMANDS = [
    InfoCommand, LLMCommand, RoleCommand, DisplayCommand, PluginCommand, StepsCommand,
    BlockCommand, ContextCommand, TaskCommand, MCPCommand, HelpCommand, CustomCommand,
]


class CommandManagerV2(Completer):
    """
    新版命令管理器 - 向后兼容的包装器
    
    提供与旧版相同的接口，内部使用新架构
    """
    
    def __init__(self, settings, tm, console):
        """保持与旧版相同的构造函数签名"""
        self.settings = settings
        self.tm = tm
        self.console = console
        self.task = None
        self.mode = CommandMode.MAIN
        self.log = logger.bind(src="CommandManagerV2")
        
        # 创建命令上下文
        context = CommandContext(
            task=self.task,
            tm=tm,
            console=console,
            mode=self.mode
        )
        
        # 创建新的命令管理器
        self._new_manager = NewCommandManager(context)
        
        # 自定义命令管理器
        self.custom_command_manager = CustomCommandManager()
        self.custom_command_manager.add_command_dir(Path(__pkgpath__ / "commands" ))
        self.custom_command_manager.add_command_dir(Path(settings['config_dir']) / "commands")
        
        # 初始化命令
        self._init_commands()
        
        # 创建键绑定（兼容旧版）
        self.key_bindings = self.create_key_bindings()
    
    def _init_commands(self):
        """初始化所有命令"""
        # 注册内置命令
        for command_class in BUILTIN_COMMANDS:
            try:
                # 创建旧命令实例
                old_cmd = command_class(self)
                
                # 使用适配器包装
                adapted_cmd = LegacyCommandAdapter(old_cmd)
                
                # 注册到新管理器
                self._new_manager.register(adapted_cmd)
                
                self.log.debug(f"Registered builtin command: {adapted_cmd.name}")
            except Exception as e:
                self.log.error(f"Failed to register command {command_class.__name__}: {e}")
        
        # 注册自定义命令
        self._load_custom_commands()
    
    def _load_custom_commands(self):
        """加载自定义命令"""
        try:
            custom_commands = self.custom_command_manager.scan_commands()
            
            for custom_cmd in custom_commands:
                # 设置管理器引用
                custom_cmd.manager = self
                
                # 自定义命令通常是 MarkdownCommand 实例
                if isinstance(custom_cmd, MarkdownCommand):
                    # MarkdownCommand 已经继承自 ParserCommand
                    adapted_cmd = LegacyCommandAdapter(custom_cmd)
                    self._new_manager.register(adapted_cmd)
                    self.log.debug(f"Registered custom command: {adapted_cmd.name}")
            
            self.log.info(f"Loaded {len(custom_commands)} custom commands")
            
        except Exception as e:
            self.log.error(f"Failed to load custom commands: {e}")
    
    @property
    def context(self):
        """获取命令上下文（兼容旧版）"""
        return self._new_manager.context
    
    @property
    def commands(self):
        """获取当前模式的命令（兼容旧版）"""
        commands_dict = {}
        current_mode = self._new_manager.context.mode
        
        # 获取当前模式下可用的命令
        for cmd in self._new_manager.registry.list_all():
            # 检查命令是否支持当前模式
            if current_mode in cmd.modes:
                # 对于适配的命令，返回原始的旧命令对象以保持兼容
                if isinstance(cmd, LegacyCommandAdapter):
                    commands_dict[cmd.name] = cmd.legacy
                else:
                    commands_dict[cmd.name] = cmd
        
        return commands_dict
    
    @property
    def commands_main(self):
        """获取主模式命令（兼容旧版）"""
        commands_dict = {}
        for cmd in self._new_manager.registry.get_by_mode(CommandMode.MAIN):
            # 对于适配的命令，返回原始的旧命令对象
            if isinstance(cmd, LegacyCommandAdapter):
                commands_dict[cmd.name] = cmd.legacy
            else:
                commands_dict[cmd.name] = cmd
        return commands_dict
    
    @property
    def commands_task(self):
        """获取任务模式命令（兼容旧版）"""
        commands_dict = {}
        for cmd in self._new_manager.registry.get_by_mode(CommandMode.TASK):
            # 对于适配的命令，返回原始的旧命令对象
            if isinstance(cmd, LegacyCommandAdapter):
                commands_dict[cmd.name] = cmd.legacy
            else:
                commands_dict[cmd.name] = cmd
        return commands_dict
    
    def is_task_mode(self):
        """检查是否在任务模式（兼容旧版）"""
        return self._new_manager.context.is_task_mode()
    
    def is_main_mode(self):
        """检查是否在主模式（兼容旧版）"""
        return self._new_manager.context.is_main_mode()
    
    def set_task_mode(self, task):
        """设置任务模式（兼容旧版）"""
        self.task = task
        self.mode = CommandMode.TASK
        self._new_manager.context.task = task
        self._new_manager.context.mode = CommandMode.TASK
        self._new_manager.set_task(task)
    
    def set_main_mode(self):
        """设置主模式（兼容旧版）"""
        self.task = None
        self.mode = CommandMode.MAIN
        self._new_manager.context.task = None
        self._new_manager.context.mode = CommandMode.MAIN
        self._new_manager.set_mode(CommandMode.MAIN)
    
    def execute(self, user_input: str) -> CommandResult:
        """
        执行命令（兼容旧版）
        
        保持与旧版相同的异常类型
        """
        if not user_input.startswith('/'):
            raise CommandInputError(user_input)
        
        try:
            # 使用新管理器执行
            result = self._new_manager.execute(user_input)
            
            # 包装结果以保持兼容性
            if isinstance(result, CommandResult):
                return result
            elif isinstance(result, TaskModeResult):
                return result
            else:
                # 从执行结果构造 CommandResult
                import shlex
                args = shlex.split(user_input[1:])
                command_name = args[0] if args else ""
                
                return CommandResult(
                    command=command_name,
                    subcommand=None,
                    args={},
                    result=result
                )
                
        except ValueError as e:
            # 转换异常类型以保持兼容性
            error_msg = str(e)
            if "Unknown command" in error_msg:
                command_name = error_msg.split(": ")[-1] if ": " in error_msg else ""
                raise InvalidCommandError(command_name)
            elif "Invalid arguments" in error_msg:
                raise CommandArgumentError(error_msg)
            else:
                raise CommandError(error_msg)
        except Exception as e:
            raise CommandError(str(e))
    
    def get_completions(self, document, complete_event):
        """
        获取自动补齐（兼容旧版）
        
        直接委托给新管理器
        """
        return self._new_manager.get_completions(document, complete_event)
    
    def reload_custom_commands(self):
        """重新加载自定义命令（兼容旧版）"""
        # 先从新管理器中移除所有自定义命令
        for cmd_name in list(self._new_manager.registry.commands.keys()):
            cmd = self._new_manager.registry.commands[cmd_name]
            # 检查是否是自定义命令（通过是否有 file_path 属性判断）
            if hasattr(cmd, 'legacy') and hasattr(cmd.legacy, 'file_path'):
                self._new_manager.unregister(cmd_name)
        
        # 重新加载
        self._load_custom_commands()
        
        return len(self.custom_command_manager.get_all_commands())
    
    def create_key_bindings(self):
        """创建键绑定（兼容旧版）"""
        from prompt_toolkit.key_binding import KeyBindings
        
        kb = KeyBindings()
        
        @kb.add('@')
        def _(event):
            """按 @ 插入符号并进入文件补齐模式"""
            buffer = event.app.current_buffer
            buffer.insert_text('@')
            
            # 创建文件补齐器
            from ..completer.specialized import PathCompleter
            from ..completer.base import CompleterContext, PrefixCompleter
            
            # 使用新的路径补齐器
            path_completer = PrefixCompleter('@', PathCompleter())
            
            # 临时切换到文件补齐器
            class TempCompleter(Completer):
                def get_completions(self, document, complete_event):
                    text = document.text_before_cursor
                    context = CompleterContext(
                        text=text,
                        cursor_pos=len(text),
                        words=text.split(),
                        current_word=text.split()[-1] if text.split() else "",
                        word_before_cursor=text
                    )
                    return path_completer.get_completions(context)
            
            buffer.completer = TempCompleter()
            buffer.start_completion()
        
        @kb.add('c-f')
        def _(event):
            """按 Ctrl+F 直接进入文件补齐模式"""
            buffer = event.app.current_buffer
            
            from ..completer.specialized import PathCompleter
            from ..completer.base import CompleterContext
            
            path_completer = PathCompleter()
            
            class TempCompleter(Completer):
                def get_completions(self, document, complete_event):
                    text = document.text_before_cursor
                    context = CompleterContext(
                        text=text,
                        cursor_pos=len(text),
                        words=text.split(),
                        current_word=text.split()[-1] if text.split() else "",
                        word_before_cursor=text
                    )
                    return path_completer.get_completions(context)
            
            buffer.completer = TempCompleter()
            buffer.start_completion()
        
        @kb.add('escape', eager=True)
        def _(event):
            """按ESC恢复默认补齐模式"""
            buffer = event.app.current_buffer
            buffer.completer = self
            if buffer.complete_state:
                buffer.cancel_completion()
        
        @kb.add('c-t')
        def _(event):
            """按Ctrl+T插入当前时间戳"""
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            event.app.current_buffer.insert_text(timestamp)
        
        return kb