#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
from io import StringIO
from abc import ABC, abstractmethod

import utils

INIT_IMPORTS = """
import os
import re
import sys
import json
import time
import random
import traceback
"""

class Runtime(ABC):
    @abstractmethod
    def install_packages(self, packages):
        pass

    @abstractmethod
    def getenv(self, name, desc=None):
        pass

class Runner(Runtime):
    def __init__(self, console):
        self._console = console
        self.env = {}
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
            self.history.append({'code': code_str, 'result': result, 'session': self._globals['__session__']})

        s = captured_stdout.getvalue().strip()
        if s: result['stdout'] = s
        s = captured_stderr.getvalue().strip()
        if s: result['stderr'] = s         

        vars = gs.get('__result__')
        if vars:
            result['__result__'] = vars
        return result
    
    @utils.restore_output
    def install_packages(self, packages):
        return utils.confirm(self._console, f"\n⚠️ LLM 申请安装第三方包: {packages}", "💬 如果同意且已安装，请输入 'y")
    
    @utils.restore_output
    def getenv(self, name, desc=None):
        self._console.print(f"\n⚠️ LLM 申请获取环境变量 {name}，用途: {desc}")
        try:
            value = self.env[name][0]
            self._console.print(f"✅ 环境变量 {name} 存在，返回给代码使用")
        except KeyError:
            value = self._console.input(f"💬 未找到环境变量 {name}，请输入: ")
            value = value.strip()
            if value:
                self.setenv(name, value, desc)
        return value
    
    def setenv(self, name, value, desc):
        self.env[name] = (value, desc)
