#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import defaultdict

from loguru import logger

from .base_openai import OpenAIBaseClient
from .client_ollama import OllamaClient
from .client_claude import ClaudeClient
from .session import ChatHistory
from .. import Stoppable, event_bus, T

class OpenAIClient(OpenAIBaseClient): 
    MODEL = 'gpt-4o'
    PARAMS = {'stream_options': {'include_usage': True}}

class GeminiClient(OpenAIBaseClient): 
    BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/'
    MODEL = 'gemini-2.5-pro-exp-03-25'
    PARAMS = {'stream_options': {'include_usage': True}}

class DeepSeekClient(OpenAIBaseClient): 
    BASE_URL = 'https://api.deepseek.com'
    MODEL = 'deepseek-chat'

class GrokClient(OpenAIBaseClient): 
    BASE_URL = 'https://api.x.ai/v1/'
    MODEL = 'grok-3-mini'
    PARAMS = {'stream_options': {'include_usage': True}}

class TrustClient(OpenAIBaseClient): 
    BASE_URL = 'https://api.trustoken.ai/v1'
    MODEL = 'auto'
    PARAMS = {'stream_options': {'include_usage': True}}

class AzureOpenAIClient(OpenAIBaseClient): 
    MODEL = 'gpt-4o'

    def __init__(self, config):
        super().__init__(config)
        self._end_point = config.get('endpoint')

    def usable(self):
        return super().usable() and self._end_point
    
    def _get_client(self):
        from openai import AzureOpenAI
        return AzureOpenAI(azure_endpoint=self._end_point, api_key=self._api_key, api_version="2024-02-01")

CLIENTS = {
    "openai": OpenAIClient,
    "ollama": OllamaClient,
    "claude": ClaudeClient,
    "gemini": GeminiClient,
    "deepseek": DeepSeekClient,
    'grok': GrokClient,
    'trust': TrustClient,
    'azure': AzureOpenAIClient
}

class ClientManager(object):
    def __init__(self, settings, console, system_prompt=None):
        self.llms = {}
        self.console = console
        self.default = None
        self._last = None
        self.log = logger.bind(src='llm')
        self.history = ChatHistory()
        self.system_prompt = system_prompt
        names = defaultdict(set)
        for name, config in settings.llm.items():
            if not config.get('enable', True):
                names['disabled'].add(name)
                continue

            try:
                client = self.get_client(config)
            except Exception as e:
                self.console.print_exception()
                self.log.exception('Error creating LLM client', name=name, config=config)
                names['error'].add(name)
                continue
            
            names['enabled'].add(name)
            client.name = name
            client.console = console
            self.llms[name] = client

            if config.get('default', False) and not self.default:
                self.default = client
                names['default'] = name

        if not self.default:
            name = list(self.llms.keys())[0]
            self.default = self.llms[name]
            names['default'] = name
        self.current = self.default
        self.names = names

    def __len__(self):
        return len(self.llms)
    
    def __repr__(self):
        return f"Current: {'default' if self.current == self.default else self.current}, Default: {self.default}"
    
    @property
    def enabled(self):
        return self.names['enabled']
    
    @property
    def last(self):
        return self._last.name if self._last else None
    
    def get_last_message(self, role='assistant'):
        return self.history.get_last_message(role)
    
    def clear(self):
        self.history = ChatHistory()

    def get_client(self, config):
        proto = config.get("type", "openai")

        client = CLIENTS.get(proto.lower())
        if not client:
            self.log.error('Unsupported LLM provider', proto=proto)
            raise ValueError(f"Unsupported LLM provider: {proto}")
        return client(config)
    
    def __contains__(self, name):
        return name in self.llms
    
    def use(self, name):
        llm = self.llms.get(name)
        if llm and llm.usable():
            self.current = llm
            return True
        return False
    
    def stop(self):
        if self._last:
            self._last.stop()

    def __call__(self, instruction, *, system_prompt=None, name=None):
        """ LLM 选择规则
        1. 如果 name 为 None, 使用 current
        2. 如果 name 存在，使用 name 对应的
        3. 使用 default
        """
        if not name:
            llm = self.current
        else:
            llm = self.llms.get(name, self.default)

        if not llm.usable():
            self.console.print(f"[red]LLM: {name} {T("Not usable")}")
            return None
        
        self._last = llm
        ret = llm(self.history, instruction, system_prompt=system_prompt)
        event_bus.broadcast('response_complete', {'llm': llm.name, 'content': ret})
        return ret
