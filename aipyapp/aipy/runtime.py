#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from typing import Union, Any
from functools import wraps
import inspect

from term_image.image import from_file, from_url

from . import utils
from .tool import llm_call
from .plugin import event_bus
from .. import T
from ..exec import PythonRuntime
from .blocks import CodeBlock

def restore_output(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        try:
            return func(self, *args, **kwargs)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
    return wrapper

class CliPythonRuntime(PythonRuntime):
    def __init__(self, task):
        super().__init__(task.role.env)
        self.gui = task.gui
        self.task = task
        self.console = task.console
        self._auto_install = task.settings.get('auto_install')
        self._auto_getenv = task.settings.get('auto_getenv')

    @restore_output
    def install_packages(self, *packages: str) -> bool:
        """
        Install third-party packages

        Args:
            packages: The names of the packages to install

        Returns:
            bool: True if the packages are installed successfully, False otherwise

        Examples:
            >>> runtime.install_packages('requests', 'openai')
            True
            >>> runtime.install_packages('requests', 'openai')
            False
        """
        self.console.print(f"\n⚠️ LLM {T('Request to install third-party packages')}: {packages}")
        ok = utils.confirm(self.console, f"💬 {T('If you agree, please enter')} 'y'> ", auto=self._auto_install)
        if ok:
            ret = self.ensure_packages(*packages)
            self.console.print("\n✅" if ret else "\n❌")
            return ret
        return False
    
    @restore_output
    def get_env(self, name: str, default: str = None, *, desc: str = None) -> Union[str, None]:
        self.console.print(f"\n⚠️ LLM {T('Request to obtain environment variable {}, purpose', name)}: {desc}")
        try:
            value = self.envs[name][0]
            self.console.print(f"✅ {T('Environment variable {} exists, returned for code use', name)}")
        except KeyError:
            if self._auto_getenv:
                self.console.print(f"✅ {T('Auto confirm')}")
                value = None
            else:
                value = self.console.input(f"💬 {T('Environment variable {} not found, please enter', name)}: ")
                value = value.strip()
            if value:
                self.set_env(name, value, desc)
        return value or default
    
    @restore_output
    def display(self, path: str = None, url: str = None) -> None:
        image = {'path': path, 'url': url}
        event_bus.broadcast('display', image)
        if not self.gui:
            image = from_file(path) if path else from_url(url)
            image.draw()

    @restore_output
    def input(self, prompt: str) -> str:
        return self.console.input(prompt)    
    
    def get_block_by_name(self, block_name: str) -> Union[CodeBlock, None]:
        return self.task.code_blocks.get_block_by_name(block_name)
    
    def call_tool(self, name: str, **kwargs) -> Any:
        """
        Call a tool

        Args:
            name: The name of the tool to call
            **kwargs: The arguments to pass to the tool

        Returns:
            Any: The result of the tool call
        """
        return llm_call(name, **kwargs)
    
    
    def get_function_list(self):
        """
        根据函数签名和docstring，生成函数调用提示
        """
        functions = {}
        names = ['install_packages', 'get_env', 'display', 'input', 'get_block_by_name', 'call_tool']
        for name in names:
            func_obj = getattr(self, name)
            docstring = func_obj.__doc__
            signature = inspect.signature(func_obj)
            functions[name] = {
                'docstring': docstring,
                'signature': signature
            }
        return functions

if __name__ == '__main__':
    runtime = CliPythonRuntime(None)
    functions = runtime.get_function_list()
    print(functions)