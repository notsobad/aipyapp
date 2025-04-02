#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
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

def confirm(console, msg, prompt, default="n", auto=None):
    console.print(msg)
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

def get_uv_from_venv():
    venv_path = os.getenv("VIRTUAL_ENV")
    if not venv_path:
        print("VIRTUAL_ENV is not set.")
        return None
    
    cfg_path = os.path.join(venv_path, "pyvenv.cfg")
    if not os.path.exists(cfg_path):
        print(f"pyvenv.cfg not found in {venv_path}")
        return None
    
    uv_value = None
    with open(cfg_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("uv ="):
                _, uv_value = map(str.strip, line.split("=", 1))
                break
    
    return uv_value

def uv_install_packages(console, packages):
    uvv = get_uv_from_venv()
    if not uvv:
        console.print("[red]Not in uv venv, can't install packages")
        return False
    
    console.print(f"[green]Install packages: {', '.join(packages)} with uv {uvv}")
    cp = subprocess.run(['uv', "add"] + packages)
    return cp.returncode == 0