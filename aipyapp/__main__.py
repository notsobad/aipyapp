#!/usr/bin/env python
# coding: utf-8

from .main import main as main1
from .saas import main as main2

def main():
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        parser.add_argument('-p', '--python', default=False, action='store_true', help="Python mode")
        parser.add_argument('cmd', nargs='?', default=None, help="Command to execute")
        return parser.parse_args()
    args = parse_args()
    if args.python:
        main1(args)
    else:
        main2(args)

if __name__ == '__main__':
    main()
