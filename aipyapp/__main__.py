#!/usr/bin/env python
# coding: utf-8

def main():
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        parser.add_argument('-p', '--python', default=False, action='store_true', help="Python mode")
        parser.add_argument('-g', '--gui', default=False, action='store_true', help="GUI mode")
        parser.add_argument('cmd', nargs='?', default=None, help="Task to execute, e.g. 'Who are you?'")
        return parser.parse_args()
    
    args = parse_args()
    if args.python:
        from .main import main as aipy_main
    elif args.gui:
        from .gui import main as aipy_main
    else:
        from .saas import main as aipy_main
    aipy_main(args)

if __name__ == '__main__':
    main()
