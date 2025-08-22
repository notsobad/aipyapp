"""基于 argparse 的补齐器"""

import argparse
import shlex
from typing import List, Optional, Dict, Set, Callable, Tuple, Protocol
from prompt_toolkit.completion import Completion

from loguru import logger

from .base import CompleterBase, CompleterContext, create_completion
from .specialized import PathCompleter


class HasParser(Protocol):
    @property
    def parser(self) -> argparse.ArgumentParser:
        ...

    def get_arg_values(self, name: str, subcommand: Optional[str]=None, partial: Optional[str]=None) -> Optional[List[Tuple[str, str]]]:
        ... 

class ArgumentInfo:
    """参数信息封装"""
    
    def __init__(self, action: argparse.Action):
        self.action = action
        self.dest = action.dest
        self.option_strings = action.option_strings
        self.choices = action.choices
        self.type = action.type
        self.help = action.help
        self.nargs = action.nargs
        self.required = action.required if hasattr(action, 'required') else False
        self.is_flag = isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction))
        
    @property
    def is_option(self) -> bool:
        """是否是选项参数"""
        return bool(self.option_strings)
    
    @property
    def is_positional(self) -> bool:
        """是否是位置参数"""
        return not self.is_option and self.dest not in ('help', 'subcommand')
    
    @property
    def requires_value(self) -> bool:
        """是否需要值"""
        if self.is_flag:
            return False
        if self.is_positional:
            return True
        return self.type is not None or self.nargs is not None or self.choices is not None


class ParsedArguments:
    """已解析的参数状态"""
    
    def __init__(self):
        self.options_with_values: Dict[str, str] = {}  # 已提供值的选项
        self.flags: Set[str] = set()  # 已使用的标志
        self.positionals: List[str] = []  # 已提供的位置参数
        self.subcommand: Optional[str] = None  # 已选择的子命令
        self.pending_option: Optional[str] = None  # 等待值的选项
    
    def add_option_value(self, option: str, value: str):
        """添加选项值"""
        self.options_with_values[option] = value
        self.pending_option = None
    
    def add_flag(self, flag: str):
        """添加标志"""
        self.flags.add(flag)
        self.pending_option = None
    
    def add_positional(self, value: str):
        """添加位置参数"""
        self.positionals.append(value)
    
    def set_pending_option(self, option: str):
        """设置等待值的选项"""
        self.pending_option = option
    
    def is_option_used(self, option: str) -> bool:
        """检查选项是否已使用"""
        return option in self.options_with_values or option in self.flags


