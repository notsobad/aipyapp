#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import subprocess
from enum import Enum, auto
from pathlib import Path
import importlib.resources as resources

from typing import Any, Optional, Union
import threading
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext

from dynaconf import Dynaconf
from rich.console import Console,JustifyMethod, OverflowMethod
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter

from . import __version__
from .aipy.config import ConfigManager
from .aipy import TaskManager
from .aipy.i18n import T
#
__PACKAGE_NAME__ = "aipyapp"


class GUIConsole(Console):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gui = None

    def set_gui(self, gui):
        self.gui = gui


    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        justify: Optional[JustifyMethod] = None,
        overflow: Optional[OverflowMethod] = None,
        no_wrap: Optional[bool] = None,
        emoji: Optional[bool] = None,
        markup: Optional[bool] = None,
        highlight: Optional[bool] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop: bool = True,
        soft_wrap: Optional[bool] = None,
        new_line_start: bool = False,
    ) -> None:
        """Print to the console and send the output to a GUI handler."""
        message = ""
        # if the first argument is a string, use it as the message
        if len(objects) == 1 and isinstance(objects[0], str):
            message = objects[0]
        else:
            # Otherwise, join all objects into a single string
            #message = sep.join(str(_object) for _object in objects)
            pass
        # If the message is empty, return
        if not message:
            return
        print("message", message)

        if self.gui:
            self.gui.handle_ai_output(message)


    def print_exception(self, *args, **kwargs):
        super().print_exception(*args, **kwargs)
        # Optionally, capture the formatted exception and display in the text_widget
        # This requires capturing the output of super().print_exception
        # and redirecting it to the text_widget.  A full implementation is
                # beyond the scope of this example.

class CommandType(Enum):
    CMD_DONE = auto()
    CMD_USE = auto()
    CMD_EXIT = auto()
    CMD_INVALID = auto()
    CMD_TEXT = auto()

def parse_command(input_str, llms=set()):
    lower = input_str.lower()

    if lower in ("/done", "done"):
        return CommandType.CMD_DONE, None
    if lower in ("/exit", "exit"):
        return CommandType.CMD_EXIT, None
    if lower in llms:
        return CommandType.CMD_USE, input_str
    
    if lower.startswith("/use "):
        arg = input_str[5:].strip()
        if arg in llms:
            return CommandType.CMD_USE, arg
        else:
            return CommandType.CMD_INVALID, arg

    if lower.startswith("use "):
        arg = input_str[4:].strip()
        if arg in llms:
            return CommandType.CMD_USE, arg
               
    return CommandType.CMD_TEXT, input_str

