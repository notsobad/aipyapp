#!/usr/bin/env python
#coding: utf-8

import os
import sys
import time
import json
import queue
import base64
import mimetypes
import traceback
import threading
import importlib.resources as resources
import subprocess

import wx
import wx.html2
import matplotlib
import matplotlib.pyplot as plt
from loguru import logger
from rich.console import Console
from wx.lib.newevent import NewEvent
from wx import FileDialog, FD_SAVE, FD_OVERWRITE_PROMPT

from . import __version__
from .aipy.config import ConfigManager, CONFIG_DIR
from .aipy import TaskManager, event_bus
from .aipy.i18n import T, set_lang, __lang__
from .gui import TrustTokenAuthDialog, ConfigDialog, ApiMarketDialog, show_provider_config
from .config import LLMConfig

__PACKAGE_NAME__ = "aipyapp"
ChatEvent, EVT_CHAT = NewEvent()


matplotlib.use('Agg')

def image_to_base64(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        return None

    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        return None

    data_url = f"data:{mime_type};base64,{encoded_string}"
    return data_url

class AIPython(threading.Thread):
    def __init__(self, gui):
        super().__init__(daemon=True)
        self.gui = gui
        self.tm = gui.tm
        self._busy = threading.Event()
        plt.show = self.on_plt_show
        sys.modules["matplotlib.pyplot"] = plt

    def can_done(self):
        return not self._busy.is_set() and self.tm.busy

    def on_plt_show(self, *args, **kwargs):
        filename = f'{time.strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(filename)
        user = 'BB-8'
        content = f'![{filename}]({filename})'
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_display(self, image):
        user = T('Turing')
        if image['path']:
            base64_data = image_to_base64(image['path'])
            content = base64_data if base64_data else image['path']
        else:
            content = image['url']

        msg = f'![图片]({content})'
        evt = ChatEvent(user=user, msg=msg)
        wx.PostEvent(self.gui, evt)

    def on_response_complete(self, msg):
        user = T('Turing') #msg['llm']
        #content = f"```markdown\n{msg['content']}\n```"
        evt = ChatEvent(user=user, msg=msg['content'])
        wx.PostEvent(self.gui, evt)

    def on_summary(self, summary):
        user = T('AIPy')
        evt = ChatEvent(user=user, msg=f'{T("End processing instruction")} {summary}')
        wx.PostEvent(self.gui, evt)

    def on_exec(self, blocks):
        user = 'BB-8'
        content = f"```python\n{blocks['main']}\n```"
        evt = ChatEvent(user=user, msg=content)
        wx.PostEvent(self.gui, evt)

    def on_result(self, result):
        user = 'BB-8'
        content = json.dumps(result, indent=4, ensure_ascii=False)
        content = f'{T("Run result")}\n```json\n{content}\n```'
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
                    self._busy.set()
                    self.tm(instruction)
                except Exception as e:
                    traceback.print_exc()
                finally:
                    self._busy.clear()
                wx.CallAfter(self.gui.toggle_input)

class CStatusBar(wx.StatusBar):
    def __init__(self, parent):
        super().__init__(parent, style=wx.STB_DEFAULT_STYLE)
        self.parent = parent
        self.SetFieldsCount(3)
        self.SetStatusWidths([-1, 30, 80])

        self.tm = parent.tm
        self.current_llm = self.tm.llm.names['default']
        self.enabled_llm = list(self.tm.llm.names['enabled'])
        self.menu_items = self.enabled_llm
        self.radio_group = []

        self.folder_button = wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_FOLDER_OPEN, wx.ART_MENU))
        self.folder_button.Bind(wx.EVT_LEFT_DOWN, self.on_open_work_dir)
        self.Bind(wx.EVT_SIZE, self.on_size)

        self.SetStatusText(f"{self.current_llm} ▾", 2)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_click)

    def on_size(self, event):
        rect = self.GetFieldRect(1)
        self.folder_button.SetPosition((rect.x + 5, rect.y + 2))
        event.Skip()

    def on_click(self, event):
        rect = self.GetFieldRect(2)
        if rect.Contains(event.GetPosition()):
            self.show_menu()

    def show_menu(self):
        self.current_menu = wx.Menu()
        self.radio_group = []
        for label in self.menu_items:
            item = wx.MenuItem(self.current_menu, wx.ID_ANY, label, kind=wx.ITEM_RADIO)
            self.current_menu.Append(item)
            self.radio_group.append(item)
            self.Bind(wx.EVT_MENU, self.on_menu_select, item)
            if label == self.current_llm:
                item.Check()
        rect = self.GetFieldRect(2)
        pos = self.ClientToScreen(rect.GetBottomLeft())
        self.PopupMenu(self.current_menu, self.ScreenToClient(pos))

    def on_menu_select(self, event):
        item = self.current_menu.FindItemById(event.GetId())
        label = item.GetItemLabel()
        if self.tm.use(label):
            self.current_llm = label
            self.SetStatusText(f"{label} ▾", 2)
        else:
            wx.MessageBox(T('LLM {} is not available').format(label), T('Warning'), wx.OK|wx.ICON_WARNING)

    def on_open_work_dir(self, event):
        """打开工作目录"""
        work_dir = self.tm.workdir
        if os.path.exists(work_dir):
            if sys.platform == 'win32':
                os.startfile(work_dir)
            elif sys.platform == 'darwin':
                subprocess.call(['open', work_dir])
            else:
                subprocess.call(['xdg-open', work_dir])
        else:
            wx.MessageBox(T('Work directory does not exist'), T('Error'), wx.OK | wx.ICON_ERROR)