class ArgparseCompleter(CompleterBase):
    """基于 argparse.ArgumentParser 的补齐器"""
    
    def __init__(self, command: HasParser, parser: argparse.ArgumentParser=None):
        self.command = command
        self.parser = parser or command.parser
        self.log = logger.bind(src='ArgparseCompleter', name=self.command.name)
        self._analyze_parser()
    
    def _analyze_parser(self):
        """分析 parser 结构"""
        self.arguments: List[ArgumentInfo] = []
        self.options: Dict[str, ArgumentInfo] = {}
        self.positionals: List[ArgumentInfo] = []
        self.subparsers: Dict[str, 'ArgparseCompleter'] = {}
        self.has_subcommands = False
        
        for action in self.parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                self.has_subcommands = True
                for name, subparser in action.choices.items():
                    self.subparsers[name] = ArgparseCompleter(self.command, subparser)
            elif action.dest != 'help':
                arg_info = ArgumentInfo(action)
                self.arguments.append(arg_info)
                
                if arg_info.is_option:
                    for option in arg_info.option_strings:
                        self.options[option] = arg_info
                elif arg_info.is_positional:
                    self.positionals.append(arg_info)
    
    def get_completions(self, context: CompleterContext) -> List[Completion]:
        """获取补齐建议"""
        # 解析当前输入状态
        parsed = self._parse_input(context)
        
        # 如果有子命令且已选择，委托给子命令补齐器
        if parsed.subcommand and parsed.subcommand in self.subparsers:
            subcommand_completer = self.subparsers[parsed.subcommand]
            # 如果是增强补齐器，设置当前子命令
            if hasattr(subcommand_completer, '_current_subcommand'):
                subcommand_completer._current_subcommand = parsed.subcommand
            # 创建子命令的上下文（移除子命令名称）
            subcontext = self._create_subcommand_context(context, parsed.subcommand)
            return subcommand_completer.get_completions(subcontext)
        
        # 根据当前状态提供补齐
        completions = []
        
        # 如果有等待值的选项
        if parsed.pending_option:
            option_info = self.options.get(parsed.pending_option)
            if option_info and option_info.requires_value:
                completions.extend(self._complete_option_value(option_info, context))
                if completions:
                    return completions
        
        # 补齐子命令
        if self.has_subcommands and not parsed.subcommand:
            completions.extend(self._complete_subcommands(context))
        
        # 补齐选项
        completions.extend(self._complete_options(parsed, context))
        
        # 补齐位置参数
        positional_index = len(parsed.positionals)
        if positional_index < len(self.positionals):
            arg_info = self.positionals[positional_index]
            completions.extend(self._complete_positional(arg_info, context))
        
        return completions
    
    def _parse_input(self, context: CompleterContext) -> 'ParsedArguments':
        """解析输入状态"""
        parsed = ParsedArguments()
        
        # 安全地解析单词
        try:
            words = shlex.split(context.word_before_cursor)
        except ValueError:
            # 引号不匹配等情况
            words = context.word_before_cursor.split()
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # 检查是否是选项
            if word.startswith('-'):
                if word in self.options:
                    option_info = self.options[word]
                    if option_info.is_flag:
                        parsed.add_flag(word)
                    elif i + 1 < len(words):
                        # 下一个词是值
                        parsed.add_option_value(word, words[i + 1])
                        i += 1  # 跳过值
                    else:
                        # 选项在末尾，等待值
                        parsed.set_pending_option(word)
            # 检查是否是子命令
            elif self.has_subcommands and not parsed.subcommand and word in self.subparsers:
                parsed.subcommand = word
                # 子命令后的所有内容由子命令处理
                break
            # 否则是位置参数
            else:
                parsed.add_positional(word)
            
            i += 1
        
        # 处理末尾的空格（表示新位置）
        if context.is_empty_position and parsed.pending_option is None:
            # 刚输入空格，准备输入新内容
            if len(words) > 0 and words[-1].startswith('-') and words[-1] in self.options:
                option_info = self.options[words[-1]]
                if option_info.requires_value:
                    parsed.set_pending_option(words[-1])
        
        return parsed
    
    def _complete_subcommands(self, context: CompleterContext) -> List[Completion]:
        """补齐子命令"""
        completions = []
        partial = context.current_word
        
        has_subcommand = getattr(self.command, 'has_subcommand', None)
        if has_subcommand and not callable(has_subcommand):
            has_subcommand = None
        
        for name, subparser_completer in self.subparsers.items():
            if name.startswith(partial) and (not has_subcommand or has_subcommand(name)):
                # 获取子命令的描述
                description = ""
                if subparser_completer.parser.description:
                    description = subparser_completer.parser.description
                
                completions.append(create_completion(
                    name,
                    start_position=-len(partial) if partial else 0,
                    display_meta=description
                ))
        
        return completions
    
    def _complete_options(self, parsed: ParsedArguments, context: CompleterContext) -> List[Completion]:
        """补齐选项"""
        completions = []
        partial = context.current_word
        
        # 修改逻辑：空位置或以 - 开头时都补齐选项
        # 但如果有非空的 partial 且不以 - 开头，则不补齐（可能是在输入位置参数）
        if partial and not partial.startswith('-'):
            return []
        
        for option, arg_info in self.options.items():
            # 跳过已使用的选项（除非支持多次使用）
            if parsed.is_option_used(option):
                continue
            
            if option.startswith(partial):
                completions.append(create_completion(
                    option,
                    start_position=-len(partial) if partial else 0,
                    display_meta=arg_info.help or ""
                ))
        
        return completions
    
    def _complete_option_value(self, option_info: ArgumentInfo, context: CompleterContext) -> List[Completion]:
        """补齐选项值"""
        completions = []
        partial = context.current_word if not context.is_empty_position else ""

        get_arg_values = getattr(self.command, 'get_arg_values', None)
        if get_arg_values and callable(get_arg_values):
            values = get_arg_values(option_info.dest, partial=partial)
            if values:
                for name, desc in values:
                    if name.startswith(partial):
                            completions.append(create_completion(
                                name,
                                start_position=-len(partial) if partial else 0,
                                display_meta=desc or ""
                            ))
        elif option_info.choices:
            for choice in option_info.choices:
                choice_str = str(choice)
                if choice_str.startswith(partial):
                    completions.append(create_completion(
                        choice_str,
                        start_position=-len(partial) if partial else 0
                    ))
        
        return completions
    
    def _complete_positional(self, arg_info: ArgumentInfo, context: CompleterContext) -> List[Completion]:
        """补齐位置参数"""
        completions = []
        partial = context.current_word if not context.is_empty_position else ""

        get_arg_values = getattr(self.command, 'get_arg_values', None)
        if get_arg_values and callable(get_arg_values):
            values = get_arg_values(arg_info.dest, partial=partial)
            
            if values:
                for name, desc in values:
                    if name.startswith(partial):
                            completions.append(create_completion(
                                name,
                                start_position=-len(partial) if partial else 0,
                                display_meta=desc or ""
                            ))
        elif arg_info.choices:
            for choice in arg_info.choices:
                choice_str = str(choice)
                if choice_str.startswith(partial):
                    completions.append(create_completion(
                        choice_str,
                        start_position=-len(partial) if partial else 0,
                        display_meta=arg_info.help or ""
                    ))
        
        return completions
    
    def _create_subcommand_context(self, context: CompleterContext, subcommand: str) -> CompleterContext:
        """创建子命令的上下文"""
        # 找到子命令在文本中的位置
        subcommand_pos = context.word_before_cursor.find(subcommand)
        if subcommand_pos == -1:
            return context
        
        # 提取子命令后的文本（保留前导空格以正确判断 is_empty_position）
        text_after_subcommand_raw = context.word_before_cursor[subcommand_pos + len(subcommand):]
        text_after_subcommand = text_after_subcommand_raw.lstrip()
        
        # 重新解析单词（排除子命令本身）
        try:
            all_words = shlex.split(context.word_before_cursor)
            subcommand_index = all_words.index(subcommand) if subcommand in all_words else -1
            words_after = all_words[subcommand_index + 1:] if subcommand_index >= 0 else []
        except ValueError:
            words_after = text_after_subcommand.split()
        
        # 确定当前单词
        # 如果原始文本以空格结尾，说明是空位置
        is_empty = text_after_subcommand_raw.endswith(' ') or text_after_subcommand_raw == ' '
        if is_empty:
            current_word = ""
        elif words_after:
            current_word = words_after[-1]
        else:
            current_word = text_after_subcommand
        
        # 如果是空位置但 text_after_subcommand 是空的，需要特殊处理
        if is_empty and not text_after_subcommand:
            # 创建一个以空格结尾的上下文，以正确识别 is_empty_position
            return CompleterContext(
                text=" ",
                cursor_pos=1,
                words=[],
                current_word="",
                word_before_cursor=" "
            )
        
        return CompleterContext(
            text=text_after_subcommand,
            cursor_pos=len(text_after_subcommand),
            words=words_after,
            current_word=current_word,
            word_before_cursor=text_after_subcommand
        )

