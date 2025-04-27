#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from functools import wraps

from term_image.image import from_file, from_url

from . import utils
from .. import event_bus, T
from ..exec import BaseRuntime

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

class Runtime(BaseRuntime):
    def __init__(self, settings, console=None):
        super().__init__()
        self.console = console
        self._auto_install = settings.get('auto_install')
        self._auto_getenv = settings.get('auto_getenv')

    @restore_output
    def install_packages(self, *packages):
        self._console.print(f"\n⚠️ LLM {T("Request to install third-party packages")}: {packages}")
        ok = utils.confirm(self._console, f"💬 {T("If you agree, please enter")} 'y'> ", auto=self._auto_install)
        if ok:
            ret = self.ensure_packages(*packages)
            self._console.print("\n✅" if ret else "\n❌")
            return ret
        return False
    
    @restore_output
    def getenv(self, name, default=None, *, desc=None):
        self._console.print(f"\n⚠️ LLM {T("Request to obtain environment variable {}, purpose", name)}: {desc}")
        try:
            value = self.envs[name][0]
            self._console.print(f"✅ {T("Environment variable {} exists, returned for code use", name)}")
        except KeyError:
            if self._auto_getenv:
                self._console.print(f"✅ {T("Auto confirm")}")
                value = None
            else:
                value = self._console.input(f"💬 {T("Environment variable {} not found, please enter", name)}: ")
                value = value.strip()
            if value:
                self.setenv(name, value, desc)
        return value or default
    
    @restore_output
    def display(self, path=None, url=None):
        gui = getattr(self._console, 'gui', False)
        image = {'path': path, 'url': url}
        event_bus.broadcast('display', image)
        if not gui:
            image = from_file(path) if path else from_url(url)
            image.draw()

    @restore_output
    def input(self, prompt=''):
        return self._console.input(prompt)    