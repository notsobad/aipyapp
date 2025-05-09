#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess

__cache__ = set()

def ensure_packages(*packages, upgrade=False, quiet=False):
    """
    安装多个 pip 包。包名以位置参数传入，其它选项必须使用关键字参数。

    参数：
        *packages: 位置参数，例如 'requests>=2.0'
        upgrade (keyword-only): 是否使用 --upgrade
        quiet (keyword-only): 是否静默安装（-q）
    """
    if not packages:
        return True

    packages = list(set(packages) - __cache__)
    if not packages:
        return True
    
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    if quiet:
        cmd.append("-q")
    cmd.extend(packages)

    try:
        subprocess.check_call(cmd)
        __cache__.update(packages)
        return True
    except subprocess.CalledProcessError:
        #TODO: use logger
        pass
        #print("依赖安装失败:", " ".join(packages))
    
    return False


def ensure_requirements(path="requirements.txt", **kwargs):
    with open(path) as f:
        reqs = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return ensure_requirements(reqs, **kwargs)


if __name__ == "__main__":
    ensure_packages("requests>=2.25", "openai>=1.68.2", "pandas>=2.2.3")
    ensure_packages("requests>=2.25", "openai>=1.68.2", "pandas>=2.2.3")
