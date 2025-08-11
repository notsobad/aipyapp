"""示例命令 - 展示新架构的使用方式"""

import argparse
from typing import Any, List
from pathlib import Path

from .base_refactored import SimpleCommand, SubcommandCommand, CommandMode, CommandMeta
from ..completer.base import CompleterBase, CompleterContext
from ..completer.specialized import CompositeCompleter, PathCompleter, ChoiceCompleter, DynamicCompleter
from ..completer.argparse_completer import ArgparseCompleter


class ExampleSimpleCommand(SimpleCommand):
    """
    简单命令示例
    
    展示如何创建一个基础命令
    """
    
    def __init__(self):
        super().__init__(
            name="example",
            description="A simple example command",
            modes=[CommandMode.MAIN, CommandMode.TASK]
        )
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        """定义命令参数"""
        parser.add_argument(
            'action',
            choices=['start', 'stop', 'status'],
            help='Action to perform'
        )
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose output'
        )
        parser.add_argument(
            '--config',
            type=str,
            help='Configuration file path'
        )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        """执行命令"""
        result = {
            'action': args.action,
            'verbose': args.verbose,
            'config': args.config
        }
        
        if args.verbose:
            print(f"Executing {args.action} with config: {args.config}")
        
        return result
    
    def _create_completer(self) -> CompleterBase:
        """
        自定义补齐器
        
        为 --config 参数提供文件路径补齐
        """
        completer = CompositeCompleter()
        
        # 基础 argparse 补齐
        completer.add_strategy(ArgparseCompleter(self.parser))
        
        # 为 --config 参数添加文件路径补齐
        def is_config_arg(ctx: CompleterContext) -> bool:
            return '--config' in ctx.text and ctx.text.rstrip().endswith('--config')
        
        completer.add_strategy(
            PathCompleter(only_files=True),
            condition=is_config_arg
        )
        
        return completer


class ExampleSubcommandCommand(SubcommandCommand):
    """
    子命令示例
    
    展示如何创建支持子命令的命令
    """
    
    def __init__(self):
        meta = CommandMeta(
            name="project",
            description="Project management command",
            modes=[CommandMode.MAIN]
        )
        super().__init__(meta)
        
        # 注册子命令
        self.register_subcommand(ProjectListSubcommand())
        self.register_subcommand(ProjectCreateSubcommand())
        self.register_subcommand(ProjectDeleteSubcommand())
    
    def add_common_arguments(self, parser: argparse.ArgumentParser):
        """添加通用参数"""
        parser.add_argument(
            '--format',
            choices=['json', 'yaml', 'table'],
            default='table',
            help='Output format'
        )
    
    def execute_main(self, args: argparse.Namespace, context: Any) -> Any:
        """主命令执行（没有子命令时）"""
        return {
            'message': 'Please specify a subcommand',
            'available': list(self.subcommands.keys())
        }


class ProjectListSubcommand(SimpleCommand):
    """列出项目子命令"""
    
    def __init__(self):
        super().__init__(
            name="list",
            description="List all projects"
        )
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            '--filter',
            type=str,
            help='Filter projects by name pattern'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of projects to show'
        )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        # 模拟项目列表
        projects = [
            {'name': 'project1', 'status': 'active'},
            {'name': 'project2', 'status': 'inactive'},
            {'name': 'project3', 'status': 'active'},
        ]
        
        # 应用过滤
        if args.filter:
            projects = [p for p in projects if args.filter in p['name']]
        
        # 应用限制
        projects = projects[:args.limit]
        
        return {'projects': projects, 'count': len(projects)}


class ProjectCreateSubcommand(SimpleCommand):
    """创建项目子命令"""
    
    def __init__(self):
        super().__init__(
            name="create",
            description="Create a new project"
        )
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            'name',
            help='Project name'
        )
        parser.add_argument(
            '--template',
            choices=['basic', 'web', 'api', 'ml'],
            default='basic',
            help='Project template'
        )
        parser.add_argument(
            '--path',
            type=str,
            help='Project directory path'
        )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        return {
            'action': 'create',
            'name': args.name,
            'template': args.template,
            'path': args.path or f"./{args.name}"
        }
    
    def _create_completer(self) -> CompleterBase:
        """为 --path 参数提供目录补齐"""
        completer = CompositeCompleter()
        completer.add_strategy(ArgparseCompleter(self.parser))
        
        # 路径补齐
        def is_path_arg(ctx: CompleterContext) -> bool:
            return '--path' in ctx.text
        
        completer.add_strategy(
            PathCompleter(only_dirs=True),
            condition=is_path_arg
        )
        
        return completer


