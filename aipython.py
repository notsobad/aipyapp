import code
import builtins

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.history import InMemoryHistory
from pygments.lexers.python import PythonLexer

from agent import Agent

# 自定义自动补全器（包含 Python 内置函数）
class PythonCompleter(WordCompleter):
    def __init__(self):
        super().__init__([name for name in dir(builtins)], ignore_case=True)


def main(args):
    load_dotenv(args.env)
    print("Python use - AIPython (Quit with 'exit()')")

    ai = Agent()
    ai.reset()
    context = {'ai': ai}
    console = code.InteractiveConsole(context)
    history = InMemoryHistory()

    while True:
        try:
            user_input = prompt(
                '>>> ',
                completer=PythonCompleter(),
                auto_suggest=AutoSuggestFromHistory(),
                lexer=PygmentsLexer(PythonLexer),
                history=history,
            )

            if user_input.strip() in {"exit()", "quit()"}:
                break
            console.push(user_input)
        except (EOFError, KeyboardInterrupt):  # 捕获 Ctrl-D 退出时显示消息，EOFError:
            print("Exiting...")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("--env", type=str, default=None, help="Environment file")
        return parser.parse_args()
    main(parse_args())
