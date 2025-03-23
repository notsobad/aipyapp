#!/usr/bin/env python
# -*- coding: utf-8 -*-

from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from llm import LLM
from runner import Runner, Runtime
from utils import restore_output

STMTS = """
import os
import sys
import json
import traceback
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from bs4 import BeautifulSoup
"""

SYS_PROMPT = f"""
你是一位Python软件工程师。

用户告诉你任务，你的职责是分析客户的任务，然后写一段能完成任务的Python代码交给客户执行。
要谨记以严谨/专业/职业的态度完成客户的任务，清楚告诉客户需要执行的代码段，并向用户简要描述代码的工作原理。
客户会实际执行你写的代码，并向你反馈运行结果，你需要分析结果，判断是非需要修正代码。

## 任务转换规则
- 解析客户的任务，生成能够完成任务并可以直接运行的 Python 代码
- 使用 ```run 和 ``` 标记需要客户执行的用来完成任务的 Python 代码块
- 和客户任务无关的 Python 代码块使用 ```python 和 ``` 标记，例如给客户的进一步建议。
- 每个消息里最多只能包含一段需要客户执行的 Python 代码
- 优先使用一段 Python 代码解决问题
- 如果任务复杂，分解为多个步骤给客户一步步执行
- 对于多步骤任务，清晰标明当前进度和后续步骤

## Python运行环境
Python运行环境已经用下述代码初始化，你可以直接使用这些已经导入的模块：
{STMTS}

上述已导入的第三方模块可以直接使用。
Python 自带模块里 os/sys/json/traceback 已导入，可以直接使用，其它需要 import 后使用。
其它需要使用的第三方模块，必需先调用 runtime 对象的 install_packages 方法申请客户同意:
- 参数为要安装的模块名称列表，如 ['numpy', 'pandas']
- 返回 True 表示已安装，可以导入使用
- 返回 False 表示安装被拒绝或安装失败

如果你希望获取代码执行后某个变量的值用来判断执行情况，可以在代码最后把这个变量放入 __vars__ 字典。
例如："__vars__['result'] = result"，客户执行完后会把 __vars__ 内容反馈给你。

## Python代码规则
- 确保代码在 Python 运行环境中可以无需修改直接执行，例如不能要求提供 API_KEY 之类
- 提供的代码将在同一个Python环境中执行，可以访问和修改全局变量
- 每个代码片段应当是独立的、可执行的步骤，但可以引用之前步骤创建的变量和对象
- 不需要重复导入已经导入的库，假设代码在连续的环境中运行
- 如果需要安装额外库，先调用 runtime 对象的 install_packages 方法申请安装
- 实现适当的错误处理，包括但不限于：
  * 文件操作的异常处理
  * 网络请求的超时和连接错误处理
  * 数据处理过程中的类型错误和值错误处理
- 确保代码安全，不执行任何有害操作
- 代码里，正常信息必需输出到 stdout，错误信息必需输出到 stderr

## 代码执行结果反馈
每执行完一段Python代码，我都会立刻通过一个JSON字符串对象反馈执行结果给你，对象包括以下属性：
- `stdout`: 标准输出内容
- `stderr`: 标准错误输出
- `vars`: 代码最后一个表达式的值
- `errstr`: 异常信息
- `traceback`: 异常堆栈信息

注意：
- 如果某个属性为空，它不会出现在反馈中。
- 如果代码没有任何输出，客户会反馈一对空的大括号 {{}}，这种情况应该表示执行正常。

生成Python代码的时候，你可以有意使用stdout/stderr以及前述__vars__变量来记录执行情况。
但避免在 stdout 和 vars 中保存相同的内容，这样会导致反馈内容重复且太长。

## 反馈处理策略
根据执行结果反馈采取相应的后续行动：
1. **成功执行**：
   - 如果有`stdout`或`lastexpr`且没有错误信息，代码执行成功
   - 简要解释结果含义并提供下一步建议

2. **部分成功**：
   - 如果有`stderr`但无`errstr`或`traceback`，代码执行但有警告
   - 解释警告含义并提供优化建议

3. **执行失败**：
   - 如果有`errstr`或`traceback`，代码执行失败
   - 根据错误信息准确分析失败原因
   - 提供修复建议和改进的代码

4. **无输出情况**：
   - 如果没有任何输出或输出一对空的大括号{{}}，可能表明代码执行成功但无输出
"""

class Command(Enum):
    RUN = "运行"
    STOP = "终止"
    END = "完成"
    CONT = "继续"

class MsgType(Enum):
    CODE = "代码"
    TEXT = "文本"

class Agent(object):
    def __init__(self, inst=None):
        self._llm = None
        self._runner = None
        self._console = None

    def reset(self):
        self._runner = Runner(self, stmts=STMTS)
        self._llm = LLM()
        self._console = Console(record=True)

    @property
    def llm(self):
        return self._llm
    
    @property
    def runner(self):
        return self._runner
    
    def save(self, path, clear=False):
        path = Path(path)
        if path.suffix == '.svg':
            self._console.save_svg(path, clear=clear)
        elif path.suffix in ('.html', '.htm'):
            self._console.save_html(path, clear=clear)
        else:
            self._console.print(f"不支持的文件格式：{path}")

    def parse_reply(self, text):
        lines = text.split('\n')
        code_block = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith('```run'):
                in_code_block = True
                continue
            elif line.strip().startswith('```') and in_code_block:
                break
            if in_code_block:
                code_block.append(line)
        
        if code_block:
            ret = {'type': MsgType.CODE, 'code': '\n'.join(code_block)}
        else:
            ret = {'type': MsgType.TEXT, 'code': None}
        return ret
        
    def process_code_reply(self, msg):
        code_block = msg['code']
        self._console.print(f"\n⚡ 开始执行代码块:", Markdown(f"```python\n{code_block}\n```"))
        result = self._runner(code_block)
        self._console.print("✅ 执行结果:\n", Markdown(f"```json\n{result}\n```"))
        self._console.print("\n📤 开始反馈结果")
        feedback_response = self._llm(str(result))
        return feedback_response

    def __call__(self, instruction, reset=False):
        """
        执行自动处理循环，直到 LLM 不再返回代码消息
        """
        self._console.print("▶ [yellow]开始处理指令:", f'[red]{instruction}')
        if reset:
            self.reset()
        system_prompt = None if self._llm.history else SYS_PROMPT
        response = self._llm(instruction, system_prompt=system_prompt)

        while response:
            self._console.print("\n📩 LLM 响应:\n", Markdown(response))
            msg = self.parse_reply(response)
            if msg['type'] != MsgType.CODE:
                break
            response = self.process_code_reply(msg)

        self._console.print("\n⏹ 结束处理指令")

    @restore_output
    def install_packages(self, packages):
        self._console.print(f"\n⚠️ LLM 申请安装第三方包: {packages}")
        while True:
            response = Prompt.ask("💬 如果同意且已安装，请输入 'y", choices=["y", "n"], default="n", console=self._console)
            if response in ["y", "n"]:
                break
        return response == "y"
        
    def chat(self, prompt):
        system_prompt = None if self._llm.history else SYS_PROMPT
        response, ok = self._llm(prompt, system_prompt=system_prompt)
        self._console.print(Markdown(response))

    def step(self):
        response = self._llm.get_last_message()
        if not response:
            self._console.print("❌ 未找到上下文信息")
            return
        self.process_reply(response)
