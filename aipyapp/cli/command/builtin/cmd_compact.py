"""
Task Context Compact Command

Provides intelligent context compression for tasks using LLM-generated summaries.
"""

import argparse
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import time

from aipyapp import T
from ..base import ParserCommand
from ..common import CommandMode, CommandContext


class CompactCommand(ParserCommand):
    """Intelligent task context compression command"""

    name = "compact"
    description = T("Intelligently compress task context using LLM-generated summaries")
    modes = [CommandMode.TASK]

    def __init__(self):
        super().__init__()
        self.console = Console()

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add command arguments"""
        parser.add_argument(
            '--client', '-c',
            type=str,
            help=T('LLM client to use for summarization (default: current task client)')
        )
        parser.add_argument(
            '--force', '-f',
            action='store_true',
            help=T('Force compression even if context is small')
        )

        # Subcommands
        subparsers = parser.add_subparsers(dest='subcommand', help=T('Available subcommands'))

        # Show subcommand
        show_parser = subparsers.add_parser('show', help=T('Show current context statistics'))

    def get_arg_values(self, arg_name: str, subcommand=None, partial=None) -> List[str]:
        """Get tab completion values for arguments"""
        if arg_name == 'client':
            ctx = self.manager.context
            return [(client.name, str(client)) for client in ctx.tm.client_manager.clients.values()]
        elif arg_name == 'subcommand':
            return ['show']
        return []

    def cmd(self, args: argparse.Namespace, ctx: CommandContext) -> bool:
        """Main compact command"""
        task = ctx.task
        if not task:
            self.console.print("[red]❌ No active task found[/red]")
            return False

        # Handle subcommands
        if args.subcommand == 'show':
            return self._cmd_show(task)

        # Main compact command
        return self._cmd_compact(task, args)

    def _cmd_show(self, task) -> bool:
        """Show current context statistics"""
        try:
            self._display_context_stats(task, "Current Context Statistics")
            return True
        except Exception as e:
            self.console.print(f"[red]❌ Failed to get context statistics: {e}[/red]")
            return False

    def _cmd_compact(self, task, args: argparse.Namespace) -> bool:
        """Execute context compression using Task's compress_context method"""
        try:
            # Show current statistics
            stats_before = task.context_manager.get_stats()
            self._display_context_stats(task, "Context Statistics - Before Compression")

            # Check if compression would be beneficial
            if (stats_before['message_count'] < 10 and
                stats_before['total_tokens'] < 5000 and
                not args.force):
                self.console.print("[yellow]ℹ️  Context is relatively small, compression may not be necessary[/yellow]")
                self.console.print("Use --force to compress anyway")
                return True

            # Prepare for compression
            self.console.print(f"\n[bold]🚀 Starting Context Compression[/bold]")

            client_name = args.client or "current task client"
            self.console.print(f"Using LLM: [cyan]{client_name}[/cyan]")

            # Call Task's compress_context method
            result = task.compress_context(client_name=args.client)

            # Handle result
            if not result['success']:
                self.console.print(f"[red]❌ Compression failed: {result['error']}[/red]")
                return False

            # Display compression results
            self._display_compression_results(result)

            self.console.print("\n[green]✅ Context compression completed successfully[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]❌ Compression failed: {e}[/red]")
            return False

    def _display_context_stats(self, task, title: str):
        """Display context statistics in a formatted table"""
        stats = task.context_manager.get_stats()

        # Create main stats table
        table = Table(title=title, show_header=False, box=None)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green")

        table.add_row("Message Count", f"{stats['message_count']:,}")
        table.add_row("Total Tokens", f"{stats['total_tokens']:,}")

        # Show last compression time
        last_compression = stats.get('last_compression')
        if last_compression:
            time_ago = time.time() - last_compression
            if time_ago < 60:
                time_str = f"{int(time_ago)} seconds ago"
            elif time_ago < 3600:
                time_str = f"{int(time_ago // 60)} minutes ago"
            else:
                time_str = f"{int(time_ago // 3600)} hours ago"
            table.add_row("Last Compression", time_str)
        else:
            table.add_row("Last Compression", "Never")

        self.console.print(table)

        # Show message breakdown by role
        if hasattr(task.context_manager, 'messages'):
            role_counts = {}
            for msg in task.context_manager.messages:
                role = msg.role.value
                role_counts[role] = role_counts.get(role, 0) + 1

            if role_counts:
                breakdown_table = Table(title="Message Breakdown", show_header=True, box=None)
                breakdown_table.add_column("Role", style="cyan")
                breakdown_table.add_column("Count", style="green")
                breakdown_table.add_column("Percentage", style="yellow")

                total_msgs = sum(role_counts.values())
                for role, count in role_counts.items():
                    percentage = (count / total_msgs) * 100
                    breakdown_table.add_row(role, str(count), f"{percentage:.1f}%")

                self.console.print(breakdown_table)

    def _display_compression_results(self, result: Dict[str, Any]):
        """Display compression results using data from Task's compress_context method"""
        stats_before = result['stats_before']
        stats_after = result['stats_after']
        summary_tokens = result['summary_tokens']
        messages_saved = result['messages_saved']
        tokens_saved = result['tokens_saved']
        compression_ratio = result['compression_ratio']

        # Create results table
        table = Table(title="Compression Results", show_header=True)
        table.add_column("Metric", style="cyan", width=15)
        table.add_column("Before", style="red", width=12)
        table.add_column("After", style="green", width=12)
        table.add_column("Saved", style="yellow", width=12)
        table.add_column("Reduction", style="bright_magenta", width=10)

        table.add_row(
            "Messages",
            f"{stats_before['message_count']:,}",
            f"{stats_after['message_count']:,}",
            f"{messages_saved:,}",
            f"{(messages_saved/stats_before['message_count']*100):.1f}%"
        )
        table.add_row(
            "Tokens",
            f"{stats_before['total_tokens']:,}",
            f"{stats_after['total_tokens']:,}",
            f"{tokens_saved:,}",
            f"{compression_ratio*100:.1f}%"
        )
        table.add_row(
            "Summary",
            "-",
            f"{summary_tokens:,}",
            "-",
            "-"
        )

        self.console.print(table)

        # Show compression summary
        self.console.print(f"\n[bold]📊 Compression Summary:[/bold]")
        self.console.print(f"  • Messages reduced: [yellow]{messages_saved:,}[/yellow]")
        self.console.print(f"  • Tokens saved: [yellow]{tokens_saved:,}[/yellow] ({compression_ratio:.1%} reduction)")
        self.console.print(f"  • Summary size: [green]{summary_tokens:,} tokens[/green]")