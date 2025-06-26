from ... import T
from .base import BaseCommand
from .utils import print_records

class TaskCommand(BaseCommand):
    name = 'task'
    description = T('Task operations')

    def add_subcommands(self, subparsers):
        subparsers.add_parser('list', help='List tasks')

    def cmd_list(self, args):
        rows = self.manager.tm.list_tasks()
        print_records(rows)

    def cmd(self, args):
        self.cmd_list(args)