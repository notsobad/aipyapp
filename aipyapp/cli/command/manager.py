import code
import shlex
import argparse

from .base import BaseCommand
from .cmd_info import InfoCommand
from .cmd_help import HelpCommand
from .cmd_llm import LLMCommand
from .cmd_use import UseCommand
from .cmd_env import EnvCommand
from .cmd_task import TaskCommand
from .cmd_mcp import MCPCommand

from loguru import logger
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings

COMMANDS = [InfoCommand, HelpCommand, LLMCommand, UseCommand, EnvCommand, TaskCommand, MCPCommand]

class CommandManager(Completer):
    def __init__(self, tm):
        self.tm = tm
        self.commands = {}
        self.log = logger.bind(src="CommandManager")
        self.init()

    def init(self):
        """Initialize all registered commands"""
        for command in COMMANDS:
            self.register_command(command())
        
        for command in self.commands.values():
            command.init()

    def register_command(self, command_instance):
        """Register a command instance"""
        if not isinstance(command_instance, BaseCommand):
            raise ValueError("Command must be an instance of BaseCommand")
        if command_instance.name in self.commands:
            raise ValueError(f"Command '{command_instance.name}' is already registered")
        self.commands[command_instance.name] = command_instance
        command_instance.manager = self

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith('/'):
            return
        
        text = text[1:]
        words = shlex.split(text)
        
        if len(words) == 0 or (len(words) == 1 and not text.endswith(' ')):
            # Complete main commands
            partial_cmd = words[0] if len(words) > 0 else ''
            for cmd in self.commands.keys():
                command_instance = self.commands[cmd]
                if cmd.startswith(partial_cmd):
                    yield Completion(
                        cmd,
                        start_position=-len(words[0]) if words else -len(text),
                    display_meta=command_instance.description or ''
                )
            return
                
        cmd = words[0]
        if cmd not in self.commands:
            return
        
        command_instance = self.commands[cmd]
        subcommands = command_instance.subcommands
        
        # Complete subcommands
        if subcommands:
            if len(words) == 1 or (len(words) == 2 and not text.endswith(' ')):
                partial_subcmd = words[1] if len(words) > 1 else ''
                for subcmd, info in subcommands.items():
                    if subcmd.startswith(partial_subcmd):
                        yield Completion(
                            subcmd,
                            start_position=-len(partial_subcmd),
                            display_meta=info['help'] or ''
                        )
                return
            
            subcmd = words[1]
            if subcmd not in subcommands:
                return
            arguments = subcommands[subcmd]['arguments']
        else:
            arguments = command_instance.arguments
        
        if text.endswith(' '):
            partial_arg = ''
            last_word = words[-1]
        else:
            partial_arg = words[-1]
            last_word = words[-2]

        arg = arguments.get(last_word, None)
        if arg and arg['requires_value']:
            if arg['choices']:
                for choice in arg['choices']:
                    if choice.startswith(partial_arg):
                        yield Completion(
                            choice,
                            start_position=-len(partial_arg),
                        )
            return
        
        for arg, info in arguments.items():
            if arg.startswith(partial_arg) and arg not in words:
                yield Completion(
                    arg,
                    start_position=-len(partial_arg),
                    display_meta=info['help'] or ''
                )
 

    def execute(self, user_input):
        """Execute a command"""
        if not user_input.startswith('/'):
            return
        
        user_input = user_input[1:].strip()
        if not user_input:
            return
        
        args = shlex.split(user_input)
        command = args[0]
        if command not in self.commands:
            print(f"Unknown command: {command}")
            return
        
        command_instance = self.commands[command]
        parser = command_instance.parser
        
        try:
            # Parse remaining arguments (excluding the command name)
            parsed_args = parser.parse_args(args[1:])
            parsed_args.raw_args = args[1:]
            command_instance.execute(parsed_args)
        except SystemExit:
            pass
        except argparse.ArgumentError as e:
            print(f"Argument error: {e}")
        except Exception as e:
            print(f"Error: {e}")