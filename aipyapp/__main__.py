#!/usr/bin/env python
# coding: utf-8

import os
import sys
import argparse
from pathlib import Path

from .aipy.config import CONFIG_DIR

config_help_message = (
    f"Specify the configuration directory.\nDefaults to {CONFIG_DIR} if not provided."
)

def ensure_wxpython():
    try:
        import wx
    except:
        import subprocess

        cp = subprocess.run([sys.executable, "-m", "pip", "install", 'wxpython'])
        assert cp.returncode == 0

def parse_args():
    parser = argparse.ArgumentParser(description="Python use - AIPython", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-c", '--config-dir', type=str, help=config_help_message)
    parser.add_argument('-p', '--python', default=False, action='store_true', help="Python mode")
    parser.add_argument('-g', '--gui', default=False, action='store_true', help="GUI mode")
    parser.add_argument('--debug', default=False, action='store_true', help="Debug mode")
    parser.add_argument('cmd', nargs='?', default=None, help="Task to execute, e.g. 'Who are you?'")
    return parser.parse_args()

def mainw():
    devnull = open(os.devnull, 'w')
    sys.stdout = devnull
    sys.stderr = devnull
    args = parse_args()
    ensure_wxpython()
    from .wxgui import main as aipy_main
    aipy_main(args)

def main():
    args = parse_args()
    if args.python:
        from .main import main as aipy_main
    elif args.gui:
        ensure_wxpython()
        from .wxgui import main as aipy_main
    else:
        from .saas import main as aipy_main
    aipy_main(args)

if __name__ == '__main__':
    main()
