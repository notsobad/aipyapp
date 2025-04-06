#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import openai
import requests
import anthropic

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
        self._total_tokens = Counter()

    def __len__(self):
        return len(self.messages)
    
    def json(self):
        return [msg.__dict__ for msg in self.messages]
    
    def add(self, role, content):
        self.add_message(ChatMessage(role=role, content=content))

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        self._total_tokens += message.usage

    def get_usage(self):
        return iter(row.usage for row in self.messages if row.role == "assistant")
    
    def get_summary(self):
        summary = dict(self._total_tokens)
        summary['rounds'] = sum(1 for row in self.messages if row.role == "assistant")
        return summary

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
        return f"{self.__class__.__name__}<{self.name}>({self._model}, {self.max_tokens})"
    
    @abstractmethod
    def get_completion(self, messages):
        pass
        
    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    @abstractmethod
    def parse_usage(self, response):
        pass

    @abstractmethod
    def parse_response(self, response):
        pass

    def __call__(self, history, prompt, system_prompt=None):
        # We shall only send system prompt once
        if not history and system_prompt:
            self.add_system_prompt(history, system_prompt)
        history.add("user", prompt)

        start = time.time()
        response = self.get_completion(history.get_messages())
        end = time.time()
        if response:
            msg = self.parse_response(response)
            usage = self.parse_usage(response)
            usage['time'] = round(end - start, 3)
            msg.usage = Counter(usage)
            history.add_message(msg)
            if msg.reason:
                response = f"{T('think')}:\n---\n{msg.reason}\n---\n{msg.content}"
            else:
                response = msg.content
        return response

# https://platform.openai.com/docs/api-reference/chat/create
# https://api-docs.deepseek.com/api/create-chat-completion
class OpenAIClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._client = openai.Client(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)

    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    def parse_usage(self, response):
        usage = response.usage
        return {'total_tokens': usage.total_tokens,
                'input_tokens': usage.prompt_tokens,
                'output_tokens': usage.completion_tokens}
    
    def parse_response(self, response):
        message = response.choices[0].message
        reason = getattr(message, "reasoning_content", None)
        return ChatMessage(
            role=message.role,
            content=message.content,
            reason=reason
        )

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

# https://github.com/ollama/ollama/blob/main/docs/api.md
class OllamaClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._session = requests.Session()

    def parse_usage(self, response):
        ret = {'input_tokens': response['prompt_eval_count'], 'output_tokens': response['eval_count']}
        ret['total_tokens'] = ret['input_tokens'] + ret['output_tokens']
        return ret
    
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

# https://docs.anthropic.com/en/api/messages
class ClaudeClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout)

    def parse_usage(self, response):
        usage = response.usage
        ret = {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens}
        ret['total_tokens'] = ret['input_tokens'] + ret['output_tokens']
        return ret
    
    def parse_response(self, response):
        content = response.content[0].text
        role = response.role
        return ChatMessage(role=role, content=content)
    
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
        names = defaultdict(set)
        for name, config in configs.items():
            if not config.get('enable', True):
                names['disabled'].add(name)
                continue

            try:
                client = self.get_client(config)
            except Exception as e:
                names['error'].add(name)
                continue
            
            names['available'].add(name)
            client.name = name
            client.console = console
            if not client.max_tokens:
                client.max_tokens = self.max_tokens
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
        self.console.record = False
        with self.console.status(f"[dim white]{llm.name} {T('thinking')}..."):
            ret = llm(self.history, instruction, system_prompt=system_prompt)
        self.console.record = True
        return ret
    