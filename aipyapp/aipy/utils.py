#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import subprocess
from functools import wraps

from .i18n import T

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

def confirm(console, prompt, default="n", auto=None):
    if auto in (True, False):
        console.print(f"✅ {T('auto_confirm')}")
        return auto
    while True:
        response = console.input(prompt).strip().lower()
        if not response:
            response = default
        if response in ["y", "n"]:
            break
    return response == "y"

def install_packages(console, packages):
    console.print(f"[green]Install packages: {', '.join(packages)} with pip")
    cp = subprocess.run([sys.executable, "-m", "pip", "install"] + packages)
    return cp.returncode == 0