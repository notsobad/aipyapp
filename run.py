#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import traceback
from io import StringIO
from dataclasses import dataclass

@dataclass
class Result:
    stdout: str = ''
    stderr: str = ''
    lastexpr: str = ''
    errstr: str = ''
    traceback: str = ''

    def __str__(self):
        d = {}
        for field, value in self.__dict__.items():
            if value:
                d[field] = value
        return json.dumps(d, ensure_ascii=False)

    def has_error(self):
        return self.errstr or self.traceback
    
    def markdown(self) -> str:
        lines = []
        for field, value in self.__dict__.items():
            if value:
                lines.append(f"**{field}**:\n```\n{value}\n```")
        return "\n\n".join(lines)


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
    
    def __call__(self, code_str):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        captured_stdout = StringIO()
        captured_stderr = StringIO()
        sys.stdout, sys.stderr = captured_stdout, captured_stderr
        result = Result()
        try:
            exec(code_str, self._globals, self._locals)
        except Exception as e:
            result.errstr = str(e)
            result.traceback = traceback.format_exc()
            return result
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        result.stdout = captured_stdout.getvalue().strip()
        result.stderr = captured_stderr.getvalue().strip()

        if '_' in self._locals:
            result.lastexpr = str(self._locals['_'])
        return result

 
    def reset(self):
        self._globals = {}
        self._locals = {}
        if self._stmts:
            exec(self._stmts, self._globals, self._locals)
