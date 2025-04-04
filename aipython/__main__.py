#!/usr/bin/env python
# coding: utf-8

from .main import main as main1
from .saas import main as main2

def main():
    def parse_args():
        import argparse
        parser = argparse.ArgumentParser(description="Python use - AIPython")
        parser.add_argument("-c", '--config', type=str, default=None, help="Toml config file")
        parser.add_argument('--saas', default=False, action='store_true', help="SAAS mode")
        return parser.parse_args()
    args = parse_args()
    if args.saas:
        main2(args)
    else:
        main1(args)

if __name__ == '__main__':
    main()
