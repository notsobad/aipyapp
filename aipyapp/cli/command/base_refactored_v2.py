"""重构后的命令基类 - 职责分离（简化版）"""

from abc import ABC, abstractmethod
from typing import Optional, Any, List
from enum import Enum
import argparse

from ..completer.base import CompleterBase
from ..completer.argparse_completer import ArgparseCompleter


class CommandMode(Enum):
    """命令模式"""
    MAIN = "main"
    TASK = "task"


class Command(ABC):
    """
    重构后的命令基类（简化版）
    
    职责：
    1. 定义命令元信息
    2. 创建和管理 ArgumentParser
    3. 执行命令逻辑
    
    不负责：
    - 自动补齐（委托给 Completer）
    - 参数解析细节（委托给 ArgumentParser）
    """
    
    def __init__(self, 
                 name: str,
                 description: str = "",
                 modes: Optional[List[CommandMode]] = None):
        """
        初始化命令
        
        Args:
            name: 命令名称
            description: 命令描述
            modes: 支持的模式列表
        """
        self.name = name
        self.description = description
        self.modes = modes or [CommandMode.MAIN]
        self._parser: Optional[argparse.ArgumentParser] = None
        self._completer: Optional[CompleterBase] = None
    
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
    
    用于快速创建简单命令，提供了基础的 parser 创建逻辑
    """
    
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
        
        子类重写此方法来定义具体参数
        
        Args:
            parser: ArgumentParser 实例
        """
        pass


class SubCommand(Command):
    """
    带子命令的命令基类
    """
    
    def create_parser(self) -> argparse.ArgumentParser:
        """创建带子命令的 parser"""
        parser = argparse.ArgumentParser(
            prog=self.name,
            description=self.description,
            exit_on_error=False
        )
        
        # 添加子命令
        subparsers = parser.add_subparsers(
            dest='subcommand',
            help='Available subcommands'
        )
        
        self.add_subcommands(subparsers)
        return parser
    
    @abstractmethod
    def add_subcommands(self, subparsers):
        """
        添加子命令
        
        Args:
            subparsers: 子命令解析器
        """
        pass


class HybridCommand(Command):
    """
    混合命令基类
    
    同时支持直接执行和子命令
    """
    
    def create_parser(self) -> argparse.ArgumentParser:
        """创建混合 parser"""
        parser = argparse.ArgumentParser(
            prog=self.name,
            description=self.description,
            exit_on_error=False
        )
        
        # 添加主命令参数
        self.add_arguments(parser)
        
        # 添加子命令（可选）
        if self.has_subcommands():
            subparsers = parser.add_subparsers(
                dest='subcommand',
                help='Available subcommands'
            )
            self.add_subcommands(subparsers)
        
        return parser
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        """添加主命令参数"""
        pass
    
    def has_subcommands(self) -> bool:
        """是否有子命令"""
        return False
    
    def add_subcommands(self, subparsers):
        """添加子命令"""
        pass