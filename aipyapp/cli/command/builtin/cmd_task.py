import time

from aipyapp.aipy.events import TypedEventBus
from aipyapp import T
from ..base import ParserCommand
from ..common import TaskModeResult
from ..completer.base import CompleterBase
from ..completer.argparse_completer import EnhancedArgparseCompleter
from .utils import record2table

class TaskCommand(ParserCommand):
    name = 'task'
    description = T('Task operations')

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help=T('List recent tasks'))
        parser = subparsers.add_parser('use', help=T('Load a recent task by task id'))
        parser.add_argument('tid', type=str, help=T('Task ID'))
        parser = subparsers.add_parser('resume', help=T('Load task from task.json file'))
        parser.add_argument('path', type=str, help=T('Path to task.json file'))
        parser = subparsers.add_parser('replay', help=T('Replay task from task.json file'))
        parser.add_argument('path', type=str, help=T('Path to task.json file'))
        parser.add_argument('--speed', type=float, default=1.0, help=T('Replay speed multiplier'))

    def _create_completer(self) -> CompleterBase:
        """创建任务命令的自定义补齐器"""
        return EnhancedArgparseCompleter(self)

    def cmd_list(self, args, ctx):
        rows = ctx.tm.list_tasks()
        if rows:
            table = record2table(rows)
            ctx.console.print(table)

    def get_arg_values(self, name, subcommand=None, partial=None):
        """为 tid 参数提供补齐值，path 参数由 PathCompleter 处理"""
        if name == 'tid':
            tasks = self.manager.context.tm.get_tasks()
            return [(task.task_id, task.instruction[:32]) for task in tasks]
        return None

    def cmd_use(self, args, ctx):
        task = ctx.tm.get_task_by_id(args.tid)
        return TaskModeResult(task=task)

    def cmd_resume(self, args, ctx):
        task = ctx.tm.load_task(args.path)
        return TaskModeResult(task=task)

    def _replay_task(self, event_bus, task, speed=1.0):
        if not task.steps:
            return

        prev_event = None
        subtask_index = 0
        for i, event in enumerate(task.events):
            # 计算等待时间
            if i > 0:
                wait_time = (event.timestamp - prev_event.timestamp) / speed
                if wait_time > 0:
                    time.sleep(wait_time)
            
            event_bus.emit_event(event)

            if event.name == 'tool_call_started' and event.tool_call.name == 'SubTask':
                event = self._replay_task(event_bus, task.subtasks[subtask_index], speed)
                subtask_index += 1
            prev_event = event
        return event

    def cmd_replay(self, args, ctx):
        task = ctx.tm.load_task(args.path)
        if not task.steps:
            ctx.console.print(T("No steps to replay"))
            return

        display = ctx.tm.display_manager.create_display_plugin()
        event_bus = TypedEventBus()
        event_bus.add_listener(display)
        speed = args.speed if args.speed > 0 else 1.0
        
        self._replay_task(event_bus, task, speed)

    def cmd(self, args, ctx):
        self.cmd_list(args, ctx)