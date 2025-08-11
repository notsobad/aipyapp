"""适配器模块 - 用于兼容现有命令（简化版）"""

import argparse
from typing import Any, Optional

from .base_refactored_v2 import Command, CommandMode
from .base import BaseCommand, CommandMode as LegacyCommandMode, Completable
from .base_parser import ParserCommand
from ..completer.base import CompleterBase, CompleterContext, create_completion
from ..completer.argparse_completer import ArgparseCompleter, ArgumentInfo
from prompt_toolkit.completion import Completion
import shlex


class LegacyCommandAdapter(Command):
    """
    适配器 - 将旧命令适配到新架构（简化版）
    
    支持：
    - BaseCommand 子类
    - ParserCommand 子类
    """
    
    def __init__(self, legacy_command: BaseCommand):
        """
        Args:
            legacy_command: 旧命令实例
        """
        self.legacy = legacy_command
        
        # 转换旧的 CommandMode 到新的 CommandMode
        legacy_modes = getattr(legacy_command, 'modes', [LegacyCommandMode.MAIN])
        converted_modes = []
        for mode in legacy_modes:
            if isinstance(mode, LegacyCommandMode):
                # 转换旧的枚举值到新的
                if mode == LegacyCommandMode.MAIN:
                    converted_modes.append(CommandMode.MAIN)
                elif mode == LegacyCommandMode.TASK:
                    converted_modes.append(CommandMode.TASK)
            else:
                # 已经是新的 CommandMode
                converted_modes.append(mode)
        
        # 直接初始化父类，不再需要 CommandMeta
        super().__init__(
            name=legacy_command.name,
            description=getattr(legacy_command, 'description', ''),
            modes=converted_modes
        )
        
        # 如果旧命令是 ParserCommand，确保它已初始化
        if isinstance(legacy_command, ParserCommand) and not legacy_command.parser:
            legacy_command.init()
    
    def create_parser(self) -> argparse.ArgumentParser:
        """从旧命令获取 parser"""
        if isinstance(self.legacy, ParserCommand):
            # ParserCommand 有 parser 属性
            if not self.legacy.parser:
                self.legacy.init()
            return self.legacy.parser
        else:
            # 基础 BaseCommand，创建简单 parser
            parser = argparse.ArgumentParser(
                prog=self.name,
                description=self.description,
                exit_on_error=False
            )
            return parser
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        """执行旧命令"""
        # 旧命令的 execute 方法签名可能不同
        if isinstance(self.legacy, ParserCommand):
            # ParserCommand.execute(args)
            return self.legacy.execute(args)
        else:
            # BaseCommand.execute(args, context)
            return self.legacy.execute(args, context)
    
    def get_completer(self) -> CompleterBase:
        """获取补齐器"""
        # 如果旧命令有自定义补齐逻辑，适配它
        if isinstance(self.legacy, ParserCommand):
            return LegacyParserCommandCompleter(self.legacy)
        else:
            # 使用默认的 argparse 补齐器
            return ArgparseCompleter(self.parser)


