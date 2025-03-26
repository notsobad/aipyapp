#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from abc import ABC, abstractmethod

import openai
import requests
from rich import print

class History(list):
    def add(self, role, content, reason=None):
        self.append((role, content, reason))

    def get_last_message(self, role='assistant'):
        for msg in reversed(self):
            if msg[0] == role:
                return msg[1]
        return None
    
    def __iter__(self, skip=True):
        for msg in super().__iter__():
            if skip:
                yield {"role": msg[0], "content": msg[1]}
            else:
                yield {"role": msg[0], "content": msg[1], "reason": msg[2]}

class BaseClient(ABC):
    def __init__(self, model, max_tokens):
        self.name = None
        self._model = model
        self._max_tokens = max_tokens
    
    def __repr__(self):
        return f"{self.__class__.__name__}<{self.name}>({self._model}, {self._max_tokens})"
    
    @abstractmethod
    def get_completion(self, messages):
        pass
        
    def __call__(self, history, prompt, system_prompt=None):
        # We shall only send system prompt once
        if not history and system_prompt:
            history.add("system", system_prompt)
        history.add("user", prompt)

        content = self.get_completion(history)
        if content:
            if isinstance(content, str):
                history.add("assistant", content)
            else:
                content, reason = content
                history.add("assistant", content, reason)
                content = f"Think:\n---\n{reason}\n---\n{content}"
        return content
    
class OpenAIClient(BaseClient):
    def __init__(self, model, api_key, base_url=None, max_tokens=None):
        super().__init__(model, max_tokens)
        self._client = openai.Client(api_key=api_key, base_url=base_url)

    def get_completion(self, messages):
        try:
            response = self._client.chat.completions.create(
                model = self._model,
                messages = messages,
                max_tokens = self._max_tokens
            )
            msg = response.choices[0].message
            content = msg.content
            reason = getattr(msg, "reasoning_content", None)
            if reason:
                content = (content, reason)
        except Exception as e:
            print(f"❌ [bold red]OpenAI API 调用失败: [yellow]{str(e)}")
            content = None

        return content
    
class OllamaClient(BaseClient):
    def __init__(self, model, base_url, max_tokens=None):
        super().__init__(model, max_tokens)
        self._session = requests.Session()
        self._base_url = base_url

    def get_completion(self, messages):
        try:
            response = self._session.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": self._max_tokens}
                }
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            print(f"❌ [bold red]Ollama API 调用失败: [yellow]{str(e)}")
            content = None

        return content

class LLM(object):
    def __init__(self, configs, max_tokens=None):
        self.llms = {}
        self.default = None
        self.history = History()
        self.max_tokens = max_tokens
        for name, config in configs.items():
            if config.get('enable', True) is False:
                print(f"LLM: [yellow]ignore '{name}'")
                continue

            try:
                client = self.get_client(config)
            except Exception as e:
                print(f"LLM: [red]init '{name}' failed: [yellow]{str(e)}")
                continue
            
            client.name = name
            self.llms[name] = client
            if config.get('default', False) and not self.default:
                self.default = client
                print(f"LLM: [green]init '{name}' success ([yellow]default)")
            else:
                print(f"LLM: [green]init '{name}' success")
        if not self.default:
            name = list(self.llms.keys())[0]
            print(f"LLM: [yellow]use '{name}' as default")
            self.default = self.llms[name]
        self.current = self.default

    def __repr__(self):
        return f"Current: {'default' if self.current == self.default else self.current}, Default: {self.default}"
    
    def get_last_message(self, role='assistant'):
        return self.history.get_last_message(role)
    
    def clear(self):
        self.history = History()

    def get_client(self, config):
        proto = config.get("type", "openai")
        model = config.get("model")
        max_tokens = config.get("max_tokens") or self.max_tokens
        if proto == "openai":
            return OpenAIClient(
                model,
                config.get("api_key"),
                base_url = config.get("base_url"),
                max_tokens = max_tokens
            )
        elif proto == "ollama":
            return OllamaClient(
                model,
                config.get("base_url"),
                max_tokens = max_tokens
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {proto}")
        
    def __contains__(self, name):
        return name in self.llms
    
    def use(self, name):
        llm = self.llms.get(name)
        if not llm:
            print(f"[red]LLM: {name} not found")
        else:
            self.current = llm
            print(f"[green]LLM: use {name}")

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
        return llm(self.history, instruction, system_prompt=system_prompt)
    