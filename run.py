#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import traceback
from io import StringIO

class Runner(object):
    def __init__(self, stmts=None):
        self._globals = {}
        self._locals = {}
        self._stmts = stmts
        if stmts:
            exec(stmts, self._globals, self._locals)

    @property
    def locals(self):
        return self._locals
    
    def exec(self, code_str):
        old_stdout = sys.stdout
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            # 在当前环境中执行代码
            exec(code_str, self._globals, self._locals)
            output = captured_output.getvalue()
            output = output.strip()

            # 获取最后一个表达式的值（如果有）
            if not output and '_' in self._locals:
                output = str(self._locals['_'])
            if not output:
                output = "代码执行成功，没有输出。可以访问全局变量。"
                
            return True, output
        except Exception as e:
            return False, f"执行异常: {str(e)}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
 
    def reset(self):
        self._globals = {}
        self._locals = {}
        if self._stmts:
            exec(self._stmts, self._globals, self._locals)
