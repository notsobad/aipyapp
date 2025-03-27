#!/usr/bin/env python
# -*- coding: utf-8 -*-

import code
import builtins
from pathlib import Path

from rich import print
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.history import FileHistory
from pygments.lexers.python import PythonLexer

from agent import Agent

class PythonCompleter(WordCompleter):
    def __init__(self, ai):
        names = ['exit()']
        names += [name for name in dir(builtins)]
        names += [f"ai.{attr}" for attr in dir(ai) if not attr.startswith('_')]
        super().__init__(names, ignore_case=True)

def main(args):
    console = Console(record=True)
    home = Path(__file__).resolve().parent
    console.print("[bold cyan]🚀 Python use - AIPython ([red]Quit with 'exit()'[/red])")

    if not args.config:
        path = home / 'aipython.toml'
    else:
        path = Path(args.config)
    ai = Agent(path, console=console)
    interp = code.InteractiveConsole({'ai': ai})

    completer = PythonCompleter(ai)
    lexer = PygmentsLexer(PythonLexer)
    auto_suggest = AutoSuggestFromHistory()
    history = FileHistory(str(Path.cwd() / 'history.txt'))
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

if __name__ == "__main__":
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        return parser.parse_args()
    main(parse_args())