# EnhancedArgparseCompleter 和 LegacyParserCommandCompleter 保持不变
class EnhancedArgparseCompleter(ArgparseCompleter):
    """
    增强的 Argparse 补齐器 - 支持动态值
    
    通过调用旧命令的 get_arg_values 方法获取动态补齐值
    """
    
    def __init__(self, parser: argparse.ArgumentParser, legacy_command: ParserCommand):
        self.legacy_command = legacy_command
        self._current_subcommand = None  # 保存当前子命令
        super().__init__(parser)  # 调用父类构造函数，会调用 _analyze_parser
    
    def _analyze_parser(self):
        """重写分析方法，确保子命令也使用 EnhancedArgparseCompleter"""
        # 先调用父类方法进行基础分析
        super()._analyze_parser()
        
        # 替换子命令补齐器为增强版本
        if self.has_subcommands:
            for action in self.parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, subparser in action.choices.items():
                        # 使用增强补齐器替换普通补齐器
                        self.subparsers[name] = EnhancedArgparseCompleter(subparser, self.legacy_command)
    
    def _complete_option_value(self, option_info: ArgumentInfo, context: CompleterContext) -> list[Completion]:
        """补齐选项值 - 增强版本支持动态值"""
        # 先尝试获取动态值
        dynamic_completions = self._get_dynamic_values(option_info, context)
        if dynamic_completions:
            return dynamic_completions
        
        # 回退到基类实现
        return super()._complete_option_value(option_info, context)
    
    def _complete_positional(self, arg_info: ArgumentInfo, context: CompleterContext) -> list[Completion]:
        """补齐位置参数 - 增强版本支持动态值"""
        # 对于子命令的参数，总是尝试获取动态值
        # 因为 "use" 后面的 "provider" 是位置参数
        dynamic_completions = self._get_dynamic_values_for_positional(arg_info, context)
        if dynamic_completions:
            return dynamic_completions
        
        # 回退到基类实现
        return super()._complete_positional(arg_info, context)
    
    def _get_dynamic_values_for_positional(self, arg_info: ArgumentInfo, context: CompleterContext) -> list[Completion]:
        """专门为位置参数获取动态值"""
        if not hasattr(self.legacy_command, 'get_arg_values'):
            return []
        
        try:
            # 通过 parser 的 prog 属性推断子命令
            # 例如 prog='/llm use' 表示这是 use 子命令
            subcommand = None
            if hasattr(self.parser, 'prog'):
                prog_parts = self.parser.prog.split()
                if len(prog_parts) > 1:
                    # 最后一部分是子命令名
                    subcommand = prog_parts[-1]
            
            # 创建参数适配器
            class ArgAdapter:
                def __init__(self, arg_info):
                    self.name = arg_info.dest
                    self.desc = arg_info.help or ""
                
                def get(self, key, default=None):
                    if key == 'choices':
                        return arg_info.choices
                    return default
            
            arg = ArgAdapter(arg_info)
            partial_value = context.current_word if not context.is_empty_position else ""
            
            # 调用 get_arg_values
            values = self.legacy_command.get_arg_values(arg, subcommand, partial_value)
            
            if not values:
                return []
            
            # 转换为 Completion
            from .base import Completable
            completions = []
            for value in values:
                if isinstance(value, Completable):
                    text = value.name
                    desc = str(value.desc) if value.desc else ""
                else:
                    text = str(value)
                    desc = ""
                
                if text.startswith(partial_value):
                    completions.append(create_completion(
                        text,
                        start_position=-len(partial_value) if partial_value else 0,
                        display_meta=desc
                    ))
            
            return completions
            
        except Exception as e:
            return []
    
    def _get_dynamic_values(self, arg_info: ArgumentInfo, context: CompleterContext) -> list[Completion]:
        """通过调用 get_arg_values 获取动态值"""
        if not hasattr(self.legacy_command, 'get_arg_values'):
            return []
        
        try:
            # 解析当前输入以确定子命令
            words = context.words if hasattr(context, 'words') and context.words else []
            if not words and context.word_before_cursor:
                try:
                    words = shlex.split(context.word_before_cursor)
                except:
                    words = context.word_before_cursor.split()
            
            subcommand = None
            
            # 查找子命令（如果有）
            if self.has_subcommands and len(words) > 0:
                # 第一个非选项词可能是子命令
                for word in words:
                    if not word.startswith('-') and word in self.subparsers:
                        subcommand = word
                        break
            
            # 创建一个模拟的 Completable 对象作为参数
            class ArgAdapter:
                def __init__(self, arg_info):
                    self.name = arg_info.dest
                    self.desc = arg_info.help or ""
                
                def get(self, key, default=None):
                    if key == 'choices':
                        return arg_info.choices
                    return default
            
            arg = ArgAdapter(arg_info)
            partial_value = context.current_word if not context.is_empty_position else ""
            
            # 调用旧命令的 get_arg_values
            values = self.legacy_command.get_arg_values(arg, subcommand, partial_value)
            
            if not values:
                return []
            
            # 转换为 Completion 对象
            completions = []
            for value in values:
                if isinstance(value, Completable):
                    # 是 Completable 对象
                    text = value.name
                    desc = value.desc or ""
                else:
                    # 是普通字符串
                    text = str(value)
                    desc = ""
                
                if text.startswith(partial_value):
                    completions.append(create_completion(
                        text,
                        start_position=-len(partial_value) if partial_value else 0,
                        display_meta=desc
                    ))
            
            return completions
            
        except Exception as e:
            # 忽略错误，返回空列表
            return []


class LegacyParserCommandCompleter(CompleterBase):
    """
    旧 ParserCommand 补齐器适配器
    
    将旧的补齐逻辑适配到新的 CompleterBase 接口
    """
    
    def __init__(self, legacy_command: ParserCommand):
        self.legacy = legacy_command
        # 创建增强的 argparse 补齐器，带动态值支持
        self.argparse_completer = EnhancedArgparseCompleter(
            legacy_command.parser, 
            legacy_command
        )
    
    def get_completions(self, context: CompleterContext) -> list[Completion]:
        """获取补齐建议"""
        # 使用增强的补齐器（包含动态值支持）
        return self.argparse_completer.get_completions(context)