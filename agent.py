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
你是一位 Python 编程专家。你的任务是将用户的自然语言指令转换为可在当前程序环境中执行的 Python 代码片段。

请按照以下步骤操作：
1. 分析用户的指令，确定需要执行的任务
2. 将任务分解为清晰的步骤
3. 为每个步骤提供详细的 Python 代码，使用 ```python 和 ``` 标记代码块
4. 解释每个步骤的目的和工作原理

代码片段要求：
- 提供的代码将在同一个 Python 环境中执行，可以访问和修改全局变量
- 每个代码片段应当是独立的、可执行的步骤，但可以引用之前步骤创建的变量和对象
- 不需要重复导入已经导入的库，假设代码在连续的环境中运行
- 代码片段应当有适当的错误处理
- 可以使用标准库和后面描述的第三方库
- 确保代码安全，不执行任何有害操作
- 代码应当能够处理文件不存在等常见错误情况

Python 运行环境已经用下述代码初始化，你可以直接使用这些已经 import 的模块：
{STMTS}

用户的指令是:
"""

class Agent(Runner):
    def __init__(self, inst=None):
        super().__init__(stmts=STMTS)
        self._inst = inst
        self._llm = self.get_llm()
        self._console = Console()

    def get_llm(self):
        return LLM(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=os.getenv("OPENAI_MODEL")
        )

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
        

    def send_feedback(self, code, success, output):
        feedback_prompt = f"""
        我刚刚执行了你提供的代码，以下是执行结果:
        
        代码:
        ```python
        {code}
        ```
        
        执行结果:
        ```
        {output}
        ```
        
        {'代码执行成功，我将执行下一步，回复OK即可。' if success else '代码执行失败。请提供修复方案或替代方法。'}
        
        用户原始指令是: {self._inst}
        """
        
        print("\n📝 发送执行结果反馈...")
        feedback_response, ok = self._llm(feedback_prompt)
        print("\n🤖 LLM 反馈回应:")
        self._console.print(Markdown(feedback_response))
        return feedback_response, ok


    def run_code_blocks(self, code_blocks, depth=0):
       ret = True
       results = []
       for i, code in enumerate(code_blocks):
            print(f"\n📊 执行代码块 {i+1}/{len(code_blocks)}:")
            self._console.print(Markdown(f"```python\n{code}\n```"))
            success, output = self.exec(code)
            print("\n🔄 执行结果:")
            if success:
                print(f"✅ 执行成功:\n{output}")
                results.append(f"代码块 {i+1}: 执行成功")
            else:
                print(f"❌ 执行失败:\n{output}")
                results.append(f"代码块 {i+1}: 执行失败 - {output}")

            feedback_response, ok = self.send_feedback(code, success, output)

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
