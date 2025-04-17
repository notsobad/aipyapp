#!/usr/bin/env python
#coding: utf-8

import json
import queue
import traceback
import threading
from pathlib import Path
import importlib.resources as resources

import wx
import wx.html2
from wx.lib.newevent import NewEvent
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, TextLexer
from wx import FileDialog, FD_SAVE, FD_OVERWRITE_PROMPT
from rich.console import Console

from . import __version__
from .aipy.config import ConfigManager
from .aipy import TaskManager, event_bus
from .aipy.i18n import T,set_lang

__PACKAGE_NAME__ = "aipyapp"

ChatEvent, EVT_CHAT = NewEvent()

AVATARS = {'我': '🧑', 'Python': '🤖', 'llm': '🧠'}

CHAT_CSS = """
body {
    font-family: sans-serif;
    font-size: 14px;
}
.message {
    display: flex;
    align-items: flex-start;
    margin: 10px 0;
}
.message .emoji {
    font-size: 24px;
    margin-right: 10px;
    line-height: 1;
}
.message div {
    word-wrap: break-word; /* 自动折行 */
    white-space: normal;   /* 保证文本折行并且不增加多余空白行 */
}
.message pre {
    background: #f0f0f0;
    padding: 6px;
    border-radius: 6px;
    word-wrap: break-word;  /* 自动折行 */
    white-space: pre-wrap;  /* 保留换行符并自动折行 */
}
"""

class AIPython(threading.Thread):
    def __init__(self, gui):
        super().__init__(daemon=True)
        self.gui = gui
        self.tm = gui.tm

    def on_response_complete(self, msg):
        user = msg['llm']
        #content = f"```markdown\n{msg['content']}\n```"
        evt = ChatEvent(user=user, msg=msg['content'])
        wx.PostEvent(self.gui, evt)

    def on_exec(self, blocks):
        user = 'Python'
        content = f"```python\n{blocks['main']}\n```"
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_result(self, result):
        user = 'Python'
        content = json.dumps(result, indent=4, ensure_ascii=False)
        content = f'运行结果如下\n```json\n{content}\n```'
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def run(self):
        event_bus.register("response_complete", self.on_response_complete)
        event_bus.register("exec", self.on_exec)
        event_bus.register("result", self.on_result)
        while True:
            instruction = self.gui.get_task()
            if instruction in ('/done', 'done'):
                self.tm.done()
            elif instruction in ('/exit', 'exit'):
                break
            else:
                try:
                    self.tm(instruction)
                except Exception as e:
                    traceback.print_exc()
            wx.CallAfter(self.gui.toggle_input)

