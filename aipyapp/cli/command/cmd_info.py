import sys

from ... import T
from .base_parser import ParserCommand
from .utils import print_table

class InfoCommand(ParserCommand):
    name = 'info'
    description = T('System information')

    def execute(self, args):
        ctx = self.manager.context
        tm = ctx.tm
        settings = tm.settings

        info = [
            (T('Current configuration directory'), str(settings.config_dir)),
            (T('Current working directory'), str(tm.workdir)),
            (T('Current LLM'), repr(tm.client_manager.current)),
            (T('Current role'), '-' if settings.get('system_prompt') else tm.role_manager.current_role.name),
            (T('Current display style'), T(tm.display_manager.current_style)),
            ('Python', sys.executable),
            (T('Python version'), sys.version),
            (T('Python base prefix'), sys.base_prefix),
        ]

        print_table(info, title=T("System information"), headers=[T("Parameter"), T("Value")])
