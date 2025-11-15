#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime

from rich.tree import Tree

from .utils import row2table
from ..base import CommandMode, ParserCommand
from aipyapp import T

class SubTaskCommand(ParserCommand):
    """SubTask command - view and manage subtasks"""
    name = "subtask"
    description = T("View and manage subtasks")
    modes = [CommandMode.TASK]

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help=T('List subtasks in table format'))
        parser = subparsers.add_parser('tree', help=T('Show subtask tree'))
        parser.add_argument('--recursive', '-r', action='store_true',
                          help=T('Show nested subtasks recursively'))

    def cmd(self, args, ctx):
        """Default command: show list"""
        return self.cmd_list(args, ctx)

    def cmd_list(self, args, ctx):
        """Display subtasks in table format"""
        task = ctx.task
        subtasks = task.get_subtasks(reload=True)

        if not subtasks:
            ctx.console.print(T("No subtasks found"))
            return

        # Build table data
        rows = []
        for i, subtask in enumerate(subtasks):
            instruction = subtask.instruction[:50] if subtask.instruction else "N/A"

            # Status
            if subtask.steps:
                if subtask.steps[-1].data.end_time:
                    status = "✅ COMPLETED"
                    status_color = "green"
                else:
                    status = "⏳ RUNNING"
                    status_color = "yellow"
            else:
                status = "❓ UNKNOWN"
                status_color = "dim"

            # Time info
            if subtask.steps:
                start = datetime.fromtimestamp(subtask.steps[0].data.start_time).strftime('%H:%M:%S')
                if subtask.steps[-1].data.end_time:
                    end = datetime.fromtimestamp(subtask.steps[-1].data.end_time).strftime('%H:%M:%S')
                    duration = subtask.steps[-1].data.end_time - subtask.steps[0].data.start_time
                    time_info = f"{start}-{end} ({duration:.1f}s)"
                else:
                    time_info = f"{start} (running)"
            else:
                time_info = "N/A"

            rows.append([i, instruction, status, time_info, subtask.task_id])

        table = row2table(rows,
                         title=T('Subtasks'),
                         headers=[T('Index'), T('Instruction'), T('Status'), T('Time'), T('Task ID')])
        ctx.console.print(table)

    def cmd_tree(self, args, ctx):
        """Display subtasks in tree format"""
        task = ctx.task
        subtasks = task.get_subtasks(reload=True)

        if not subtasks:
            ctx.console.print(T("No subtasks found."))
            return

        tree = self._build_subtask_tree(task, subtasks, args.recursive)
        ctx.console.print("\n")
        ctx.console.print(tree)
        ctx.console.print("\n")

    def _build_subtask_tree(self, task, subtasks, recursive=False):
        """Build subtask tree structure"""
        # Create root node
        root_title = task.instruction[:50] if task.instruction else "Current Task"
        tree = Tree(f"[bold cyan]📋 {root_title}[/bold cyan] [dim](ID: {task.task_id})[/dim]")

        # Add subtask nodes
        for subtask in subtasks:
            self._add_subtask_node(tree, subtask, recursive)

        return tree

    def _add_subtask_node(self, parent_node, subtask, recursive):
        """Add subtask node to tree"""
        # Build node title
        instruction = subtask.instruction[:50] if subtask.instruction else "Subtask"
        title = instruction

        # Status indicator
        if subtask.steps:
            last_step = subtask.steps[-1]
            if last_step.data.end_time:
                status_icon = "✅"
                status_color = "green"
                status_text = "COMPLETED"
            else:
                status_icon = "⏳"
                status_color = "yellow"
                status_text = "RUNNING"
        else:
            status_icon = "❓"
            status_color = "dim"
            status_text = "UNKNOWN"

        # Create node
        node_title = f"{status_icon} [{status_color}]{status_text}[/{status_color}] [bold]{title}[/bold]"
        subtask_node = parent_node.add(node_title)

        # Add details
        subtask_node.add(f"[dim]ID:[/dim] {subtask.task_id}")

        # Time information
        if subtask.steps:
            first_step = subtask.steps[0]
            last_step = subtask.steps[-1]
            start_time = datetime.fromtimestamp(first_step.data.start_time).strftime('%H:%M:%S')

            if last_step.data.end_time:
                end_time = datetime.fromtimestamp(last_step.data.end_time).strftime('%H:%M:%S')
                duration = last_step.data.end_time - first_step.data.start_time
                subtask_node.add(f"[dim]Duration: {duration:.1f}s ({start_time} - {end_time})[/dim]")
            else:
                subtask_node.add(f"[dim]Started: {start_time}[/dim]")

        subtask_node.add(f"[dim]Path:[/dim] {subtask.cwd}")

        # Recursively handle nested subtasks
        if recursive:
            nested_subtasks = subtask.get_subtasks(reload=True)
            if nested_subtasks:
                nested_node = subtask_node.add(f"[dim]🔗 Nested Subtasks ({len(nested_subtasks)}):[/dim]")
                for nested in nested_subtasks:
                    self._add_subtask_node(nested_node, nested, recursive)
