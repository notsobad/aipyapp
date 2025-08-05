import time
from pathlib import Path
import json

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

    def get_arg_values(self, arg, subcommand=None):
        if subcommand == 'use' and arg.name == 'tid':
            tasks = self.manager.tm.get_tasks()
            return [Completable(task.task_id, task.instruction[:32]) for task in tasks]
        return super().get_arg_values(arg, subcommand)
    
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