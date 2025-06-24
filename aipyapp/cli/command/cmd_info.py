import sys

from ... import T
from .base import BaseCommand
from .utils import print_table

class InfoCommand(BaseCommand):
    name = 'info'
    description = 'Display system information'

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', help='Show detailed info')
        parser.add_argument('--format', choices=['json', 'text'], default='text', help='Output format')

    def execute(self, args):
        tm = self.manager.tm
        settings = tm.settings

        info = [
            (T('Current configuration directory'), str(settings.config_dir)),
            (T('Current working directory'), str(tm.workdir)),
            (T('Current LLM'), repr(tm.client_manager.current)),
            (T('Current role'), '-' if settings.get('system_prompt') else tm.tips_manager.current_tips.name),
            ('Python', sys.executable),
            (T('Python version'), sys.version),
            (T('Python base prefix'), sys.base_prefix),
        ]

        print_table(info, title=T("System information"), columns=[T("Parameter"), T("Value")])