#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import Counter
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import openai
import requests
import anthropic
from rich import print

from .i18n import T

@dataclass
class ChatMessage:
    role: str
    content: str
    reason: str = None
    usage: Counter = field(default_factory=Counter)

class ChatHistory:
    def __init__(self):
        self.messages = []
        self._total_tokens = 0

    def __len__(self):
        return len(self.messages)
    
    def add(self, role, content):
        self.add_message(ChatMessage(role=role, content=content))

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        self._total_tokens += message.usage["total_tokens"]

    @property
    def total_tokens(self):
        return self._total_tokens

    def get_messages(self):
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

class BaseClient(ABC):
    def __init__(self, config):
        self.name = None
        self.console = None
        self.max_tokens = config.get("max_tokens")
        self._model = config["model"]
        self._timeout = config.get("timeout")
        self._api_key = config.get("api_key")
        self._base_url = config.get("base_url")

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.name}>({self._model}, {self._max_tokens})"
    
    @abstractmethod
    def get_completion(self, messages):
        pass
        
    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    @abstractmethod
    def parse_response(self, response):
        pass

    def __call__(self, history, prompt, system_prompt=None):
        # We shall only send system prompt once
        if not history and system_prompt:
            self.add_system_prompt(history, system_prompt)
        history.add("user", prompt)

        response = self.get_completion(history.get_messages())
        if response:
            msg = self.parse_response(response)
            history.add_message(msg)
            if msg.reason:
                response = f"{T('think')}:\n---\n{msg.reason}\n---\n{msg.content}"
            else:
                response = msg.content
        return response
    
class OpenAIClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._client = openai.Client(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)

    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    def parse_response(self, response):
        usage = response.usage.model_dump()
        message = response.choices[0].message
        reason = getattr(message, "reasoning_content", None)
        return ChatMessage(
            role=message.role,
            content=message.content,
            reason=reason,
            usage=Counter(usage))

    def get_completion(self, messages):
        try:
            response = self._client.chat.completions.create(
                model = self._model,
                messages = messages,
                stream=False,
                max_tokens = self.max_tokens
            )
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T('call_failed')}: [yellow]{str(e)}")
            response = None
        return response
    
class OllamaClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._session = requests.Session()

    def parse_response(self, response):
        msg = response["message"]
        return ChatMessage(role=msg['role'], content=msg['content'])
    
    def get_completion(self, messages):
        try:
            response = self._session.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": self.max_tokens}
                },
                timeout=self._timeout
            )
            response.raise_for_status()
            response = response.json()
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T('call_failed')}: [yellow]{str(e)}")
            response = None
        return response

class ClaudeClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout)

    def parse_response(self, response):
        usage = Counter(response.usage)
        content = response.content[0].text
        role = response.role
        return ChatMessage(
            role=role,
            content=content,
            usage=usage)
    
    def add_system_prompt(self, history, system_prompt):
        self._system_prompt = system_prompt

    def get_completion(self, messages):
        try:
            message = self._client.messages.create(
                model = self._model,
                messages = messages,
                system=self._system_prompt,
                max_tokens = self.max_tokens
            )
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T('call_failed')}: [yellow]{str(e)}")
            message = None
        return message
    
class LLM(object):
    CLIENTS = {
        "openai": OpenAIClient,
        "ollama": OllamaClient,
        "claude": ClaudeClient
    }

    def __init__(self, console, configs, max_tokens=None):
        self.llms = {}
        self.console = console
        self.default = None
        self._last = None
        self.history = ChatHistory()
        self.max_tokens = max_tokens
        for name, config in configs.items():
            if not config.get('enable', True):
                console.print(f"LLM: [yellow]ignore '{name}'")
                continue

            try:
                client = self.get_client(config)
            except Exception as e:
                console.print(f"LLM: [red]init '{name}' failed: [yellow]{str(e)}")
                continue
            
            client.name = name
            client.console = console
            if not client.max_tokens:
                client.max_tokens = self.max_tokens
            self.llms[name] = client

            if config.get('default', False) and not self.default:
                self.default = client
                console.print(f"LLM: [green]init '{name}' success ([yellow]default)")
            else:
                console.print(f"LLM: [green]init '{name}' success")
        if not self.llms:
            raise Exception("No available LLM")
        if not self.default:
            name = list(self.llms.keys())[0]
            console.print(f"LLM: [yellow]use '{name}' as default")
            self.default = self.llms[name]
        self.current = self.default

    def __repr__(self):
        return f"Current: {'default' if self.current == self.default else self.current}, Default: {self.default}"
    
    @property
    def last(self):
        return self._last.name if self._last else None
    
    def get_last_message(self, role='assistant'):
        return self.history.get_last_message(role)
    
    def clear(self):
        self.history = ChatHistory()

    def get_client(self, config):
        proto = config.get("type", "openai")
        model = config.get("model")
        max_tokens = config.get("max_tokens") or self.max_tokens
        timeout = config.get("timeout")

        client = self.CLIENTS.get(proto.lower())
        if not client:
            raise ValueError(f"Unsupported LLM provider: {proto}")
        return client(config)
    
    def __contains__(self, name):
        return name in self.llms
    
    def use(self, name):
        llm = self.llms.get(name)
        if not llm:
            self.console.print(f"[red]LLM: {name} not found")
        else:
            self.current = llm
            self.console.print(f"[green]LLM: use {name}")

    def __call__(self, instruction, system_prompt=None, name=None):
        """ LLM 选择规则
        1. 如果 name 为 None, 使用 current
        2. 如果 name 存在，使用 name 对应的
        3. 使用 default
        """
        if not name:
            llm = self.current
        else:
            llm = self.llms.get(name, self.default)
        self._last = llm
        return llm(self.history, instruction, system_prompt=system_prompt)
    