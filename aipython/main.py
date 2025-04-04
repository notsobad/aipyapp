#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import code
import builtins
from pathlib import Path
import importlib.metadata
import importlib.resources as resources

from rich.console import Console
from dynaconf import Dynaconf
from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.history import FileHistory
from pygments.lexers.python import PythonLexer

from .aipy import Agent

__PACKAGE_NAME__ = "aipython"

class PythonCompleter(WordCompleter):
    def __init__(self, ai):
        names = ['exit()']
        names += [name for name in dir(builtins)]
        names += [f"ai.{attr}" for attr in dir(ai) if not attr.startswith('_')]
        super().__init__(names, ignore_case=True)

def get_version():
    try:
        return importlib.metadata.version('__PACKAGE_NAME__')
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
    
def get_default_config():
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    return str(default_config_path)

def main(args):
    console = Console(record=True)
    console.print(f"[bold cyan]🚀 Python use - AIPython v{get_version()} ([red]Quit with 'exit()'[/red])")

    path = args.config if args.config else 'aipython.toml'
    settings = Dynaconf(settings_files=[get_default_config(), path], envvar_prefix="AIPY", merge_enabled=True)
    try:
        ai = Agent(settings, console=console)
    except Exception as e:
        console.print_exception(e)
        console.print(f"[bold red]Error: {e}")
        return
    
    os.chdir(Path.cwd() / settings.workdir)
    interp = code.InteractiveConsole({'ai': ai})

    completer = PythonCompleter(ai)
    lexer = PygmentsLexer(PythonLexer)
    auto_suggest = AutoSuggestFromHistory()
    history = FileHistory(str(Path.cwd() / settings.history))
    session = PromptSession(history=history, completer=completer, lexer=lexer, auto_suggest=auto_suggest)
    while True:
        try:
            user_input = session.prompt(HTML('<ansiblue>>> </ansiblue>'))
            if user_input.strip() in {"exit()", "quit()"}:
                break
            interp.push(user_input)
        except EOFError:
            console.print("[bold yellow]Exiting...")
            break
        except Exception as e:
            console.print(f"[bold red]Error: {e}")

def run():
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        return parser.parse_args()
    main(parse_args())
