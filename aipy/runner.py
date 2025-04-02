#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import traceback
from io import StringIO

from term_image.image import from_file, from_url

from . import utils
from .i18n import T
from .interface import Runtime

INIT_IMPORTS = """
import os
import re
import sys
import json
import time
import random
import traceback
"""

def is_json_serializable(obj):
    try:
        json.dumps(obj)  # 尝试序列化对象
        return True
    except (TypeError, OverflowError):
        return False

class Runner(Runtime):
    def __init__(self, console, settings):
        self._console = console
        self._settings = settings
        self.env = {}
        self._auto_install = settings.get('auto_install')
        self._auto_getenv = settings.get('auto_getenv')
        for key, value in os.environ.items():
            if key == 'LC_TERMINAL':
                self.setenv(key, value, '终端应用程序')
            elif key == 'TERM':
                self.setenv(key, value, '终端类型')
        self.clear()

    def clear(self):
        self._globals = {'runtime': self, '__session__': {}}
        self.history = []
        exec(INIT_IMPORTS, self._globals)

    def __repr__(self):
        return f"<Runner history={len(self.history)}, env={len(self.env)}>"
    
    @property
    def globals(self):
        return self._globals
    
    @property
    def session(self):
        return self._globals['__session__']
    
    def __call__(self, code_str):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        captured_stdout = StringIO()
        captured_stderr = StringIO()
        sys.stdout, sys.stderr = captured_stdout, captured_stderr
        result = {}
        gs = self._globals.copy()
        gs['__result__'] = {}
        try:
            exec(code_str, gs)
        except Exception as e:
            result['errstr'] = str(e)
            result['traceback'] = traceback.format_exc()
            return result
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        s = captured_stdout.getvalue().strip()
        if s: result['stdout'] = s
        s = captured_stderr.getvalue().strip()
        if s: result['stderr'] = s         

        vars = gs.get('__result__')
        if vars:
            result['__result__'] = self.filter_result(vars)
        self.history.append({'code': code_str, 'result': result, 'session': self._globals['__session__']})
        return result
    
    @utils.restore_output
    def install_packages(self, packages):
        ok = utils.confirm(self._console, f"\n⚠️ LLM {T('ask_for_packages')}: {packages}", f"💬 {T('agree_packages')} 'y'> ", auto=self._auto_install)
        if ok:
            return utils.uv_install_packages(self._console, packages)
        
    @utils.restore_output
    def getenv(self, name, desc=None):
        self._console.print(f"\n⚠️ LLM {T('ask_for_env', name)}: {desc}")
        try:
            value = self.env[name][0]
            self._console.print(f"✅ {T('env_exist', name)}")
        except KeyError:
            if self._auto_getenv:
                self._console.print(f"✅ {T('auto_confirm')}")
                value = ''
            else:
                value = self._console.input(f"💬 {T('input_env', name)}: ")
                value = value.strip()
            if value:
                self.setenv(name, value, desc)
        return value
    
    @utils.restore_output
    def display(self, path=None, url=None):
        if path:
            image = from_file(path)
            image.draw()
        elif url:
            image = from_url(url)
            image.draw()
            
    def setenv(self, name, value, desc):
        self.env[name] = (value, desc)

    def filter_result(self, vars):
        if isinstance(vars, dict):
            for key in vars.keys():
                if key in self.env:
                    vars[key] = '<masked>'
                else:
                    vars[key] = self.filter_result(vars[key])
        elif isinstance(vars, list):
            vars = [self.filter_result(v) for v in vars]
        else:
            vars = vars if is_json_serializable(vars) else '<filtered>'
        return vars
    