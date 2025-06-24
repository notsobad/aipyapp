import argparse
from collections import OrderedDict

def requires_value(action):
    ret = (
        action.nargs is not None or
        (action.type is not None and action.type != bool) or
        action.choices is not None
    )
    return ret

class BaseCommand:
    """Base class for all commands"""
    name: str = ''
    description: str = ''

    def __init__(self):
        self.parser = None
        self.manager = None
        self.arguments = None
        self.subcommands = None

    def init(self):
        """Initialize the command, can be overridden by subclasses"""
        parser = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.add_arguments(parser)
        if hasattr(self, 'add_subcommands'):
            subparsers = parser.add_subparsers(dest='subcommand')
            self.add_subcommands(subparsers)

        arguments = OrderedDict()
        for action in parser._actions:
            if action.dest != 'help':
                for option in action.option_strings:
                    arguments[option] = {
                        'help': action.help or '',
                        'choices': action.choices or None,
                        'requires_value': requires_value(action)
                    }

        subcommands = OrderedDict()
        for action in parser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue

            for subaction in action._get_subactions():
                cmd_name = subaction.dest or subaction.name
                subcommands[cmd_name] = {
                    'help': subaction.help or '',
                    'arguments': {}
                }
            
            for subcmd, subparser in action.choices.items():
                sub_arguments = OrderedDict()
                for sub_action in subparser._actions:
                    if sub_action.dest != 'help':
                        for option in sub_action.option_strings:
                            sub_arguments[option] = {
                                'help': sub_action.help or '',
                                'choices': sub_action.choices or None,
                                'requires_value': requires_value(sub_action)
                            }
                subcommands[subcmd]['arguments'] = sub_arguments

        self.parser = parser
        self.arguments = arguments
        self.subcommands = subcommands

    def add_arguments(self, parser):
        """Add command-specific arguments to the parser"""
        pass
    
    def execute(self, args):
        """Execute the command with parsed arguments"""
        raise NotImplementedError("execute method must be implemented")

