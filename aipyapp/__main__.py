#!/usr/bin/env python
# coding: utf-8

from .main import main as main1
from .saas import main as main2
from .gui import main as main3

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
        main1(args)
    elif args.gui:
        main3(args)
    else:
        main2(args)

if __name__ == '__main__':
    main()
