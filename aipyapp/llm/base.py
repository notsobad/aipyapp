#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from abc import ABC, abstractmethod

from loguru import logger

from .. import Stoppable, T

class BaseClient(ABC, Stoppable):
    MODEL = None
    BASE_URL = None
    RPS = 2
    MAX_TOKENS = 8192
    PARAMS = {}

    def __init__(self, config):
        super().__init__()
        self.name = None
        self.console = None
        self.max_tokens = config.get("max_tokens") or self.MAX_TOKENS
        self._model = config.get("model") or self.MODEL
        self._timeout = config.get("timeout")
        self._api_key = config.get("api_key")
        self._base_url = config.get("base_url") or self.BASE_URL
        self._stream = config.get("stream", True)
        self._client = None
        self._params = {}
        if self.PARAMS:
            self._params.update(self.PARAMS)
        temperature = config.get("temperature")
        if temperature != None and temperature >= 0 and temperature <= 1:
            self._params['temperature'] = temperature
        self.log = logger.bind(src='client', name=self.name)
        
    def __repr__(self):
        return f"{self.__class__.__name__}<{self.name}>: ({self._model}, {self._base_url})"

    def usable(self):
        return self._model
    
    def _get_client(self):
        return self._client
    
    @abstractmethod
    def get_completion(self, messages):
        pass
        
    def add_system_prompt(self, messages, system_prompt):
        messages.append({"role": "system", "content": system_prompt})

    @abstractmethod
    def _parse_usage(self, response):
        pass

    @abstractmethod
    def _parse_stream_response(self, response):
        pass

    @abstractmethod
    def _parse_response(self, response):
        pass

    def parse_response(self, response):
        if self._stream:    
            response = self._parse_stream_response(response)
        else:
            response = self._parse_response(response)
        return response
    
    def __call__(self, messages, prompt, system_prompt=None):
        # We shall only send system prompt once
        if system_prompt:
            self.add_system_prompt(messages, system_prompt)
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        self.console.record = False
        with self.console.status(f"[dim white]{T("Sending task to {}", self.name)} ..."):
            response = self.get_completion(messages)
        self.console.record = True
        end = time.time()
        if response:
            msg = self.parse_response(response)
            msg.name = self.name
            msg.usage['time'] = round(end - start, 3)
            response = msg
        return response
    
