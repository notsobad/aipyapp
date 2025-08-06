import time
from pathlib import Path
import json
import os
import shlex

from rich.panel import Panel

from ... import T, EventBus
from ...aipy.event_serializer import EventSerializer
from .base import Completable
from .base_parser import ParserCommand
from .utils import print_records


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
        print_records(rows)

    def get_arg_values(self, arg, subcommand=None, partial_value=''):
        if subcommand == 'use' and arg.name == 'tid':
            tasks = self.manager.tm.get_tasks()
            return [Completable(task.task_id, task.instruction[:32]) for task in tasks]
        elif subcommand in ('resume', 'replay') and arg.name == 'path':
            return self._get_path_completions(partial_value)
        return super().get_arg_values(arg, subcommand)

    def _get_path_completions(self, partial_path=''):
        """获取文件路径补齐选项，优先显示 .json 文件"""
        completions = []
        
        # 处理可能包含引号的路径输入
        try:
            # 尝试解析引号，如果失败则使用原始输入
            unquoted_path = shlex.split(partial_path)[0] if partial_path else ''
        except ValueError:
            # 如果引号不匹配，使用原始输入
            unquoted_path = partial_path
        
        # 如果是空输入或相对路径，从当前目录开始
        if not unquoted_path or not os.path.isabs(unquoted_path):
            search_dir = os.getcwd()
            if unquoted_path:
                # 处理相对路径
                if os.sep in unquoted_path:
                    search_dir = os.path.join(search_dir, os.path.dirname(unquoted_path))
                    prefix = os.path.basename(unquoted_path)
                else:
                    prefix = unquoted_path
            else:
                prefix = ''
        else:
            # 绝对路径
            search_dir = os.path.dirname(unquoted_path)
            prefix = os.path.basename(unquoted_path)
        
        try:
            if os.path.isdir(search_dir):
                items = os.listdir(search_dir)
                
                # 分别收集文件和目录
                json_files = []
                other_files = []
                directories = []
                
                for item in items:
                    if not item.startswith('.') and item.startswith(prefix):
                        full_path = os.path.join(search_dir, item)
                        # 处理包含空格的文件名，使用引号包装
                        display_name = shlex.quote(item) if ' ' in item else item
                        
                        if os.path.isdir(full_path):
                            # 对于目录，在引号内添加 / 后缀
                            if ' ' in item:
                                display_name = shlex.quote(item + '/')
                            else:
                                display_name = item + '/'
                            directories.append(Completable(display_name, f"Directory"))
                        elif item.endswith('.json'):
                            json_files.append(Completable(display_name, f"JSON file"))
                        else:
                            other_files.append(Completable(display_name, f"File"))
                
                # 优先显示 JSON 文件，然后目录，最后其他文件
                completions = json_files + directories + other_files
        except (OSError, PermissionError):
            # 如果无法访问目录，返回空列表
            pass
        
        return completions
    
    def cmd_use(self, args, ctx):
        task = ctx.tm.get_task_by_id(args.tid)
        return task

    def _load_task_data(self, path):
        task_file = Path(path)
        if not task_file.exists():
            raise FileNotFoundError(f"Task file not found: {path}")
        if not task_file.name.endswith('.json'):
            raise ValueError("Task file must be a .json file")
        
        # 读取任务数据
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")
        return task_data
    
    def cmd_resume(self, args, ctx):
        """从 task.json 文件加载任务"""
        task_data = self._load_task_data(args.path)
        
        # 将任务添加到任务管理器中
        task = ctx.tm.load_task(task_data)
        return task

    def cmd_replay(self, args, ctx):
        """重放任务"""
        task_data = self._load_task_data(args.path)
        
        # 显示重放信息
        instruction = task_data.get('instruction')
        task_id = task_data.get('task_id')
        events = task_data.get('events', [])
        events_count = len(events)
        
        panel = Panel(
            f"🎬 Task Replay\n\n"
            f"Task ID: {task_id}\n"
            f"Instruction: {instruction}\n"
            f"Events: {events_count}\n"
            f"Speed: {args.speed}x",
            title="Replay Mode",
            border_style="cyan"
        )
        ctx.console.print(panel)
        
        if events:
            self._replay_events(ctx, events, args.speed)

    def _replay_events(self, ctx, events, speed):
        """简化的事件重放 - 直接按时间间隔触发事件"""
        display = ctx.tm.display_manager.get_current_plugin()
        event_bus = EventBus()
        event_bus.add_listener(display)

        # 反序列化事件中的对象
        replay_events = EventSerializer.deserialize_events(events)

        for i, event in enumerate(replay_events):
            # 检查是否是 round_start 事件，需要用户确认
            if event['type'] == 'round_start':
                if not self._confirm_round_start(ctx,event):
                    print("\n🛑 重放已取消")
                    return
            
            # 计算等待时间
            if i > 0:
                prev_event = replay_events[i - 1]
                wait_time = (event['relative_time'] - prev_event['relative_time']) / speed
                if wait_time > 0:
                    time.sleep(wait_time)
            
            event_name = event['type']
            event_data = event['data'].copy() if isinstance(event['data'], dict) else {}
            
            event_bus.emit(event_name, **event_data)

    def _confirm_round_start(self, ctx, event):
        """在 round_start 事件时提示用户确认是否继续"""
        console = ctx.console
        data = event.get('data', {})
        
        # 获取 step 信息
        round_num = data.get('round', 'Unknown')
        instruction = data.get('instruction', 'Unknown instruction')
        
        # 显示提示面板
        panel = Panel(
            f"📋 即将重放 Step {round_num}\n\n"
            f"指令: {instruction}\n\n"
            f"⚠️  继续重放此步骤吗？",
            title="🔄 Step 重放确认",
            border_style="yellow"
        )
        console.print(panel)
        
        # 等待用户输入
        try:
            while True:
                choice = console.input("\n请选择 [y/n]: ").lower().strip()
                if choice in ['y', 'yes', '是']:
                    console.print("✅ 继续重放...")
                    return True
                elif choice in ['n', 'no', '否']:
                    return False
                else:
                    console.print("❓ 请输入 'y' 继续或 'n' 取消")
        except KeyboardInterrupt:
            console.print("\n\n❌ 用户中断，取消重放")
            return False
        except EOFError:
            # 处理非交互式环境（如自动化测试）
            console.print("\n⚠️  检测到非交互式环境，自动继续重放")
            return True

    def cmd(self, args, ctx):
        self.cmd_list(args, ctx)