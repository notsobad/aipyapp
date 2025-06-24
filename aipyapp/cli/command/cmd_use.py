from ... import T
from .base import BaseCommand

class UseCommand(BaseCommand):
    name = 'use'
    description = 'Use a LLM or a role'

    def add_arguments(self, parser):
        tm = self.manager.tm
        names = tm.client_manager.names
        roles = {tips.name: tips.role.short for tips in tm.tips_manager.tips.values()}
        parser.add_argument('--llm', choices=names['enabled'], default=names['default'], help='Use a LLM')
        parser.add_argument('--role', choices=roles.keys(), help='Use a role')

    def execute(self, args):
        tm = self.manager.tm
        settings = tm.settings

        params = {}
        if args.llm:
            params['llm'] = args.llm
        if args.role:
            params['role'] = args.role
        if params:
            tm.use(**params)