class FileDropTarget(wx.FileDropTarget):
    def __init__(self, text_ctrl):
        super().__init__()
        self.text_ctrl = text_ctrl

    def OnDropFiles(self, x, y, filenames):
        s = json.dumps(filenames, ensure_ascii=False)
        self.text_ctrl.AppendText(s)
        return True


class ChatFrame(wx.Frame):
    def __init__(self, tm):
        title = T('AIPY - Your AI Assistant')
        super().__init__(None, title=title, size=(1024, 768))
        
        self.tm = tm
        self.title = title
        self.log = logger.bind(src='gui')
        self.task_queue = queue.Queue()
        self.aipython = AIPython(self)
        self.welcomed = False  # 添加初始化标志
        resources_dir = resources.files(f"{__PACKAGE_NAME__}.res")
        self.html_file_path = os.path.abspath(resources_dir / "chatroom.html")
        self.avatars = {T('Me'): '🧑', 'BB-8': '🤖', T('Turing'): '🧠', T('AIPy'): '🐙'}

        icon = wx.Icon(str(resources_dir / "aipy.ico"), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        self.make_menu_bar()
        self.make_panel()
        self.statusbar = CStatusBar(self)
        self.SetStatusBar(self.statusbar)
        self.statusbar.SetStatusText(T('Press Ctrl+Enter to send message'), 0)

        self.Bind(EVT_CHAT, self.on_chat)
        self.webview.Bind(wx.html2.EVT_WEBVIEW_TITLE_CHANGED, self.on_webview_title_changed)
        self.aipython.start()
        self.Show()

    def make_input_panel(self, panel):
        self.container = wx.Panel(panel)
 
        self.input = wx.TextCtrl(self.container, style=wx.TE_MULTILINE)
        self.input.SetMinSize((-1, 60))
        self.input.SetWindowStyleFlag(wx.BORDER_SIMPLE)
        self.input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.done_button = wx.Button(self.container, label=T('End'), size=(50, -1))
        self.done_button.Hide()
        self.done_button.Bind(wx.EVT_BUTTON, self.on_done)
        self.send_button = wx.Button(self.container, label=T('Send'), size=(50, -1))
        self.send_button.Bind(wx.EVT_BUTTON, self.on_send)
        self.container.Bind(wx.EVT_SIZE, self.on_container_resize)
        return self.container

    def make_input_panel2(self, panel):
        container = wx.Panel(panel)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(container, style=wx.TE_MULTILINE)
        self.input.SetMinSize((-1, 80))
        self.input.SetWindowStyleFlag(wx.BORDER_SIMPLE)
        self.input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        hbox.Add(self.input, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        vbox = wx.BoxSizer(wx.VERTICAL)
        self.done_button = wx.Button(container, label=T('End'))
        self.done_button.Hide()
        self.done_button.Bind(wx.EVT_BUTTON, self.on_done)
        self.done_button.SetBackgroundColour(wx.Colour(255, 230, 230)) 
        self.send_button = wx.Button(container, label=T('Send'))
        self.send_button.Bind(wx.EVT_BUTTON, self.on_send)
        vbox.Add(self.done_button, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        vbox.AddSpacer(10)
        vbox.Add(self.send_button, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        hbox.Add(vbox, 0, wx.ALIGN_CENTER)
        container.SetSizer(hbox)    
        self.container = container
        return container
    
    def make_panel(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.webview = wx.html2.WebView.New(panel)
        self.webview.LoadURL(f'file://{self.html_file_path}')
        self.webview.SetWindowStyleFlag(wx.BORDER_NONE)
        vbox.Add(self.webview, proportion=1, flag=wx.EXPAND | wx.ALL, border=12)

        if sys.platform == 'darwin':
            input_panel = self.make_input_panel(panel)
        else:
            input_panel = self.make_input_panel2(panel)
        drop_target = FileDropTarget(self.input)
        self.input.SetDropTarget(drop_target)
        font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.input.SetFont(font)
    
        vbox.Add(input_panel, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=12)

        panel.SetSizer(vbox)
        self.panel = panel

    def make_menu_bar(self):
        menubar = wx.MenuBar()
        
        # 文件菜单
        file_menu = wx.Menu()
        save_item = file_menu.Append(wx.ID_SAVE, T('Save chat history as HTML'))
        clear_item = file_menu.Append(wx.ID_CLEAR, T('Clear chat'))
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, T('Exit'))
        menubar.Append(file_menu, T('File'))
        
        # 编辑菜单
        edit_menu = wx.Menu()
        config_item = edit_menu.Append(wx.ID_ANY, T('Configuration'))
        api_market_item = edit_menu.Append(wx.ID_ANY, T('API Market'))
        menubar.Append(edit_menu, T('Edit'))
        
        # 任务菜单
        task_menu = wx.Menu()
        self.new_task_item = task_menu.Append(wx.ID_NEW, T('Start new task'))
        menubar.Append(task_menu, T('Task'))
        
        # 帮助菜单
        help_menu = wx.Menu()
        website_item = help_menu.Append(wx.ID_ANY, T('Website'))
        #forum_item = help_menu.Append(wx.ID_ANY, T('Forum'))
        if __lang__ == 'zh':
            wechat_item = help_menu.Append(wx.ID_ANY, T('WeChat Group'))
            self.Bind(wx.EVT_MENU, self.on_open_website, wechat_item)
        help_menu.AppendSeparator()
        about_item = help_menu.Append(wx.ID_ABOUT, T('About'))
        menubar.Append(help_menu, T('Help'))
        
        self.SetMenuBar(menubar)
        
        # 绑定事件
        self.Bind(wx.EVT_MENU, self.on_save_html, save_item)
        self.Bind(wx.EVT_MENU, self.on_clear_chat, clear_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_done, self.new_task_item)
        self.Bind(wx.EVT_MENU, self.on_config, config_item)
        self.Bind(wx.EVT_MENU, self.on_api_market, api_market_item)
        self.Bind(wx.EVT_MENU, self.on_open_website, website_item)
        #self.Bind(wx.EVT_MENU, self.on_open_website, forum_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

    def on_exit(self, event):
        self.task_queue.put('exit')
        self.aipython.join()
        self.Close()

    def on_done(self, event):
        self.tm.done()
        self.done_button.Hide()
        self.SetStatusText(T('Current task has ended'), 0)
        self.new_task_item.Enable(False)
        self.SetTitle(self.title)
        self.clear_chat()

    def on_container_resize(self, event):
        container_size = event.GetSize()
        self.input.SetSize(container_size)

        overlap = -20
        send_button_size = self.send_button.GetSize()
        button_pos_x = container_size.width - send_button_size.width + overlap
        button_pos_y = container_size.height - send_button_size.height - 10
        self.send_button.SetPosition((button_pos_x, button_pos_y))

        if self.aipython.can_done():
            done_button_size = self.done_button.GetSize()
            button_pos_x = container_size.width - done_button_size.width + overlap
            button_pos_y = 10
            self.done_button.SetPosition((button_pos_x, button_pos_y))
            self.done_button.Show()

        event.Skip()

    def on_clear_chat(self, event):
        self.webview.LoadURL(f'file://{self.html_file_path}')

    def clear_chat(self):
        """清空聊天记录"""
        js_code = """
        const chatContainer = document.querySelector('.chat-container');
        chatContainer.innerHTML = '';
        lastUser = '';
        lastMessage = null;
        lastRawContent = '';
        """
        self.webview.RunScript(js_code)

    def on_open_website(self, event):
        """打开网站"""
        menu_item = self.GetMenuBar().FindItemById(event.GetId())
        if not menu_item:
            return
            
        label = menu_item.GetItemLabel()
        if label == T('Website'):
            url = T("https://aipy.app")
        elif label == T('Forum'):
            url = T("https://d.aipy.app")
        elif label == T('WeChat Group'):
            url = T("https://d.aipy.app/d/13")
        else:
            return
            
        wx.LaunchDefaultBrowser(url)

    def on_about(self, event):
        about_dialog = AboutDialog(self)
        about_dialog.ShowModal()
        about_dialog.Destroy()

    def on_save_html(self, event):
        try:
            html_content = self.webview.GetPageSource()
            self.save_html_content(html_content)
        except Exception as e:
            wx.MessageBox(f"save html error: {e}", "Error")

    def save_html_content(self, html_content):
        with FileDialog(self, T('Save chat history as HTML file'), wildcard="HTML file (*.html)|*.html",
                        style=FD_SAVE | FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            path = dialog.GetPath()
            try:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(html_content)
            except IOError:
                wx.LogError(f"{T('Failed to save file')}: {path}")

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        send_shortcut = (event.ControlDown() or event.CmdDown()) and keycode == wx.WXK_RETURN

        if send_shortcut:
            self.send_message()
        else:
            event.Skip()

    def on_send(self, event):
        self.send_message()

    def get_task(self):
        return self.task_queue.get()

    def toggle_input(self):
        if self.container.IsShown():
            self.container.Hide()
            self.done_button.Hide()
            wx.BeginBusyCursor()
            self.SetStatusText(T('Operation in progress, please wait...'), 0)
            self.new_task_item.Enable(False)
        else:
            self.container.Show()
            self.done_button.Show()
            wx.EndBusyCursor()
            self.SetStatusText(T('Operation completed. If you start a new task, please click the "End" button'), 0)
            self.new_task_item.Enable(self.aipython.can_done())
        self.panel.Layout()
        self.panel.Refresh()

    def send_message(self):
        text = self.input.GetValue().strip()
        if not text:
            return
        
        if not self.tm.busy:
            self.SetTitle(f"[{T('Current task')}] {text}")

        self.append_message(T('Me'), text)
        self.input.Clear()
        self.toggle_input()
        self.task_queue.put(text)

    def on_chat(self, event):
        user = event.user
        text = event.msg
        self.append_message(user, text)

    def append_message(self, user, text):
        avatar = self.avatars[user]
        js_code = f'appendMessage("{avatar}", "{user}", {repr(text)});'
        self.webview.RunScript(js_code)

    def on_config(self, event):
        dialog = ConfigDialog(self, self.tm.settings)
        if dialog.ShowModal() == wx.ID_OK:
            values = dialog.get_values()
            if values['timeout'] == 0:
                del values['timeout']
            self.tm.config_manager.update_sys_config(values)
        dialog.Destroy()

    def on_api_market(self, event):
        """打开API配置对话框"""
        dialog = ApiMarketDialog(self, self.tm.config_manager)
        dialog.ShowModal()
        dialog.Destroy()

    def on_llm_config(self, event):
        """打开LLM配置向导"""
        show_provider_config(self.tm.llm_config, parent=self)

    def on_webview_title_changed(self, event):
        """WebView 标题改变时的处理"""
        if not self.welcomed:
            wx.CallLater(100, self.append_message, T('AIPy'), T('welcome_message'))
            self.welcomed = True

            # 检查更新
            try:
                update = self.tm.get_update()
                if update and update.get('has_update'):
                    wx.CallLater(1000, self.append_message, T('AIPy'), f"\n🔔 **{T('Update available')}❗**: `v{update.get('latest_version')}`")
            except Exception as e:
                self.log.error(f"检查更新时出错: {e}")
            
        event.Skip()

class AboutDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=T('About AIPY'))
        
        # 创建垂直布局
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        logo_panel = wx.Panel(self)
        logo_sizer = wx.BoxSizer(wx.HORIZONTAL)

        with resources.path(f"{__PACKAGE_NAME__}.res", "aipy.ico") as icon_path:
            icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO)
            bmp = wx.Bitmap()
            bmp.CopyFromIcon(icon)
            # Scale the bitmap to a more appropriate size
            scaled_bmp = wx.Bitmap(bmp.ConvertToImage().Scale(48, 48, wx.IMAGE_QUALITY_HIGH))
            logo_sizer.Add(wx.StaticBitmap(logo_panel, -1, scaled_bmp), 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # 添加标题
        title = wx.StaticText(logo_panel, -1, label=T('AIPy'))
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        logo_sizer.Add(title, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        logo_panel.SetSizer(logo_sizer)
        vbox.Add(logo_panel, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加描述
        desc = wx.StaticText(self, label=T('AIPY is an intelligent assistant that can help you complete various tasks.'))
        desc.Wrap(350)
        vbox.Add(desc, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加版本信息
        version = wx.StaticText(self, label=f"{T('Version')}: {__version__}")
        vbox.Add(version, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加配置目录信息
        config_dir = wx.StaticText(self, label=f"{T('Current configuration directory')}: {CONFIG_DIR}")
        config_dir.Wrap(350)
        vbox.Add(config_dir, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加工作目录信息
        work_dir = wx.StaticText(self, label=f"{T('Current working directory')}: {parent.tm.workdir}")
        work_dir.Wrap(350)
        vbox.Add(work_dir, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加团队信息
        team = wx.StaticText(self, label=T('AIPY Team'))
        vbox.Add(team, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加确定按钮
        ok_button = wx.Button(self, wx.ID_OK, T('OK'))
        vbox.Add(ok_button, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        self.SetSizer(vbox)
        self.SetMinSize((400, 320))
        self.Fit()
        self.Centre()

def main(args):
    app = wx.App(False)
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    conf = ConfigManager(default_config_path, args.config_dir)
    settings = conf.get_config()
    lang = settings.get('lang')
    if lang: set_lang(lang)
    llm_config = LLMConfig(CONFIG_DIR / "config")
    if conf.check_config(gui=True) == 'TrustToken':
        if llm_config.need_config():
            show_provider_config(llm_config)
            if llm_config.need_config():
                return
        settings["llm"] = llm_config.config
        
    settings.gui = True
    settings.auto_install = True
    settings.auto_getenv = True

    file = None if args.debug else open(os.devnull, 'w', encoding='utf-8')
    console = Console(file=file, record=True)
    console.gui = True
    try:
        tm = TaskManager(settings, console=console)
    except Exception as e:
        traceback.print_exc()
        return
    tm.config_manager = conf
    tm.llm_config = llm_config
    ChatFrame(tm)
    app.MainLoop()