class EnhancedArgparseCompleter(ArgparseCompleter):
    """增强的 Argparse 补齐器，为路径参数使用专门的 PathCompleter"""
    
    def _analyze_parser(self):
        """重写解析器分析，确保子解析器也使用增强版本"""
        super()._analyze_parser()
        
        # 重新创建子解析器，使用增强版本
        enhanced_subparsers = {}
        for name, subparser_completer in self.subparsers.items():
            # 使用增强版本替换默认的 ArgparseCompleter
            enhanced_subparsers[name] = EnhancedArgparseCompleter(self.command, subparser_completer.parser)
        self.subparsers = enhanced_subparsers
    
    def get_completions(self, context: CompleterContext) -> List[Completion]:
        """重写补齐方法，特殊处理路径参数的补齐逻辑"""
        
        # 解析当前输入状态
        parsed = self._parse_input(context)
        
        # 如果有子命令且已选择，委托给子命令补齐器
        if parsed.subcommand and parsed.subcommand in self.subparsers:
            subcommand_completer = self.subparsers[parsed.subcommand]
            subcontext = self._create_subcommand_context(context, parsed.subcommand)
            return subcommand_completer.get_completions(subcontext)
        
        # 特殊处理：如果当前单词看起来像路径，或者是空位置且需要path参数，强制进行路径补齐
        has_path_param = self.positionals and self.positionals[0].dest == 'path'
        looks_like_path = context.current_word and ('/' in context.current_word or context.current_word.endswith('.json'))
        is_empty_path_position = context.is_empty_position and len(parsed.positionals) == 0
        
        if has_path_param and (looks_like_path or is_empty_path_position):
            # 直接调用路径补齐
            return self._complete_path_argument(self.positionals[0], context)
        
        # 其他情况使用默认逻辑
        return super().get_completions(context)
    
    def _complete_path_argument(self, arg_info: ArgumentInfo, context: CompleterContext) -> List[Completion]:
        """专门的路径参数补齐方法"""
        path_completer = PathCompleter(
            glob_pattern="*",
            show_hidden=False
        )
        completions = path_completer.get_completions(context)
        
        # 过滤和排序：JSON 文件优先
        json_files = []
        directories = []
        other_files = []
        
        for completion in completions:
            if completion.text.endswith('.json'):
                json_completion = Completion(
                    text=completion.text,
                    start_position=completion.start_position,
                    display=completion.display,
                    display_meta="📄 JSON"
                )
                json_files.append(json_completion)
            elif hasattr(completion, 'display_meta') and completion.display_meta == "目录":
                dir_completion = Completion(
                    text=completion.text,
                    start_position=completion.start_position,
                    display=completion.display,
                    display_meta="📁 Directory"
                )
                directories.append(dir_completion)
            else:
                # 其他所有文件都保留，包括目录（如果display_meta不是"目录"）
                other_files.append(completion)
        
        return json_files + directories + other_files
    
    def _complete_positional(self, arg_info: ArgumentInfo, context: CompleterContext) -> List[Completion]:
        """重写位置参数补齐，为路径类型使用 PathCompleter"""
        
        # 如果是路径参数，使用专门的路径补齐方法
        if arg_info.dest == 'path':
            return self._complete_path_argument(arg_info, context)
        
        # 其他参数使用默认逻辑
        return super()._complete_positional(arg_info, context)
