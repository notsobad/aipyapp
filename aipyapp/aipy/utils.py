#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import errno
import time
from pathlib import Path
from typing import Union
from functools import wraps
from importlib.resources import read_text

from loguru import logger
from rich.panel import Panel

from .. import T, __respkg__

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

def confirm_disclaimer(console):
    DISCLAIMER_TEXT = read_text(__respkg__, "DISCLAIMER.md")
    console.print()
    panel = Panel.fit(DISCLAIMER_TEXT, title="[red]免责声明", border_style="red", padding=(1, 2))
    console.print(panel)

    while True:
        console.print("\n[red]是否确认已阅读并接受以上免责声明？[/red](yes/no):", end=" ")
        response = input().strip().lower()
        if response in ("yes", "y"):
            console.print("[green]感谢确认，程序继续运行。[/green]")
            return True
        elif response in ("no", "n"):
            console.print("[red]您未接受免责声明，程序将退出。[/red]")
            return False
        else:
            console.print("[yellow]请输入 yes 或 no。[/yellow]")

def safe_rename(path: Path, input_str: str, max_length=16, max_retries=3) -> Path:
    input_str = input_str.strip()
    safe_str = re.sub(r'[\\/:*?"<>|\s]', '', input_str).strip()
    if not safe_str:
        safe_str = "Task"

    name = safe_str[:max_length]
    # 对于目录，suffix 为空，所以直接使用名称
    new_path = path.parent / f"{name}{path.suffix}"
    counter = 1

    while True:
        if not new_path.exists():
            # 添加重试机制处理 PermissionError
            for attempt in range(max_retries):
                try:
                    path.rename(new_path)
                    return new_path  # 成功时返回新路径
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        # 指数退避重试：1秒、2秒、4秒
                        delay = 2 ** attempt
                        time.sleep(delay)
                        continue
                    else:
                        # 重试失败，返回原路径并记录警告
                        logger.warning(f"重命名失败（权限错误），使用原路径: {path} -> {new_path}")
                        return path
                except FileExistsError:
                    # 并发创建导致的文件已存在，跳出重试循环，继续尝试下一个名称
                    break
                except OSError as e:
                    if e.errno in (errno.EEXIST, errno.ENOTEMPTY):
                        # 文件或目录已存在，继续尝试下一个名称
                        break
                    else:
                        # 其他错误，重新抛出
                        raise

        # 如果新路径已存在或重试失败，尝试下一个名称
        new_path = path.parent / f"{name}_{counter}{path.suffix}"
        counter += 1

def validate_file(path: Union[str, Path]) -> None:
    """验证文件格式和存在性"""
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")
    
    if not path.name.endswith('.json'):
        raise ValueError("Task file must be a .json file")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
