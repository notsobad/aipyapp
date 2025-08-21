#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime

from .utils import row2table
from ..base import CommandMode, ParserCommand
from aipyapp import T

class StepsCommand(ParserCommand):
    """Steps command"""
    name = "step"
    description = T("Manage task steps")
    modes = [CommandMode.TASK]

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help=T('List task steps'))
        subparsers.add_parser('clear', help=T('Clear task steps'))
        parser = subparsers.add_parser('delete', help=T('Delete task steps'))
        parser.add_argument('index', type=int, help=T('Index of the task step to delete'))
        
    def get_arg_values(self, name, subcommand=None):
        if name == 'index':
            task = self.manager.context.task
            return [(str(index), step.title or step.instruction[:32]) for index, step in enumerate(task.steps)]
        return None
    
    def cmd(self, args, ctx):
        return self.cmd_list(args, ctx)
    
    def cmd_list(self, args, ctx):
        steps = ctx.task.steps
        if not steps:
            ctx.console.print(T("No task steps found"))
            return
        
        rows = []
        for i, step in enumerate(steps):
            start_time_s = datetime.fromtimestamp(step.start_time).strftime('%m-%d %H:%M')
            end_time_s = datetime.fromtimestamp(step.end_time).strftime('%m-%d %H:%M') if step.end_time else ''
            rows.append([i, step.title or step.instruction[:32], len(step.rounds), len(step.blocks), start_time_s, end_time_s])
        table = row2table(rows, title=T('Task Steps'), headers=[T('Index'), T('Title'), T('Rounds'), T('Blocks'), T('Start Time'), T('End Time')])
        ctx.console.print(table)
    
    def cmd_clear(self, args, ctx):
        task = ctx.task
        ret = task.clear_steps()
        if ret:
            ctx.console.print(T("Task steps cleared"))
        else:
            ctx.console.print(T("Failed to clear task steps"))
        return ret
    
    def cmd_delete(self, args, ctx):
        task = ctx.task
        ret = task.delete_step(args.index)
        if ret:
            ctx.console.print(T("Task step deleted"))
        else:
            ctx.console.print(T("Failed to delete task step"))
        return ret