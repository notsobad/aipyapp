from .base import BaseCommand

class GitCommand(BaseCommand):
    name = 'git'
    description = 'Git operations'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate operation')
        
    def add_subcommands(self, subparsers):
        # Commit subcommand
        commit_parser = subparsers.add_parser('commit', help='Commit changes')
        commit_parser.add_argument('--amend', action='store_true', help='Amend previous commit')
        commit_parser.add_argument('--message', '-m', nargs='?', type=str, help='Commit message')
        
        # Status subcommand
        status_parser = subparsers.add_parser('status', help='Show repository status')
        status_parser.add_argument('--short', action='store_true', help='Show short status')
        status_parser.add_argument('--branch', action='store_true', help='Show branch info')
        
        # Push subcommand
        push_parser = subparsers.add_parser('push', help='Push changes')
        push_parser.add_argument('--force', action='store_true', help='Force push')
        push_parser.add_argument('--remote', type=str, help='Remote repository')
        
    def execute(self, args, registry=None):
        subcommand = getattr(args, 'subcommand', None)
        print(f"Git {subcommand or 'main'} executed with args: {args}")
        