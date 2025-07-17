from rich import print
from rich.table import Table

from ... import T
from .base import BaseCommand
from .utils import print_table

class ToolsCommand(BaseCommand):
    name = 'tools'
    description = T('Tools operations')

    def process_tools_ret(self, args, ret):
        """处理 tools 命令的返回结果并格式化显示"""
        if not isinstance(ret, dict):
            print(f"[red]{T('Invalid response format')}[/red]")
            return
            
        action = args[0] if args else "list"
        
        # 显示操作结果
        if action == "enable":
            print(
                f"[green]{T('Internal tools have been enabled successfully')}[/green]"
            )
        elif action == "disable":
            print(
                f"[yellow]{T('Internal tools have been disabled successfully')}[/yellow]"
            )
        
        # 如果返回的是错误信息
        if ret.get("status") == "error":
            print(f"[red]{T('Error')}: {ret.get('message', 'Unknown error')}[/red]")
            return
        
        # 显示服务器状态表格
        servers = ret
        if servers:
            table_data = []

            for server_name, info in servers.items():
                status = T('Enabled') if info.get("enabled", False) else T('Disabled')
                tools_count = info.get("tools_count", 0)
                if info.get("enabled", False):
                    table_data.append([server_name, status, tools_count])

            if table_data:
                headers = [T('Server Name'), T('Status'), T('Tools Count')]
                print_table(
                    table_data,
                    title=T("Internal Tools Servers"),
                    headers=headers
                )

        else:
            print(f"[dim]{T('No internal tools servers found')}[/dim]")

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help=T('List available tools'))
        subparsers.add_parser('enable', help=T('Enable tools'))
        subparsers.add_parser('disable', help=T('Disable tools'))

    def execute(self, args):
        raw_args = args.raw_args
        if not raw_args:
            # 默认执行 list 操作
            raw_args = ['list']
        
        tm = self.manager.tm
        if not tm.mcp:
            self.log.error('MCP not found')
            return
            
        ret = tm.mcp.process_tool_cmd(raw_args)
        self.process_tools_ret(raw_args, ret)