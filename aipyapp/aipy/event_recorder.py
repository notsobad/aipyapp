#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from loguru import logger

from ..interface import Trackable
from .events import BaseEvent

class EventRecords(BaseModel):
    start_time: Optional[float] = Field(default=None)
    end_time: Optional[float] = Field(default=None)
    events: List[BaseEvent.get_subclasses_union()] = Field(default_factory=list)

class EventRecorder(Trackable):
    """事件记录器 - 记录任务执行过程中的所有重要事件"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled  
        self.records = EventRecords()
        self.log = logger.bind(src='event_recorder')
    
    @property
    def events(self) -> List[BaseEvent]:
        """获取所有事件"""
        return self.records.events
    
    def start_recording(self):
        """开始记录"""
        self.records.start_time = time.time()
        self.records.events.clear()
        self.log.info('Started event recording')
    
    def stop_recording(self):
        """停止记录"""
        if self.records.start_time:
            self.records.end_time = time.time()
            self.log.info(f'Stopped event recording, total events: {len(self.records.events)}')
    
    def record_event(self, event: BaseEvent):
        """记录事件
        
        Args:
            event: 事件对象
        """
        self.records.events.append(event)
        
        # 记录调试信息（简化版本，避免logger level检查）
        if len(self.events) % 100 == 0:  # 每100个事件记录一次调试信息
            self.log.debug(f'Recorded {len(self.records.events)} events, latest: {event.name} at {event.timestamp:.3f}s')
    
    def clear_events(self):
        """清空所有事件"""
        self.records.events.clear()
        self.log.info('Cleared all events')
    
    # Trackable接口实现
    def get_checkpoint(self) -> int:
        """获取当前检查点状态 - 返回事件数量"""
        return len(self.records.events)
    
    def restore_to_checkpoint(self, checkpoint: Optional[int]):
        """恢复到指定检查点"""
        if checkpoint is None:
            # 恢复到初始状态
            self.clear_events()
        else:
            # 恢复到指定事件数量
            if checkpoint < len(self.records.events):
                deleted_count = len(self.records.events) - checkpoint
                self.records.events = self.records.events[:checkpoint]
                self.log.info(f'Restored to checkpoint {checkpoint}, deleted {deleted_count} events')
    
    def get_summary(self) -> Dict[str, Any]:
        """获取事件摘要统计"""
        if not self.records.events:
            return {'total_events': 0, 'duration': 0, 'event_types': {}}
        
        # 统计事件类型
        event_types = {}
        for event in self.records.events:
            event_type = event.name
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            'total_events': len(self.records.events),
            'start_time': self.records.start_time,
            'end_time': self.records.end_time,
            'event_types': event_types
        }
    
    def __len__(self):
        """返回事件数量"""
        return len(self.records.events)
    
    def __bool__(self):
        """检查是否有事件"""
        return len(self.records.events) > 0