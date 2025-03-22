import code
import builtins

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer

from agent import Agent

# 自定义自动补全器（包含 Python 内置函数）
class PythonCompleter(WordCompleter):
    def __init__(self):
        super().__init__([name for name in dir(builtins)], ignore_case=True)

class CustomConsole(code.InteractiveConsole):
    def __init__(self):
        # 使用单个 exec() 初始化 context 中的模块
        context = {}
        exec("""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
""", context)

        # 传递初始化后的 context 给 InteractiveConsole
        super().__init__(context)

    def __call__(self, code_str):
        # 使用 exec() 执行传入的代码字符串
        self.push(code_str)

    def __getattr__(self, name):
        # 如果属性是 context 中的模块或变量，则返回
        # 使用 locals() 来避免递归
        if name in self.locals:
            return self.locals[name]
        # 如果访问的是 console 本身的属性，则抛出 AttributeError
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


def main(args):
    load_dotenv(args.env)
    print("Python use - AIPython (Quit with 'exit()')")

    ai = Agent()
    context = {'ai': ai}
    console = code.InteractiveConsole(context)

    while True:
        try:
            user_input = prompt(
                '>>> ',
                completer=PythonCompleter(),
                auto_suggest=AutoSuggestFromHistory(),
                lexer=PygmentsLexer(PythonLexer),
            )

            if user_input.strip() in {"exit()", "quit()"}:
                break
            console.push(user_input)
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("--env", type=str, default=None, help="Environment file")
        return parser.parse_args()
    main(parse_args())
