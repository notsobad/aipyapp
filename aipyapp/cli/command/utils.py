from rich import print
from rich.table import Table
import random

COLORS = ["red", "green", "blue", "yellow", "magenta", "cyan", "white", "bright_red", "bright_green", "bright_blue", "bright_yellow", "bright_magenta", "bright_cyan"]

def print_table(rows, title=None, columns=None):
    table = Table(title=title, show_lines=True)
    for column in columns:  
        # 为每一列随机选择一个颜色
        color = random.choice(COLORS)
        table.add_column(column, justify="center", style=f"bold {color}", no_wrap=True)
    for row in rows:
        table.add_row(*row)
    print(table)