class ChatFrame(wx.Frame):
    def __init__(self, tm):
        super().__init__(None, title=f"Python-use: AIPy (v{__version__})", size=(800, 600))

        self.tm = tm
        self.task_queue = queue.Queue()
        self.make_menu_bar()
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 消息展示区域
        self.browser = wx.html2.WebView.New(panel)
        vbox.Add(self.browser, 1, wx.EXPAND | wx.ALL, 5)

        # 消息输入框
        self.input = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.input.SetBackgroundColour(wx.Colour(255, 255, 255))  # 白色背景
        self.input.SetForegroundColour(wx.Colour(0, 0, 0))        
        vbox.Add(self.input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 绑定键盘事件
        self.input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        panel.SetSizer(vbox)
        self.messages_md = []  # 原始 Markdown 消息
        self.rendered_messages = []  # 渲染后的 HTML 消息
        self.panel = panel

        # 注册事件回调
        self.Bind(EVT_CHAT, self.on_chat)

        self.aipython = AIPython(self)
        self.aipython.start()

        self.Show()

    def make_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(wx.ID_SAVE, "保存聊天记录为 Markdown(&S)\tCtrl+S", "保存当前聊天记录为 Markdown 文件")
        menu_item = file_menu.Append(wx.ID_ANY, "保存聊天记录为 HTML(&H)", "保存当前聊天记录为 HTML 文件")
        self.Bind(wx.EVT_MENU, self.on_save_html, menu_item)
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "退出(&Q)\tCtrl+Q", "退出程序")
        self.Bind(wx.EVT_MENU, self.on_save_markdown, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)

        edit_menu = wx.Menu()
        edit_menu.Append(wx.ID_CLEAR, "清空聊天(&C)", "清除所有消息")
        self.Bind(wx.EVT_MENU, self.on_clear_chat, id=wx.ID_CLEAR)

        help_menu = wx.Menu()
        self.ID_WEBSITE = wx.NewIdRef()
        menu_item = wx.MenuItem(help_menu, self.ID_WEBSITE, "官网(&W)\tCtrl+W", "打开官方网站")
        help_menu.Append(menu_item)
        self.ID_FORUM = wx.NewIdRef()
        menu_item = wx.MenuItem(help_menu, self.ID_FORUM, "论坛(&W)\tCtrl+W", "打开官方论坛")
        help_menu.Append(menu_item)
        self.Bind(wx.EVT_MENU, self.on_open_website, id=self.ID_WEBSITE)
        self.Bind(wx.EVT_MENU, self.on_open_website, id=self.ID_FORUM)

        menu_bar.Append(file_menu, "文件(&F)")
        menu_bar.Append(edit_menu, "编辑(&E)")
        menu_bar.Append(help_menu, "帮助(&H)")

        self.SetMenuBar(menu_bar)

    def on_exit(self, event):
        self.task_queue.put('exit')
        self.aipython.join()
        self.Close()

    def on_clear_chat(self, event):
        self.messages_md.clear()
        self.rendered_messages.clear()
        self.refresh_chat()

    def on_open_website(self, event):
        if event.GetId() == self.ID_WEBSITE:
            url = "https://aipy.app"
        elif event.GetId() == self.ID_FORUM:
            url = "https://d.aipy.app"
        wx.LaunchDefaultBrowser(url)
            
    def on_save_markdown(self, event):
        with FileDialog(self, "保存聊天记录为 Markdown 文件", wildcard="Markdown 文件 (*.md)|*.md",
                        style=FD_SAVE | FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            path = dialog.GetPath()
            try:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write("\n\n---\n\n".join(self.messages_md))
            except IOError:
                wx.LogError(f"无法保存文件：{path}")

    def on_save_html(self, event):
        with FileDialog(self, "保存聊天记录为 HTML 文件", wildcard="HTML 文件 (*.html)|*.html",
                        style=FD_SAVE | FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            path = dialog.GetPath()
            try:
                with open(path, 'w', encoding='utf-8') as file:
                    html_content = self.generate_chat_html()
                    file.write(html_content)
            except IOError:
                wx.LogError(f"无法保存文件：{path}")

    def generate_chat_html(self):
        content_html = "<hr>".join(self.rendered_messages)
        style = HtmlFormatter().get_style_defs('.highlight')

        full_html = f"""
        <html>
        <head>
        <meta charset="utf-8">
        <style>{style}</style>
        <style>{CHAT_CSS}</style>
        </head>
        <body>
        {content_html}
        </body>
        </html>
        """

        return full_html

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        send_shortcut = (event.ControlDown() or event.CmdDown()) and keycode == wx.WXK_RETURN

        if send_shortcut:
            self.send_message()
        else:
            event.Skip()

    def get_task(self):
        return self.task_queue.get()

    def toggle_input(self):
        if self.input.IsShown():
            self.input.Hide()
        else:
            self.input.Show()
        self.panel.Layout()
        self.panel.Refresh()

    def send_message(self):
        text = self.input.GetValue().strip()
        if not text:
            return

        self.append_message('我', text)
        self.input.Clear()
        self.toggle_input()
        self.task_queue.put(text)

    def on_chat(self, event):
        user = event.user
        text = event.msg
        self.append_message(user, text)

    def append_message(self, user, text):
        msg = f"{user}\n{text}"
        avatar = AVATARS.get(user) or AVATARS['llm']

        html_body = self.convert_markdown_to_html(text)
        html = f'''
            <div class="message">
                <div class="emoji">{avatar}</div>
                <div><b>{user}：</b><br>{html_body}</div>
            </div>
        '''
        self.rendered_messages.append(html)
        self.messages_md.append(msg)
        self.refresh_chat()

    def refresh_chat(self):
        content_html = "<hr>".join(self.rendered_messages)
        style = HtmlFormatter().get_style_defs('.highlight')

        full_html = f"""
        <html>
        <head>
        <meta charset=\"utf-8\">
        <style>{style}</style>
        <style>{CHAT_CSS}</style>
        </head>
        <body>
        {content_html}
        </body>
        </html>
        """

        self.browser.SetPage(full_html, "")
        wx.CallLater(100, lambda: self.browser.RunScript("window.scrollTo(0, document.body.scrollHeight);"))

    def convert_markdown_to_html(self, md_text):
        def pygments_highlight(code, lang, attrs=None):
            try:
                lexer = get_lexer_by_name(lang)
            except Exception:
                lexer = TextLexer()
            formatter = HtmlFormatter(nowrap=True)
            return f'<pre class="highlight"><code>{highlight(code, lexer, formatter)}</code></pre>'

        md = MarkdownIt("commonmark", {
            "highlight": pygments_highlight
        })
        return md.render(md_text)


def main(args):
    path = args.config if args.config else 'aipy.toml'
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    conf = ConfigManager(default_config_path, path)
    conf.check_config()
    settings = conf.get_config()

    settings.auto_install = True
    settings.auto_getenv = True

    lang = settings.get('lang')
    if lang: set_lang(lang)

    try:
        tm = TaskManager(settings, console=Console())
    except Exception as e:
        traceback.print_exc()
        return
    
    app = wx.App()
    ChatFrame(tm)
    app.MainLoop()
