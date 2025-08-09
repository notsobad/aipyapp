#!/usr/bin/env python
# coding: utf-8

import os
import sys

if "pythonw" in sys.executable.lower():
    sys.stdout = open(os.devnull, "w", encoding='utf-8')
    sys.stderr = open(os.devnull, "w", encoding='utf-8')

from loguru import logger

logger.remove()
from .aipy.config import CONFIG_DIR
logger.add(CONFIG_DIR / "aipyapp.log", format="{time:HH:mm:ss} | {level} | {message} | {extra}", level='INFO')

def parse_args():
    import argparse
    config_help_message = (
        f"Specify the configuration directory.\nDefaults to {CONFIG_DIR} if not provided."
    )

    parser = argparse.ArgumentParser(description="Python use - AIPython", formatter_class=argparse.RawTextHelpFormatter)
    
    # 添加子命令支持
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # update 子命令
    update_parser = subparsers.add_parser('update', help='Update aipyapp to latest version')
    update_parser.add_argument('--beta', action='store_true', help='Include beta versions in update')
    
    # 主命令参数
    parser.add_argument("-c", '--config-dir', type=str, help=config_help_message)
    parser.add_argument('-p', '--python', default=False, action='store_true', help="Python mode")
    parser.add_argument('-i', '--ipython', default=False, action='store_true', help="IPython mode")
    parser.add_argument('-g', '--gui', default=False, action='store_true', help="GUI mode")
    parser.add_argument('--debug', default=False, action='store_true', help="Debug mode")
    parser.add_argument('--style', default=None, help="Style of the display, e.g. 'classic' or 'modern'")
    parser.add_argument('--role', default=None, help="Role to use")
    parser.add_argument('-f', '--fetch-config', default=False, action='store_true', help="login to trustoken and fetch token config")
    parser.add_argument('--agent', default=False, action='store_true', help="Agent mode - HTTP API server for n8n integration")
    parser.add_argument('--port', type=int, default=8848, help="Port for agent mode HTTP server (default: 8848)")
    parser.add_argument('--host', default='127.0.0.1', help="Host for agent mode HTTP server (default: 127.0.0.1)")
    parser.add_argument('cmd', nargs='?', default=None, help="Task to execute, e.g. 'Who are you?'")
    return parser.parse_args()

def ensure_pkg(pkg):
    try:
        if pkg == 'wxpython':
            import wx
        elif pkg == 'ipython':
            import IPython
        elif pkg == 'fastapi':
            import fastapi
        elif pkg == 'uvicorn':
            import uvicorn
    except ImportError:
        import subprocess
        print(f"Installing required package: {pkg}")
        cp = subprocess.run([sys.executable, "-m", "pip", "install", pkg])
        assert cp.returncode == 0

def handle_update(args):
    """处理 update 命令"""
    import subprocess
    from . import __version__
    
    package_name = 'aipyapp'
    print(f"当前版本: {__version__}")
    
    if args.beta:
        print(f"更新到最新版本 (包括测试版): {package_name}")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--pre", package_name]
    else:
        print(f"更新到最新稳定版本: {package_name}")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package_name]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("更新完成!")
        if result.stdout.strip():
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"更新失败: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"更新失败: {str(e)}")
        sys.exit(1)

def mainw():
    args = parse_args()
    ensure_pkg('wxpython')
    from .gui.main import main as aipy_main
    aipy_main(args)

def main():
    args = parse_args()
    
    # 处理 update 子命令
    if args.command == 'update':
        handle_update(args)
        return
    
    if args.agent:
        ensure_pkg('fastapi')
        ensure_pkg('uvicorn')
        from .cli.cli_agent import main as aipy_main
    elif args.python:
        from .cli.cli_python import main as aipy_main
    elif args.ipython:
        ensure_pkg('ipython')
        from .cli.cli_ipython import main as aipy_main
    elif args.gui:
        ensure_pkg('wxpython')
        from .gui.main import main as aipy_main
    else:
        from .cli.cli_task import main as aipy_main
    aipy_main(args)

if __name__ == '__main__':
    main()