class ProjectDeleteSubcommand(SimpleCommand):
    """删除项目子命令"""
    
    def __init__(self):
        super().__init__(
            name="delete",
            description="Delete a project"
        )
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            'name',
            help='Project name to delete'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation'
        )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        if not args.force:
            # 在实际应用中，这里应该请求确认
            return {
                'action': 'delete',
                'name': args.name,
                'status': 'confirmation_required'
            }
        
        return {
            'action': 'delete',
            'name': args.name,
            'status': 'deleted'
        }
    
    def _create_completer(self) -> CompleterBase:
        """为项目名提供动态补齐"""
        completer = CompositeCompleter()
        
        # 基础补齐
        completer.add_strategy(ArgparseCompleter(self.parser))
        
        # 动态项目名补齐
        def get_project_names(ctx: CompleterContext) -> List[tuple[str, str]]:
            # 模拟从数据库或文件系统获取项目名
            projects = [
                ('project1', 'Web application'),
                ('project2', 'API service'),
                ('project3', 'ML pipeline'),
            ]
            return projects
        
        # 只在输入位置参数时提供项目名补齐
        def is_name_position(ctx: CompleterContext) -> bool:
            # 简单判断：没有 -- 开头的选项
            return not any(w.startswith('-') for w in ctx.words)
        
        completer.add_strategy(
            DynamicCompleter(get_project_names),
            condition=is_name_position
        )
        
        return completer


class ExampleAdvancedCommand(SimpleCommand):
    """
    高级命令示例
    
    展示复杂的补齐逻辑
    """
    
    def __init__(self):
        super().__init__(
            name="advanced",
            description="Advanced command with complex completion",
            modes=[CommandMode.MAIN]
        )
    
    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Input file or URL'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'yaml', 'xml', 'csv'],
            help='Output format'
        )
        parser.add_argument(
            '--filter',
            type=str,
            action='append',
            help='Filter expression (can be used multiple times)'
        )
    
    def execute(self, args: argparse.Namespace, context: Any) -> Any:
        return {
            'input': args.input,
            'output': args.output,
            'format': args.format,
            'filters': args.filter or []
        }
    
    def _create_completer(self) -> CompleterBase:
        """
        复杂的补齐逻辑
        
        - input: 文件或 URL
        - output: 文件路径
        - filter: 动态表达式
        """
        from ..completer.specialized import ChainedCompleter
        
        completer = CompositeCompleter()
        
        # 基础 argparse 补齐
        completer.add_strategy(ArgparseCompleter(self.parser))
        
        # Input 补齐：文件或 URL
        def is_input_arg(ctx: CompleterContext) -> bool:
            words = ctx.words
            return len(words) >= 2 and words[-2] == '--input'
        
        input_completer = ChainedCompleter([
            PathCompleter(),  # 文件路径
            ChoiceCompleter([  # 常用 URL 前缀
                'http://',
                'https://',
                'ftp://',
                'file://',
            ])
        ])
        completer.add_strategy(input_completer, condition=is_input_arg)
        
        # Output 补齐：文件路径
        def is_output_arg(ctx: CompleterContext) -> bool:
            words = ctx.words
            return len(words) >= 2 and words[-2] == '--output'
        
        completer.add_strategy(
            PathCompleter(),
            condition=is_output_arg
        )
        
        # Filter 补齐：动态表达式
        def is_filter_arg(ctx: CompleterContext) -> bool:
            words = ctx.words
            return len(words) >= 2 and words[-2] == '--filter'
        
        filter_completer = ChoiceCompleter(
            choices=[
                'name=',
                'type=',
                'size>',
                'size<',
                'created>',
                'modified<',
            ],
            descriptions={
                'name=': 'Filter by name',
                'type=': 'Filter by type',
                'size>': 'Filter by minimum size',
                'size<': 'Filter by maximum size',
                'created>': 'Filter by creation date',
                'modified<': 'Filter by modification date',
            }
        )
        completer.add_strategy(filter_completer, condition=is_filter_arg)
        
        return completer


def create_example_commands() -> List[SimpleCommand]:
    """创建所有示例命令"""
    return [
        ExampleSimpleCommand(),
        ExampleSubcommandCommand(),
        ExampleAdvancedCommand(),
    ]