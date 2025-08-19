import time
import os

from aipyapp.aipy.events import TypedEventBus
from aipyapp import T
from ..base import ParserCommand
from ..common import TaskModeResult
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
        parser.add_argument('--speed', type=float, default=1.0, help=T('Replay speed multiplier (default: 1.0)'))

    def cmd_list(self, args, ctx):
        rows = ctx.tm.list_tasks()
        table = record2table(rows)
        ctx.console.print(table)

    def get_arg_values(self, name, subcommand=None):
        if name == 'tid':
            tasks = self.manager.tm.get_tasks()
            return [(task.task_id, task.instruction[:32]) for task in tasks]
        elif name == 'path':
            return self._get_path_completions()
        return None

    def _get_path_completions(self, partial_path=''):
        """获取文件路径补齐选项 - 简化版本
        
        核心思想：
        1. 使用 glob 进行路径匹配，简单可靠
        2. 始终返回完整路径，避免复杂的路径拼接
        3. 优先显示 .json 文件和目录
        """
        import glob
        from pathlib import Path
        
        # 如果没有输入，列出当前目录
        if not partial_path:
            pattern = '*'
        else:
            # 如果以 / 结尾，列出该目录下的所有内容
            if partial_path.endswith(os.sep):
                pattern = partial_path + '*'
            else:
                # 否则进行前缀匹配
                pattern = partial_path + '*'
        
        # 使用 glob 获取匹配项
        matches = glob.glob(pattern)
        
        # 分类整理结果
        json_files = []
        directories = []
        other_files = []
        
        for match in matches:
            # 跳过隐藏文件
            if os.path.basename(match).startswith('.'):
                continue
            
            # 根据类型分类
            if os.path.isdir(match):
                # 目录不再自动添加 / 后缀
                # 这样用户输入 / 时会触发新的补齐
                directories.append((match, "📁 Directory"))
            elif match.endswith('.json'):
                json_files.append((match, "📄 JSON"))
            else:
                other_files.append((match, "📄 File"))
        
        # 按优先级排序：JSON 文件 > 目录 > 其他文件
        return json_files + directories + other_files
    
    def cmd_use(self, args, ctx):
        task = ctx.tm.get_task_by_id(args.tid)
        return TaskModeResult(task=task)

    def cmd_resume(self, args, ctx):
        task = ctx.tm.load_task(args.path)
        return TaskModeResult(task=task)

    def cmd_replay(self, args, ctx):
        task = ctx.tm.load_task(args.path)
        if not task.steps:
            ctx.console.print(T("No steps to replay"))
            return

        display = ctx.tm.display_manager.create_display_plugin()
        event_bus = TypedEventBus()
        event_bus.add_listener(display)
        
        for step in task.steps:
            prev_event = None
            for i, event in enumerate(step.events):
                # 计算等待时间
                if i > 0:
                    wait_time = (event.timestamp - prev_event.timestamp) 
                    if wait_time > 0:
                        time.sleep(wait_time)
                
                event_bus.emit_event(event)
                prev_event = event

    def cmd(self, args, ctx):
        self.cmd_list(args, ctx)