class AIAppGUI:
    def __init__(self, tm, settings):
        self.tm = tm
        self.settings = settings

        # init llm
        self.names = tm.llm.names
        completer = WordCompleter(['/use', 'use', '/done','done'] + list(self.names['enabled']), ignore_case=True)
        self.history = FileHistory(str(Path.cwd() / settings.history))
        self.session = PromptSession(history=self.history, completer=completer)
        self.style_main = Style.from_dict({"prompt": "green"})
        self.style_ai = Style.from_dict({"prompt": "cyan"})
        # EOF
        
        # GUI staff
        self.root = tk.Tk()
        self.root.title("AI Assistant")

        self.code_label = ttk.Label(self.root, text="Code:")
        self.code_label.grid(row=0, column=0, sticky="w")
        self.code_text = scrolledtext.ScrolledText(self.root, width=60, height=20)
        self.code_text.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        self.output_label = ttk.Label(self.root, text="AI Output:")
        self.output_label.grid(row=0, column=1, sticky="w")
        self.output_text = scrolledtext.ScrolledText(self.root, width=60, height=20)
        self.output_text.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        self.input_label = ttk.Label(self.root, text="Enter your prompt:")
        self.input_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.input_entry = tk.Text(self.root, width=60, height=5)
        self.input_entry.grid(row=3, column=0, padx=5, pady=2, sticky="ew")

        self.submit_button = ttk.Button(self.root, text="提交", command=self.submit_prompt)
        self.submit_button.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.continue_button = ttk.Button(self.root, text="结束会话并继续", command=self.continue_session)
        self.continue_button.grid(row=4, column=1, padx=5, pady=2, sticky="w")
        self.end_button = ttk.Button(self.root, text="结束会话并退出", command=self.end_session)
        self.end_button.grid(row=4, column=1, padx=60, pady=2, sticky="e")



        self.open_work_button = ttk.Button(self.root, text="打开工作目录", command=self.open_work_dir)
        self.open_work_button.grid(row=4, column=0, padx=5, pady=2, sticky="w")

        self.open_config_button = ttk.Button(self.root, text="打开配置文件", command=self.open_config_file)

        self.open_config_button.grid(row=4, column=0, padx=10, pady=2, sticky="e")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.print_output(f"Python use - AIPython ({__version__}) [https://www.aipy.app]\n")

    def open_work_dir(self):
        #path = self.settings.workdir
        path = Path.cwd()
        if os.path.exists(path):
            if os.name == 'nt':  # Windows
                os.startfile(path)
            elif os.name == 'posix':  # macOS or Linux
                subprocess.Popen(['open', path])  # macOS
                # For Linux, you might want to use 'xdg-open' instead of 'open'
                # subprocess.Popen(['xdg-open', path])
        else:
            print(f"Directory not found: {path}")

    def open_config_file(self):
        path = self.settings.user_config_path
        if os.path.exists(path):
            if os.name == 'nt':  # Windows
                os.startfile(path)
            elif os.name == 'posix':  # macOS or Linux
                subprocess.Popen(['open', path])
        else:
            print(f"File not found: {path}")


    def handle_ai_output(self, output):
        #print("*"*10, "handle_ai_output", "*"*10)
        #print("GUI got output", output)
        #print("*"*10, "handle_ai_output EOF", "*"*10)
        #output = output.strip()
        if "#RUN" in output:
            self.print_code("\n" + output)
        else:
            self.print_output(output)

    def print_code(self, code):
        self.code_text.insert(tk.END, code)
        self.code_text.see(tk.END)
        self.code_text.update_idletasks()  # 添加此行以强制刷新 GUI
        self.code_text.update()  # Force the GUI to refresh
    
    def print_output(self, output):
        self.output_text.insert(tk.END, output)
        self.output_text.see(tk.END)
        self.output_text.update_idletasks()  # 添加此行以强制刷新 GUI
        self.output_text.update()  # Force the GUI to refresh

    def parse_use_command(self, user_input, llms):
        words = user_input.split()
        if len(words) > 2:
            return None
        if words[0] in ('/use', 'use'):
            return words[1] if len(words) > 1 else ''
        return words[0] if len(words) == 1 and words[0] in llms else None
    
    def submit_prompt(self):
        user_input = self.input_entry.get("1.0", tk.END)

        # check use command
        if len(user_input) < 2:
            return

        cmd, arg = parse_command(user_input, self.names['enabled'])
        if cmd == CommandType.CMD_TEXT:
            task = self.tm.new_task(arg)
            self.run_task(task)
        elif cmd == CommandType.CMD_USE:
            ret = self.tm.llm.use(arg)
            #self.console.print('[green]Ok[/green]' if ret else '[red]Error[/red]')
        elif cmd == CommandType.CMD_INVALID:
            pass
            #self.console.print('[red]Error[/red]')
        elif cmd == CommandType.CMD_EXIT:
            self.end_session()

        # clear
        self.input_entry.delete("1.0", tk.END)

    def _run_task(self, task, instruction=None):
        try:
            task.run(instruction=instruction)
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception as e:
            #self.console.print_exception()
            pass

    def run_task(self, task, instruction=None):
        thread = threading.Thread(target=self._run_task, args=(task, instruction))
        thread.start()


    def end_session(self):
        try:
            self.tm.publish(verbose=False)
        except Exception as e:
            pass

        try:
            self.tm.done()
        except Exception as e:
            #self.console.print_exception()
            pass
        self.root.destroy()

    def continue_session(self):
        try:
            self.tm.publish(verbose=False)
        except Exception as e:
            pass

        try:
            self.tm.done()
        except Exception as e:
            #self.console.print_exception()
            pass
        self.input_entry.delete(0, tk.END)
        self.code_text.delete(1.0, tk.END)
        self.output_text.delete(1.0, tk.END)

    def run(self):
        self.root.mainloop()

def main(args):

    path = args.config if args.config else 'aipython.toml'
    user_config_path = Path(path).resolve()
    default_config_path = resources.files(__PACKAGE_NAME__) / "default.toml"
    conf = ConfigManager(default_config_path, path)
    conf.check_config()
    settings = conf.get_config()

    settings.user_config_path = user_config_path

    console = GUIConsole()
    try:
        tm = TaskManager(settings, console=console)
    except Exception as e:
        #console.print_exception(e)
        #console.print(f"[bold red]Error: {e}")
        print(e)
        return
   
    gui = AIAppGUI(tm, settings)  # Replace None with actual AI instance
    console.set_gui(gui)
    gui.run()