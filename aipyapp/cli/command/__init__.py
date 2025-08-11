"""
命令模块 - 使用新架构的向后兼容版本
"""

# 使用环境变量控制是否启用新架构
import os
USE_NEW_COMMAND_MANAGER = os.environ.get('USE_NEW_COMMAND_MANAGER', 'true').lower() == 'true'

if USE_NEW_COMMAND_MANAGER:
    # 使用新架构（通过适配器保持兼容性）
    from .manager_v2 import (
        CommandManagerV2 as CommandManager,
        CommandError,
        CommandInputError,
        CommandArgumentError,
        InvalidCommandError
    )
else:
    # 使用旧架构
    from .manager import (
        CommandManager,
        CommandError,
        CommandInputError,
        CommandArgumentError,
        InvalidCommandError
    )

# 导出结果类（两个版本共用）
from .result import TaskModeResult, CommandResult

__all__ = [
    'CommandManager',
    'TaskModeResult',
    'CommandError',
    'CommandResult',
    'CommandInputError',
    'CommandArgumentError',
    'InvalidCommandError'
]