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
        parser = subparsers.add_parser('show', help=T('Show detailed information about a specific subtask'))
        parser.add_argument('tid', help=T('Task ID of the subtask to show'))
        parser.add_argument('--rounds', action='store_true', help=T('Show detailed step rounds information'))

    def get_arg_values(self, name, subcommand=None, partial=None):
        """为 tid 参数提供补齐值，path 参数由 PathCompleter 处理"""
        if name == 'tid':
            tasks = self.manager.context.task.subtasks
            return [(task.task_id, task.instruction[:32]) for task in tasks]
        return None
    
    def cmd(self, args, ctx):
        """Default command: show list"""
        return self.cmd_list(args, ctx)

    def cmd_list(self, args, ctx):
        """Display subtasks in table format"""
        task = ctx.task
        subtasks = task.subtasks

        if not subtasks:
            ctx.console.print(T("No subtasks found"))
            return

        # Build table data
        rows = []
        for i, subtask in enumerate(subtasks):
            # Instruction with 32 character truncation and ellipsis
            if subtask.instruction:
                instruction = subtask.instruction[:32] + "..." if len(subtask.instruction) > 32 else subtask.instruction
            else:
                instruction = "N/A"

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

            rows.append([subtask.task_id, time_info, instruction])

        table = row2table(rows,
                         title=T('Subtasks'),
                         headers=[T('Task ID'), T('Time'), T('Instruction')])
        ctx.console.print(table)

    def cmd_show(self, args, ctx):
        """Display detailed information about a specific subtask"""
        task_id = args.tid

        # Find the subtask
        subtask = self._find_subtask_by_id(ctx.task, task_id)
        if not subtask:
            ctx.console.print(f"[red]❌ Subtask with ID '{task_id}' not found[/red]")
            return False

        # Build and display the detail tree
        tree = self._build_subtask_detail_tree(subtask, args.rounds)
        ctx.console.print(tree)
        return True

    def _find_subtask_by_id(self, task, task_id):
        """Recursively find subtask by ID"""
        for subtask in task.subtasks:
            if subtask.task_id == task_id:
                return subtask
            # Recursively search in nested subtasks
            found = self._find_subtask_by_id(subtask, task_id)
            if found:
                return found
        return None

    def _build_subtask_detail_tree(self, subtask, show_rounds=False):
        """Build detailed information tree for subtask"""
        from datetime import datetime

        # Main title
        instruction = subtask.instruction[:60] + "..." if len(subtask.instruction or "") > 60 else (subtask.instruction or "Untitled Subtask")
        tree = Tree(f"[bold cyan]📋 Subtask Details[/bold cyan]")

        # 1. Basic Information
        self._add_basic_info(tree, subtask)

        # 2. Time Information
        self._add_time_info(tree, subtask)

        # 3. Steps Summary
        self._add_steps_summary(tree, subtask)

        # 4. Hierarchy Information
        self._add_hierarchy_info(tree, subtask)

        # 5. Detailed steps (optional)
        if show_rounds:
            self._add_detailed_steps(tree, subtask)

        return tree

    def _add_basic_info(self, tree, subtask):
        """Add basic information section"""
        basic_node = tree.add("[bold blue]📋 Basic Information[/bold blue]")

        # Task ID (truncated for display)
        task_id_display = subtask.task_id[:12] + "..." if len(subtask.task_id) > 12 else subtask.task_id
        basic_node.add(f"[dim]🆔 Task ID:[/dim] {task_id_display}")

        # Instruction
        instruction = subtask.instruction or "N/A"
        if len(instruction) > 80:
            instruction = instruction[:80] + "..."
        basic_node.add(f"[dim]📝 Instruction:[/dim] \"{instruction}\"")

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

        steps_count = len(subtask.steps)
        rounds_count = sum(len(step.data.rounds) for step in subtask.steps)
        basic_node.add(f"[dim]⚡ Status:[/dim] [{status_color}]{status}[/{status_color}] ({steps_count} steps, {rounds_count} rounds)")

        # LLM Model
        model_name = getattr(subtask, 'client', None)
        if model_name:
            model_name = getattr(model_name, 'name', 'Unknown')
        else:
            model_name = 'Unknown'
        basic_node.add(f"[dim]🤖 LLM Model:[/dim] {model_name}")

        # Working Directory
        basic_node.add(f"[dim]📁 Working Directory:[/dim] {subtask.cwd}")

    def _add_time_info(self, tree, subtask):
        """Add time information section"""
        time_node = tree.add("[bold blue]⏱️ Time Information[/bold blue]")

        if subtask.steps:
            start_time = datetime.fromtimestamp(subtask.steps[0].data.start_time)
            time_node.add(f"[dim]🚀 Started:[/dim] {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            if subtask.steps[-1].data.end_time:
                end_time = datetime.fromtimestamp(subtask.steps[-1].data.end_time)
                duration = subtask.steps[-1].data.end_time - subtask.steps[0].data.start_time
                time_node.add(f"[dim]🏁 Completed:[/dim] {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Format duration
                if duration < 60:
                    duration_str = f"{duration:.1f}s"
                elif duration < 3600:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    duration_str = f"{minutes}m {seconds:.1f}s"
                else:
                    hours = int(duration // 3600)
                    minutes = int((duration % 3600) // 60)
                    seconds = duration % 60
                    duration_str = f"{hours}h {minutes}m {seconds:.1f}s"

                time_node.add(f"[dim]⏳ Duration:[/dim] {duration_str}")

                # Average per step
                avg_duration = duration / len(subtask.steps)
                if avg_duration < 60:
                    avg_str = f"{avg_duration:.1f}s"
                else:
                    avg_minutes = int(avg_duration // 60)
                    avg_seconds = avg_duration % 60
                    avg_str = f"{avg_minutes}m {avg_seconds:.1f}s"
                time_node.add(f"[dim]📊 Average per step:[/dim] {avg_str}")
            else:
                time_node.add(f"[dim]⏳ Status:[/dim] Still running...")
        else:
            time_node.add("[dim]⏳ No time information available[/dim]")

    def _add_steps_summary(self, tree, subtask):
        """Add steps summary section"""
        if not subtask.steps:
            tree.add("[bold blue]📊 Steps Summary[/bold blue] [dim](No steps)[/dim]")
            return

        steps_node = tree.add(f"[bold blue]📊 Steps Summary[/bold blue] [dim]({len(subtask.steps)} steps)[/dim]")

        total_tokens = 0
        total_rounds = 0

        for i, step in enumerate(subtask.steps):
            # Step status
            if step.data.end_time:
                status = "✅ COMPLETED"
                status_color = "green"
            else:
                status = "⏳ RUNNING"
                status_color = "yellow"

            # Step instruction (truncated)
            step_instruction = step.data.instruction[:40] + "..." if len(step.data.instruction or "") > 40 else (step.data.instruction or "Untitled Step")

            # Calculate step metrics
            rounds_count = len(step.data.rounds)
            total_rounds += rounds_count

            # Duration
            if step.data.end_time:
                duration = step.data.end_time - step.data.start_time
                if duration < 60:
                    duration_str = f"{duration:.1f}s"
                else:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    duration_str = f"{minutes}m {seconds:.1f}s"
            else:
                duration_str = "running"

            # Token counting (simplified)
            step_tokens = rounds_count * 100  # Rough estimate
            total_tokens += step_tokens

            step_node = steps_node.add(f"[dim]Step {i}:[/dim] \"{step_instruction}\" [{status_color}]{status}[/{status_color}]")
            step_node.add(f"[dim]    ⏱️ Duration:[/dim] {duration_str}")
            step_node.add(f"[dim]    🔄 Rounds:[/dim] {rounds_count}")
            step_node.add(f"[dim]    📊 Tokens:[/dim] ~{step_tokens}")

        # Total summary
        summary_node = steps_node.add("[bold]📈 Total[/bold]")
        summary_node.add(f"[dim]    🔄 Total Rounds:[/dim] {total_rounds}")
        summary_node.add(f"[dim]    📊 Estimated Tokens:[/dim] ~{total_tokens}")

    def _add_hierarchy_info(self, tree, subtask):
        """Add hierarchy information section"""
        hierarchy_node = tree.add("[bold blue]🏗️ Hierarchy[/bold blue]")

        # Parent information
        parent = getattr(subtask, 'parent', None)
        if parent:
            parent_instruction = parent.instruction[:30] + "..." if len(parent.instruction or "") > 30 else (parent.instruction or "Unknown Parent")
            parent_id = parent.task_id[:8] + "..." if len(parent.task_id) > 8 else parent.task_id
            hierarchy_node.add(f"[dim]👆 Parent:[/dim] \"{parent_instruction}\" (ID: {parent_id})")
        else:
            hierarchy_node.add("[dim]👆 Parent:[/dim] None (root task)")

        # Subtasks
        nested_count = len(getattr(subtask, 'subtasks', []))
        hierarchy_node.add(f"[dim]👶 Subtasks:[/dim] {nested_count} nested subtasks")

        # Position in parent (if we have parent info)
        if parent:
            siblings = len(getattr(parent, 'subtasks', []))
            position = next((i+1 for i, s in enumerate(getattr(parent, 'subtasks', [])) if s.task_id == subtask.task_id), 0)
            if position > 0:
                ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(position, f"{position}th")
                hierarchy_node.add(f"[dim]📍 Position:[/dim] {ordinal} subtask of parent")

    def _add_detailed_steps(self, tree, subtask):
        """Add detailed step information (optional)"""
        if not subtask.steps:
            return

        details_node = tree.add("[bold blue]🔍 Detailed Steps[/bold blue]")

        for i, step in enumerate(subtask.steps):
            step_node = details_node.add(f"[bold]Step {i}:[/bold] {step.data.instruction or 'Untitled Step'}")

            # Time details
            start_time = datetime.fromtimestamp(step.data.start_time)
            step_node.add(f"[dim]    ⏰ Started:[/dim] {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            if step.data.end_time:
                end_time = datetime.fromtimestamp(step.data.end_time)
                duration = step.data.end_time - step.data.start_time
                step_node.add(f"[dim]    🏁 Completed:[/dim] {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                step_node.add(f"[dim]    ⏳ Duration:[/dim] {duration:.1f}s")
            else:
                step_node.add("[dim]    🏁 Status:[/dim] Still running")

            # Rounds
            rounds_count = len(step.data.rounds)
            step_node.add(f"[dim]    🔄 Rounds:[/dim] {rounds_count}")

            if step.data.rounds:
                last_round = step.data.rounds[-1]
                # Add information about the last round if available
                if hasattr(last_round, 'response') and last_round.response:
                    response_preview = str(last_round.response)[:100] + "..." if len(str(last_round.response)) > 100 else str(last_round.response)
                    step_node.add(f"[dim]    💬 Last Response:[/dim] \"{response_preview}\"")
