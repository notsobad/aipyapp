#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Optional, Protocol

from loguru import logger

class Trackable(ABC):
    """可追踪对象接口"""
    
    @abstractmethod
    def get_checkpoint(self) -> Any:
        """获取当前检查点状态"""
        pass
    
    @abstractmethod
    def restore_to_checkpoint(self, checkpoint: Optional[Any]):
        """恢复到指定检查点，None表示恢复到初始状态"""
        pass

class Runtime(ABC):
    @abstractmethod
    def install_packages(self, packages):
        pass

    @abstractmethod
    def getenv(self, name, desc=None):
        pass

class ConsoleInterface(ABC):
    @abstractmethod
    def print(self, *args, sep=' ', end='\n', file=None, flush=False):
        pass

    @abstractmethod
    def input(self, prompt=''):
        pass

    @abstractmethod
    def status(self, msg):
        pass

class Stoppable():
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def on_stop(self):
        pass

    def stop(self):
        self._stop_event.set()
        self.on_stop()
        
    def is_stopped(self):
        return self._stop_event.is_set()
    
    def wait(self, timeout=None):
        return self._stop_event.wait(timeout)
    
    def reset(self):
        self._stop_event.clear()

class Event:
    def __init__(self, name: str, **data):
        self.name = name
        self.data = data

    def __str__(self):
        return f"{self.name}: {self.data}"
    
    def __getattr__(self, name: str):
        return self.data.get(name)

EventHandler = Callable[[Event], None]

class EventListener(Protocol):
    def on_event(self, event: Event) -> None:
        """事件Fallback处理函数"""
        ...

class EventBus:
    def __init__(self):
        super().__init__()
        self._listeners: Dict[str, List[EventHandler]] = {}
        self._eb_logger = logger.bind(src=self.__class__.__name__)
    
    def on_event(self, event_name: str, handler: EventHandler):
        self._listeners.setdefault(event_name, []).append(handler)

    def add_listener(self, obj: EventListener):
        for event_name in dir(obj):
            if not event_name.startswith('on_'):
                continue

            handler = getattr(obj, event_name)
            if callable(handler):
                event_name = event_name[3:]
                self.on_event(event_name, handler)
                self._eb_logger.info(f"Registered event {event_name} for {obj.__class__.__name__}")

    def emit(self, event_name: str, **kwargs):
        event = Event(event_name, **kwargs)
        for handler in self._listeners.get(event_name, []):
            try:
                handler(event)
            except Exception as e:
                self._eb_logger.exception(f"Error emitting event {event_name}")
        return event