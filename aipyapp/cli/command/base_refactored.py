"""重构后的命令基类 - 职责分离"""

from abc import ABC, abstractmethod
from typing import Optional, Any, List, Dict
from enum import Enum
import argparse

from ..completer.base import CompleterBase
from ..completer.argparse_completer import ArgparseCompleter


class CommandMode(Enum):
    """命令模式"""
    MAIN = "main"
    TASK = "task"


class CommandMeta:
    """命令元信息"""
    
    def __init__(self, 
                 name: str,
                 description: str = "",
                 modes: Optional[List[CommandMode]] = None,
                 aliases: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.modes = modes or [CommandMode.MAIN]
        self.aliases = aliases or []


class Command(ABC):
    """
    重构后的命令基类
    
    职责：
    1. 定义命令元信息
    2. 创建和管理 ArgumentParser
    3. 执行命令逻辑
    
    不负责：
    - 自动补齐（委托给 Completer）
    - 参数解析细节（委托给 ArgumentParser）
    """
    
    def __init__(self, meta: CommandMeta):
        self.meta = meta
        self._parser: Optional[argparse.ArgumentParser] = None
        self._completer: Optional[CompleterBase] = None
    
    @property
    def name(self) -> str:
        """命令名称"""
        return self.meta.name
    
    @property
    def description(self) -> str:
        """命令描述"""
        return self.meta.description
    
    @property
    def modes(self) -> List[CommandMode]:
        """支持的模式"""
        return self.meta.modes
    
    @property
    def parser(self) -> argparse.ArgumentParser:
        """
        获取 ArgumentParser（延迟创建）
        """
        if self._parser is None:
            self._parser = self.create_parser()
        return self._parser
    
    @abstractmethod
    def create_parser(self) -> argparse.ArgumentParser:
        """
        创建命令的 ArgumentParser
        
        子类实现此方法来定义命令参数
        """
        pass
    
    @abstractmethod
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        """
        执行命令
        
        Args:
            args: 解析后的参数
            context: 执行上下文
            
        Returns:
            命令执行结果
        """
        pass
    
    def get_completer(self) -> CompleterBase:
        """
        获取命令的补齐器
        
        默认使用 ArgparseCompleter，子类可以覆盖以提供自定义补齐
        """
        if self._completer is None:
            self._completer = self._create_completer()
        return self._completer
    
    def _create_completer(self) -> CompleterBase:
        """
        创建补齐器
        
        子类可以覆盖此方法以提供自定义补齐器
        """
        return ArgparseCompleter(self.parser)
    
    def validate_args(self, args: argparse.Namespace) -> Optional[str]:
        """
        验证参数
        
        Args:
            args: 解析后的参数
            
        Returns:
            错误信息，如果验证通过则返回 None
        """
        return None


class SimpleCommand(Command):
    """
    简单命令基类
    
    用于快速创建简单命令
    """
    
    def __init__(self,
                 name: str,
                 description: str = "",
                 modes: Optional[List[CommandMode]] = None):
        meta = CommandMeta(name, description, modes)
        super().__init__(meta)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """创建基础 parser"""
        parser = argparse.ArgumentParser(
            prog=self.name,
            description=self.description,
            exit_on_error=False,
            add_help=True
        )
        self.add_arguments(parser)
        return parser
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        """
        添加命令参数
        
        子类覆盖此方法来添加参数
        """
        pass


class SubcommandCommand(Command):
    """
    支持子命令的命令基类
    """
    
    def __init__(self, meta: CommandMeta):
        super().__init__(meta)
        self.subcommands: Dict[str, Command] = {}
    
    def create_parser(self) -> argparse.ArgumentParser:
        """创建支持子命令的 parser"""
        parser = argparse.ArgumentParser(
            prog=self.name,
            description=self.description,
            exit_on_error=False
        )
        
        # 添加通用参数
        self.add_common_arguments(parser)
        
        # 添加子命令
        if self.subcommands:
            subparsers = parser.add_subparsers(
                dest='subcommand',
                help='Available subcommands'
            )
            
            for subcmd_name, subcmd in self.subcommands.items():
                subparser = subparsers.add_parser(
                    subcmd_name,
                    help=subcmd.description
                )
                # 让子命令添加自己的参数
                if hasattr(subcmd, 'add_arguments'):
                    subcmd.add_arguments(subparser)
        
        return parser
    
    def add_common_arguments(self, parser: argparse.ArgumentParser):
        """添加通用参数"""
        pass
    
    def register_subcommand(self, subcommand: Command):
        """注册子命令"""
        self.subcommands[subcommand.name] = subcommand
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        """执行命令或子命令"""
        subcommand_name = getattr(args, 'subcommand', None)
        
        if subcommand_name and subcommand_name in self.subcommands:
            # 执行子命令
            subcommand = self.subcommands[subcommand_name]
            return subcommand.execute(args, context)
        else:
            # 执行主命令
            return self.execute_main(args, context)
    
    @abstractmethod
    def execute_main(self, args: argparse.Namespace, context: Any) -> Any:
        """执行主命令逻辑"""
        pass


class DelegatingCommand(Command):
    """
    委托命令 - 将执行委托给其他对象
    """
    
    def __init__(self, meta: CommandMeta, delegate: Any):
        super().__init__(meta)
        self.delegate = delegate
    
    def create_parser(self) -> argparse.ArgumentParser:
        """从委托对象创建 parser"""
        if hasattr(self.delegate, 'create_parser'):
            return self.delegate.create_parser()
        elif hasattr(self.delegate, 'parser'):
            return self.delegate.parser
        else:
            # 创建默认 parser
            return argparse.ArgumentParser(
                prog=self.name,
                description=self.description,
                exit_on_error=False
            )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        """委托执行"""
        if hasattr(self.delegate, 'execute'):
            return self.delegate.execute(args, context)
        elif callable(self.delegate):
            return self.delegate(args, context)
        else:
            raise NotImplementedError(f"Delegate {self.delegate} cannot execute")