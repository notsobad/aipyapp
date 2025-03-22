#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from rich.console import Console
from rich.markdown import Markdown

from llm import LLM
from run import Runner

STMTS = """
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from bs4 import BeautifulSoup
"""

SYS_PROMPT = f"""
你是一位Python编程专家。你的任务是将用户的自然语言指令转换为可在当前程序环境中执行的Python代码片段。

### 指令分析与执行流程
1. 仔细分析用户的指令，确定需要执行的具体任务和目标
2. 优先尝试用一段完整的Python代码实现用户的全部指令
3. 如果任务复杂，将其分解为清晰的步骤，逐步实现
4. 如果代码执行失败，根据用户反馈分析错误原因，尝试修复代码

### 代码规范与格式
1. 使用 ```python 和 ``` 标记代码块
2. 遵循PEP 8 Python代码风格规范
3. 为关键步骤添加简洁的注释
4. 提供适当的变量名和函数名，使代码自文档化
5. 对于复杂操作，解释代码的工作原理和目的

### 代码要求
- 提供的代码将在同一个Python环境中执行，可以访问和修改全局变量
- 每个代码片段应当是独立的、可执行的步骤，但可以引用之前步骤创建的变量和对象
- 不需要重复导入已经导入的库，假设代码在连续的环境中运行
- 实现适当的错误处理，包括但不限于：
  * 文件操作的异常处理
  * 网络请求的超时和连接错误处理
  * 数据处理过程中的类型错误和值错误处理
- 确保代码安全，不执行任何有害操作
- 对于用户输入，添加必要的验证和安全检查

### Python运行环境
Python运行环境已经用下述代码初始化，你可以直接使用这些已经导入的模块：
{STMTS}

### 执行结果反馈
用户每执行完一段Python代码后都会通过一个JSON字符串对象反馈执行结果，可能包括以下属性：
- `stdout`: 标准输出内容
- `stderr`: 标准错误输出
- `lastexpr`: 代码最后一个表达式的值
- `errstr`: 异常信息
- `traceback`: 异常堆栈信息
注意：如果某个属性为空，它不会出现在反馈中。

生成Python代码的时候，你可以有意使用标准输出和最后一个表达式的值，结合用户反馈结果来判断执行情况。

### 反馈处理策略
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
   - 如果没有任何输出，确认代码执行成功但无输出

### 交互模式
- 对用户的每次反馈迅速作出响应
- 对于多步骤任务，清晰标明当前进度和后续步骤
"""

class Agent(object):
    def __init__(self, inst=None):
        super().__init__()
        self._inst = inst
        self._llm = None
        self._runner = None
        self._console = Console()

    def reset(self):
        self._runner = Runner(stmts=STMTS)
        self._llm = LLM(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=os.getenv("OPENAI_MODEL")
        )

    @property
    def history(self):
        return self._llm.history
    
    @property
    def locals(self):
        return self._runner.locals
    
    def extract_code_blocks(self, text):
        code_blocks = []
        lines = text.split('\n')
        in_code_block = False
        current_block = []
        
        for line in lines:
            if line.strip().startswith('```python'):
                in_code_block = True
                continue
            elif line.strip().startswith('```') and in_code_block:
                in_code_block = False
                code_blocks.append('\n'.join(current_block))
                current_block = []
                continue
            
            if in_code_block:
                current_block.append(line)
        
        return code_blocks
        

    def send_feedback(self, result):
        print("📝 发送执行结果反馈...")
        feedback_response, ok = self._llm(str(result))
        print("🤖 LLM 反馈回应:")
        self._console.print(Markdown(feedback_response))
        return feedback_response, ok


    def run_code_blocks(self, code_blocks, depth=0):
       ret = True
       results = []
       for i, code in enumerate(code_blocks):
            print(f"\n📊 执行代码块 {i+1}/{len(code_blocks)}:")
            self._console.print(Markdown(f"```python\n{code}\n```"))
            result = self._runner(code)
            success = not result.has_error()
            if success:
                print(f"✅ 执行成功:")
                self._console.print(Markdown(result.markdown()))
                results.append(f"代码块 {i+1}: 执行成功")
            else:
                print(f"❌ 执行失败:")
                self._console.print(Markdown(result.markdown()))
                results.append(f"代码块 {i+1}: 执行失败 - {result}")

            feedback_response, ok = self.send_feedback(result)
            if success:
                continue

            if not ok or depth > 3:
                ret = False
                print("\n❌ 修复代码失败或深度超过 3 层，停止尝试修复")
                break
            
            new_code_blocks = self.extract_code_blocks(feedback_response)
            if new_code_blocks:
                print("\n🔄 尝试执行修复后的代码:")
                new_results = self.run_code_blocks(new_code_blocks, depth=depth+1)
                results.extend(new_results)
            else:
                ret = False
                print("\n❌ LLM did't give any code feedback，stop")
                break

       return results, ret
        

    def __call__(self, instruction):
        self._inst = instruction
        prompt = SYS_PROMPT + instruction

        print("📝 正在处理指令...")
        response, ok = self._llm(prompt)
        print("\n🤖 LLM 响应:")
        self._console.print(Markdown(response))

        code_blocks = self.extract_code_blocks(response)
        if not code_blocks:
            print("\n❌ 未找到可执行的代码块")
            return "未找到可执行的代码块"

        results, ok = self.run_code_blocks(code_blocks)
        print(f"\n📋 处理{'成功' if ok else '失败'}，结果摘要:\n{'\n'.join(results)}")
