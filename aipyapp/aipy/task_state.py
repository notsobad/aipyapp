#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, TYPE_CHECKING, Literal, List
from collections import OrderedDict

from pydantic import BaseModel, Field
from loguru import logger

from .event_recorder import EventRecords


if TYPE_CHECKING:
    from .task import Task, Step

# 任务版本常量
TASK_VERSION = 20250806

def validate_file(path: Union[str, Path]) -> None:
    """验证文件格式和存在性"""
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")
    
    if not path.name.endswith('.json'):
        raise ValueError("Task file must be a .json file")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
        
class TaskStateError(Exception):
    """任务状态异常"""
    pass

class TaskState(BaseModel):
    """任务状态管理器 - 封装任务状态的序列化、反序列化和文件操作"""
    
    version: int = Field(default=TASK_VERSION, frozen=True)
    task_id: str
    instruction: str
    start_time: Optional[float] = None
    done_time: Optional[float] = None

    records: EventRecords | None = None
    steps: Any
    context_manager: Any

    def model_post_init(self, __context: Any):
        self._log = logger.bind(src='task_state')

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'TaskState':
        """从文件创建 TaskState 对象"""
        path = Path(path)
        validate_file(path)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                instance = cls.model_validate_json(f.read())
                logger.info('Loaded task state from file', path=str(path), task_id=instance.task_id)
        except json.JSONDecodeError as e:
            raise TaskStateError(f'Invalid JSON file: {e}') from e
        except Exception as e:
            raise TaskStateError(f'Failed to load task state: {e}') from e
    
        return instance
    
    @classmethod
    def from_task(cls, task: 'Task') -> 'TaskState':
        """从 Task 对象提取状态"""
        instance = cls(
            task_id=task.task_id,
            instruction=task.instruction,
            start_time=task.start_time,
            done_time=task.done_time,
            records=task.event_recorder.records if task.event_recorder is not None else None,
            steps=task.steps,
            context_manager=task.context_manager.get_state(),
        )
        return instance
        
    def restore_to_task(self, task: 'Task') -> None:
        """恢复状态到 Task 对象"""
        # 验证版本兼容性
        if self.version != TASK_VERSION:
            raise TaskStateError(f'Task version mismatch: expected {TASK_VERSION}, got {self.version}')
        
        # 恢复任务基本信息
        task.task_id = self.task_id
        task.instruction = self.instruction
        task.start_time = self.start_time
        task.done_time = self.done_time
        
        task.step_manager.restore_state(self.steps)
        task.context_manager.restore_state(self.context_manager)
        task.code_blocks.restore_state(self.blocks)
        
        if task.event_recorder:
            task.event_recorder.records = self.records
        
        self.log.info('Restored state to task', task_id=self.task_id)
    
    def save_to_file(self, path: Union[str, Path]) -> None:
        """保存到文件"""
        path = Path(path)
        
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 更新完成时间
        if not self.done_time:
            self.done_time = time.time()
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.model_dump_json(indent=2, exclude_none=True))
            self._log.info('Saved task state to file', path=str(path))
        except Exception as e:
            self._log.exception('Failed to save task state', path=str(path))
            raise TaskStateError(f'Failed to save task state: {e}') from e
    
    def get_summary(self) -> Dict[str, Any]:
        """获取状态摘要信息"""
        return {
            'version': self.version,
            'task_id': self.task_id,
            'instruction': self.instruction[:50] + '...' if self.instruction and len(self.instruction) > 50 else self.instruction,
            'start_time': self.start_time,
            'done_time': self.done_time,
        }
    
    def __repr__(self):
        return f"<TaskState task_id={self.task_id}, version={self.version}>"