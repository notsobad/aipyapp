"""重构后的命令管理器 - 职责分离"""

import shlex
import argparse
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from prompt_toolkit.completion import Completer, Completion
from loguru import logger

from .base_refactored import Command, CommandMode
from ..completer.base import CompleterBase, CompleterContext


@dataclass
class CommandContext:
    """命令执行上下文"""
    task: Any = None
    tm: Any = None
    console: Any = None
    mode: CommandMode = CommandMode.MAIN
    
    def is_task_mode(self) -> bool:
        return self.mode == CommandMode.TASK
    
    def is_main_mode(self) -> bool:
        return self.mode == CommandMode.MAIN


class CommandRegistry:
    """
    命令注册表
    
    负责命令的注册和查找
    """
    
    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self.aliases: Dict[str, str] = {}  # 别名 -> 命令名
        self.commands_by_mode: Dict[CommandMode, List[Command]] = {
            CommandMode.MAIN: [],
            CommandMode.TASK: []
        }
    
    def register(self, command: Command):
        """注册命令"""
        # 注册主名称
        self.commands[command.name] = command
        
        # 注册别名
        if hasattr(command.meta, 'aliases'):
            for alias in command.meta.aliases:
                self.aliases[alias] = command.name
        
        # 按模式分类
        for mode in command.modes:
            self.commands_by_mode[mode].append(command)
    
    def unregister(self, name: str):
        """注销命令"""
        if name in self.commands:
            command = self.commands[name]
            del self.commands[name]
            
            # 移除别名
            for alias, cmd_name in list(self.aliases.items()):
                if cmd_name == name:
                    del self.aliases[alias]
            
            # 从模式列表中移除
            for mode in command.modes:
                if command in self.commands_by_mode[mode]:
                    self.commands_by_mode[mode].remove(command)
    
    def get(self, name: str) -> Optional[Command]:
        """获取命令"""
        # 先检查直接名称
        if name in self.commands:
            return self.commands[name]
        
        # 再检查别名
        if name in self.aliases:
            return self.commands.get(self.aliases[name])
        
        return None
    
    def get_by_mode(self, mode: CommandMode) -> List[Command]:
        """获取特定模式的命令"""
        return self.commands_by_mode.get(mode, [])
    
    def list_all(self) -> List[Command]:
        """列出所有命令"""
        return list(self.commands.values())


class CommandExecutor:
    """
    命令执行器
    
    负责解析和执行命令
    """
    
    def __init__(self, registry: CommandRegistry):
        self.registry = registry
        self.log = logger.bind(src="CommandExecutor")
    
    def execute(self, text: str, context: CommandContext) -> Any:
        """
        执行命令
        
        Args:
            text: 命令文本（带 / 前缀）
            context: 执行上下文
            
        Returns:
            命令执行结果
        """
        # 验证命令格式
        if not text.startswith('/'):
            raise ValueError(f"Invalid command format: {text}")
        
        # 解析命令
        text = text[1:].strip()
        if not text:
            raise ValueError("Empty command")
        
        # 分割命令和参数
        try:
            words = shlex.split(text)
        except ValueError as e:
            raise ValueError(f"Failed to parse command: {e}")
        
        if not words:
            raise ValueError("No command specified")
        
        cmd_name = words[0]
        cmd_args = words[1:]
        
        # 查找命令
        command = self.registry.get(cmd_name)
        if not command:
            raise ValueError(f"Unknown command: {cmd_name}")
        
        # 检查命令是否支持当前模式
        if context.mode not in command.modes:
            raise ValueError(f"Command '{cmd_name}' not available in {context.mode.value} mode")
        
        # 解析参数
        try:
            parsed_args = command.parser.parse_args(cmd_args)
        except SystemExit:
            # argparse 尝试退出，转换为异常
            raise ValueError(f"Invalid arguments for command '{cmd_name}'")
        except Exception as e:
            raise ValueError(f"Failed to parse arguments: {e}")
        
        # 验证参数
        if hasattr(command, 'validate_args'):
            error = command.validate_args(parsed_args)
            if error:
                raise ValueError(f"Invalid arguments: {error}")
        
        # 执行命令
        try:
            return command.execute(parsed_args, context)
        except Exception as e:
            self.log.error(f"Command execution failed: {e}")
            raise


