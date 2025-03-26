#!/usr/bin/env python
# -*- coding: utf-8 -*-

import code
import builtins
from pathlib import Path

from rich import print
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.history import InMemoryHistory
from pygments.lexers.python import PythonLexer

from agent import Agent

class PythonCompleter(WordCompleter):
    def __init__(self, ai):
        names = ['exit()']
        names += [name for name in dir(builtins)]
        names += [f"ai.{attr}" for attr in dir(ai) if not attr.startswith('_')]
        super().__init__(names, ignore_case=True)

def main(args):
    print("[bold cyan]🚀 Python use - AIPython ([red]Quit with 'exit()'[/red])")
    if not args.config:
        path = Path(__file__).resolve().parent / 'aipython.toml'
    else:
        path = Path(args.config)
    ai = Agent(path)
    console = code.InteractiveConsole({'ai': ai})
    history = InMemoryHistory()

    while True:
        try:
            user_input = prompt(
                '>>> ',
                completer=PythonCompleter(ai),
                auto_suggest=AutoSuggestFromHistory(),
                lexer=PygmentsLexer(PythonLexer),
                history=history,
            )
            if user_input.strip() in {"exit()", "quit()"}:
                break
            console.push(user_input)
        except EOFError:
            print("[bold yellow]Exiting...")
            break
        except Exception as e:
            print(f"[bold red]Error: {e}")

if __name__ == "__main__":
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        return parser.parse_args()
    main(parse_args())
