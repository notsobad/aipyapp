#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from abc import ABC, abstractmethod

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
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()