class CommandCompleter(CompleterBase):
    """
    命令级别的补齐器
    
    负责路由补齐请求到具体命令的补齐器
    """
    
    def __init__(self, registry: CommandRegistry, context_provider=None):
        self.registry = registry
        self.context_provider = context_provider  # 用于获取当前执行上下文
    
    def get_completions(self, context: CompleterContext) -> List[Completion]:
        """获取补齐建议"""
        text = context.word_before_cursor
        
        # 解析命令名
        try:
            words = shlex.split(text)
        except ValueError:
            # 引号不匹配等情况，尝试简单分割
            words = text.split()
        
        if not words:
            # 补齐所有命令名
            return self._complete_command_names("", context)
        
        cmd_name = words[0]
        
        # 如果还在输入命令名
        if len(words) == 1 and not context.is_empty_position:
            return self._complete_command_names(cmd_name, context)
        
        # 查找命令
        command = self.registry.get(cmd_name)
        if not command:
            return []
        
        # 获取命令的补齐器
        completer = command.get_completer()
        
        # 创建命令参数的上下文（去掉命令名）
        remaining_text = text[len(cmd_name):].lstrip()
        arg_context = CompleterContext(
            text=remaining_text,
            cursor_pos=len(remaining_text),
            words=words[1:],
            current_word=words[-1] if len(words) > 1 and not context.is_empty_position else "",
            word_before_cursor=remaining_text
        )
        
        return completer.get_completions(arg_context)
    
    def _complete_command_names(self, partial: str, context: CompleterContext) -> List[Completion]:
        """补齐命令名"""
        completions = []
        
        # 获取当前模式
        current_mode = CommandMode.MAIN  # 默认模式
        if self.context_provider and hasattr(self.context_provider, 'mode'):
            current_mode = self.context_provider.mode
        
        # 获取当前模式的命令
        commands = self.registry.get_by_mode(current_mode)
        for command in commands:
            if command.name.startswith(partial):
                completions.append(Completion(
                    command.name,
                    start_position=-len(partial) if partial else 0,
                    display=command.name,
                    display_meta=command.description
                ))
        
        return completions


class CommandManager(Completer):
    """
    重构后的命令管理器
    
    职责：
    1. 作为顶层接口，协调各组件
    2. 管理命令注册表
    3. 提供执行入口
    4. 作为 prompt_toolkit 的 Completer
    
    不负责：
    - 具体的补齐逻辑（委托给 CommandCompleter）
    - 具体的执行逻辑（委托给 CommandExecutor）
    - 命令的实现（由 Command 子类负责）
    """
    
    def __init__(self, initial_context: Optional[CommandContext] = None):
        self.context = initial_context or CommandContext()
        self.registry = CommandRegistry()
        self.executor = CommandExecutor(self.registry)
        self.completer = CommandCompleter(self.registry, self.context)  # 传递 context 以获取当前模式
        self.log = logger.bind(src="CommandManager")
    
    def register(self, command: Command):
        """注册命令"""
        self.registry.register(command)
        self.log.info(f"Registered command: {command.name}")
    
    def unregister(self, name: str):
        """注销命令"""
        self.registry.unregister(name)
        self.log.info(f"Unregistered command: {name}")
    
    def execute(self, text: str) -> Any:
        """
        执行命令
        
        Args:
            text: 命令文本（带 / 前缀）
            
        Returns:
            命令执行结果
        """
        return self.executor.execute(text, self.context)
    
    def get_completions(self, document, complete_event):
        """
        prompt_toolkit Completer 接口
        
        将补齐请求路由到命令补齐器
        """
        text = document.text_before_cursor
        
        # 只处理以 / 开头的命令
        if not text.startswith('/'):
            return
        
        # 去掉 / 前缀
        text = text[1:]
        
        # 创建补齐上下文
        try:
            words = shlex.split(text)
        except ValueError:
            words = text.split()
        
        current_word = ""
        if words and not text.endswith(' '):
            current_word = words[-1]
        
        context = CompleterContext(
            text=text,
            cursor_pos=len(text),
            words=words,
            current_word=current_word,
            word_before_cursor=text
        )
        
        # 获取补齐建议
        completions = self.completer.get_completions(context)
        
        # 转换为 prompt_toolkit 的 Completion
        for completion in completions:
            yield completion
    
    def set_mode(self, mode: CommandMode):
        """设置命令模式"""
        self.context.mode = mode
        self.log.info(f"Switched to {mode.value} mode")
    
    def set_task(self, task: Any):
        """设置任务上下文"""
        self.context.task = task
        if task:
            self.set_mode(CommandMode.TASK)
        else:
            self.set_mode(CommandMode.MAIN)
    
    def get_commands_for_current_mode(self) -> List[Command]:
        """获取当前模式下可用的命令"""
        return self.registry.get_by_mode(self.context.mode)
    
    def get_command(self, name: str) -> Optional[Command]:
        """获取指定命令"""
        return self.registry.get(name)