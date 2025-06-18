from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style
import re

# 菜单 + 描述
main_menu = {
    'llm': '模型API',
    'role': '用户角色',
    'tips': '可用提示',
    'task': '任务列表'
}

class DotSyntaxCompleter(Completer):
    def __init__(self, tm):
        self.tm = tm
        self.roles = {tips.name: tips.role.short for tips in tm.tips_manager.tips.values()}
        self.tips = {}
        self.llms = tm.client_manager.names['enabled']

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        match = re.search(r'@(\w*)(?:\.(\w*))?$', text)
        if not match:
            return

        category, sub = match.groups()

        # 补全主菜单（输入了 @）
        if not category:
            for key, meta in main_menu.items():
                yield Completion(key, start_position=0, display_meta=meta)

        # 补全主菜单项（如 @ro）
        elif category and sub is None and not text.endswith('.'):
            for key, meta in main_menu.items():
                if key.startswith(category):
                    yield Completion(key, start_position=-len(category), display_meta=meta)

        # 补全子菜单项
        elif category == 'role':
            prefix_len = len(sub) if sub else 0
            for item, desc in self.roles.items():
                if sub is None or item.startswith(sub):
                    yield Completion(item, start_position=-prefix_len, display_meta=desc)
        elif category == 'tip':
            prefix_len = len(sub) if sub else 0
            for item, desc in self.tips.items():
                if sub is None or item.startswith(sub):
                    yield Completion(item, start_position=-prefix_len, display_meta=desc)
        elif category == 'llm':
            prefix_len = len(sub) if sub else 0
            for item in self.llms:
                if sub is None or item.startswith(sub):
                    yield Completion(item, start_position=-prefix_len, display_meta=item)
        elif category == 'task':
            prefix_len = len(sub) if sub else 0
            for task in self.tm.get_tasks():
                if sub is None or task.task_id.startswith(sub):
                    yield Completion(task.task_id, start_position=-prefix_len, display_meta=task.instruction)
# 样式
style = Style.from_dict({
    'completion-menu.completion': 'bg:#333333 #ffffff',
    'completion-menu.completion.current': 'bg:#ffffff #000000',
    'completion-menu.meta.completion': 'bg:#333333 #888888',
})

if __name__ == "__main__":
    while True:
        try:
            text = session.prompt(">>> ")
            print("You entered:", text)
        except (EOFError, KeyboardInterrupt):
            break
