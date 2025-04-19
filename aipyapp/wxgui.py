#!/usr/bin/env python
#coding: utf-8

import os
import sys
import time
import json
import queue
import traceback
import threading
import importlib.resources as resources

import wx
import wx.html2
import matplotlib
import matplotlib.pyplot as plt
from rich.console import Console
from wx.lib.newevent import NewEvent
from wx import FileDialog, FD_SAVE, FD_OVERWRITE_PROMPT

from . import __version__
from .aipy.config import ConfigManager
from .aipy import TaskManager, event_bus
from .aipy.i18n import T,set_lang

__PACKAGE_NAME__ = "aipyapp"
ChatEvent, EVT_CHAT = NewEvent()
AVATARS = {'我': '🧑', 'BB-8': '🤖', '图灵': '🧠', '爱派': '🐙'}

matplotlib.use('Agg')

class AIPython(threading.Thread):
    def __init__(self, gui):
        super().__init__(daemon=True)
        self.gui = gui
        self.tm = gui.tm
        plt.show = self.on_plt_show
        sys.modules["matplotlib.pyplot"] = plt

    def on_plt_show(self, *args, **kwargs):
        filename = f'{time.strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(filename)
        user = 'BB-8'
        content = f'![{filename}]({filename})'
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_display(self, path):
        user = '图灵'
        content = f'![图片]({path})'
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_response_complete(self, msg):
        user = '图灵' #msg['llm']
        #content = f"```markdown\n{msg['content']}\n```"
        evt = ChatEvent(user=user, msg=msg['content'])
        wx.PostEvent(self.gui, evt)

    def on_summary(self, summary):
        user = '爱派'
        evt = ChatEvent(user=user, msg=f'结束处理指令 {summary}')
        wx.PostEvent(self.gui, evt)

    def on_exec(self, blocks):
        user = 'BB-8'
        content = f"```python\n{blocks['main']}\n```"
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_result(self, result):
        user = 'BB-8'
        content = json.dumps(result, indent=4, ensure_ascii=False)
        content = f'运行结果如下\n```json\n{content}\n```'
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def run(self):
        event_bus.register("response_stream", self.on_response_complete)
        event_bus.register("exec", self.on_exec)
        event_bus.register("result", self.on_result)
        event_bus.register("summary", self.on_summary)
        event_bus.register("display", self.on_display)
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
        super().__init__(None, title=f"Python-use: AIPy (v{__version__})", size=(1024, 768))
        
        # 设置窗口背景色
        self.SetBackgroundColour(wx.Colour(245, 245, 245))
        
        self.tm = tm
        self.task_queue = queue.Queue()
        self.aipython = AIPython(self)
        self.current_llm = tm.llm.names['default']
        self.enabled_llm = list(tm.llm.names['enabled'])

        self.make_menu_bar()
        self.make_tool_bar()
        self.make_panel()
        self.CreateStatusBar(2)
        self.SetStatusWidths([-1, 50])
        self.GetStatusBar().SetStatusStyles([wx.SB_NORMAL, wx.SB_RAISED])
        self.update_status_llm()

        self.Bind(EVT_CHAT, self.on_chat)
        self.aipython.start()
        self.Show()

    def make_panel(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        html_file_path = os.path.abspath(resources.files(__PACKAGE_NAME__) / "chatroom.html")
        self.webview = wx.html2.WebView.New(panel)
        self.webview.LoadURL(f"file://{html_file_path}")
        self.webview.SetWindowStyleFlag(wx.BORDER_NONE)
        vbox.Add(self.webview, proportion=1, flag=wx.EXPAND | wx.ALL, border=12)

        self.input = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.input.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.input.SetForegroundColour(wx.Colour(33, 33, 33))
        self.input.SetMinSize((-1, 60))
        self.input.SetWindowStyleFlag(wx.BORDER_SIMPLE)
        self.input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        vbox.Add(self.input, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

        panel.SetSizer(vbox)
        self.panel = panel

    def make_tool_bar(self):
        toolbar = self.CreateToolBar(style=wx.TB_HORIZONTAL | wx.TB_TEXT | wx.BORDER_NONE)
        toolbar.SetBackgroundColour(wx.Colour(240, 240, 240))
        
        toolbar.AddStretchableSpace()
        
        label = wx.StaticText(toolbar, label="LLM:")
        toolbar.AddControl(label)
        
        self.choice = wx.Choice(toolbar, choices=self.enabled_llm)
        self.choice.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.choice.SetForegroundColour(wx.Colour(33, 33, 33))
        self.choice.SetStringSelection(self.current_llm)
        toolbar.AddControl(self.choice)
        
        self.choice.Bind(wx.EVT_CHOICE, self.on_choice_selected)
        
        toolbar.Realize()

    def make_menu_bar(self):
        menu_bar = wx.MenuBar()
        menu_bar.SetBackgroundColour(wx.Colour(240, 240, 240))
        
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_SAVE, "保存聊天记录为 HTML(&S)\tCtrl+S", "保存当前聊天记录为 HTML 文件")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "退出(&Q)\tCtrl+Q", "退出程序")
        self.Bind(wx.EVT_MENU, self.on_save_html, id=wx.ID_SAVE)
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

    def on_choice_selected(self, event):
        name = self.choice.GetStringSelection()
        if not self.tm.use(name):
            wx.MessageBox(f"LLM {name} 不可用", "警告", wx.OK|wx.ICON_WARNING)
            self.choice.SetStringSelection(self.current_llm)
        else:
            self.current_llm = name
        self.update_status_llm()
        event.Skip()
    
    def update_status_llm(self):
        selected = self.choice.GetStringSelection()
        self.SetStatusText(selected, 1)

    def on_exit(self, event):
        self.task_queue.put('exit')
        self.aipython.join()
        self.Close()

    def on_clear_chat(self, event):
        pass

    def on_open_website(self, event):
        if event.GetId() == self.ID_WEBSITE:
            url = "https://aipy.app"
        elif event.GetId() == self.ID_FORUM:
            url = "https://d.aipy.app"
        wx.LaunchDefaultBrowser(url)

    def on_save_html(self, event):
        js_code = "document.documentElement.outerHTML"
        try:
            result = self.webview.RunScript(js_code)
            if isinstance(result, tuple):
                html_content = result[1]
            else:
                html_content = result
            self.save_html_content(html_content)
        except Exception as e:
            wx.MessageBox(f"Error executing JavaScript: {e}", "Error")

    def save_html_content(self, html_content):
        with FileDialog(self, "保存聊天记录为 HTML 文件", wildcard="HTML 文件 (*.html)|*.html",
                        style=FD_SAVE | FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            path = dialog.GetPath()
            try:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(html_content)
            except IOError:
                wx.LogError(f"无法保存文件：{path}")

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
            wx.BeginBusyCursor()
            self.SetStatusText("操作进行中，请稍候...", 0)
        else:
            self.input.Show()
            wx.EndBusyCursor()
            self.SetStatusText("操作完成", 0)
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
        avatar = AVATARS[user]
        js_code = f'appendMessage("{avatar}", "{user}", {repr(text)});'
        self.webview.RunScript(js_code)

    def refresh_chat(self):
        wx.CallLater(100, lambda: self.browser.RunScript("window.scrollTo(0, document.body.scrollHeight);"))

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

    console = Console(quiet=True, record=True)
    try:
        tm = TaskManager(settings, console=console)
    except Exception as e:
        traceback.print_exc()
        return
    
    app = wx.App()
    ChatFrame(tm)
    app.MainLoop()
