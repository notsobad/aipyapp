from ... import T
from .base import Completable
from .base_parser import ParserCommand
from .utils import print_records

class TaskCommand(ParserCommand):
    name = 'task'
    description = T('Task operations')

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help='List tasks')
        parser = subparsers.add_parser('use', help='Load an old task')
        parser.add_argument('tid', type=str, help='Task ID')

    def cmd_list(self, args, ctx):
        rows = ctx.tm.list_tasks()
        print_records(rows)

    def get_arg_values(self, arg, subcommand=None):
        if subcommand == 'use' and arg.name == 'tid':
            tasks = self.manager.tm.get_tasks()
            return [Completable(task.task_id, task.instruction) for task in tasks]
        return super().get_arg_values(arg, subcommand)
    
    def cmd_use(self, args, ctx):
        ctx.tm.use(task=args.tid)
        self.log.info(f'Use task: {args.tid}')

    def cmd(self, args, ctx):
        self.cmd_list(args, ctx)