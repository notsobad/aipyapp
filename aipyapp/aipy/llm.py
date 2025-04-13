#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import openai
import requests
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

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
        summary = {'time': 0, 'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        summary.update(dict(self._total_tokens))
        summary['rounds'] = sum(1 for row in self.messages if row.role == "assistant")
        return summary

    def get_messages(self):
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

class BaseClient(ABC):
    MODEL = None
    BASE_URL = None
    RPS = 2

    def __init__(self, config):
        self.name = None
        self.console = None
        self.max_tokens = config.get("max_tokens")
        self._model = config.get("model") or self.MODEL
        self._timeout = config.get("timeout")
        self._api_key = config.get("api_key")
        self._base_url = config.get("base_url") or self.BASE_URL
        self._stream = config.get("stream", True)
        self._client = None

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.name}>({self._model}, {self.max_tokens})"
    
    def usable(self):
        return self._model
    
    def _get_client(self):
        return self._client
    
    @abstractmethod
    def get_completion(self, messages):
        pass
        
    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

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
    
    def __call__(self, history, prompt, system_prompt=None):
        # We shall only send system prompt once
        if not history and system_prompt:
            self.add_system_prompt(history, system_prompt)
        history.add("user", prompt)

        start = time.time()
        self.console.record = False
        with self.console.status(f"[dim white]{T('sending_task', self.name)} ..."):
            response = self.get_completion(history.get_messages())
        self.console.record = True
        end = time.time()
        if response:
            msg = self.parse_response(response)
            msg.usage['time'] = round(end - start, 3)
            history.add_message(msg)
            response = msg.content
        return response

# https://platform.openai.com/docs/api-reference/chat/create
# https://api-docs.deepseek.com/api/create-chat-completion
class OpenAIClient(BaseClient):
    def usable(self):
        return super().usable() and self._api_key
    
    def _get_client(self):
        return openai.Client(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)
    
    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    def _parse_usage(self, usage):
        usage = Counter({'total_tokens': usage.total_tokens,
                'input_tokens': usage.prompt_tokens,
                'output_tokens': usage.completion_tokens})
        return usage
    
    def _parse_stream_response(self, response):
        full_response = ""
        title = f"{self.name} {T('llm_response')}"
        usage = Counter()
        response_panel = None
        with Live(auto_refresh=True, vertical_overflow='visible', transient=True, refresh_per_second=self.RPS) as live:
            status = self.console.status(f"[dim white]{self.name} {T('thinking')}...", spinner='runner')
            response_panel = Panel(status, title=title, border_style="blue")
            live.update(response_panel)
            
            for chunk in response:
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    usage = self._parse_usage(chunk.usage)

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content

                    if hasattr(self.console, 'gui'):
                        # Using Mocked console. Dont use Panel
                        self.console.print(content, end="", highlight=False)

                    try:
                        md = Markdown(full_response)
                        response_panel = Panel(md, title=title, border_style="green")
                    except Exception:
                        text = Text(full_response)
                        response_panel = Panel(text, title=title, border_style="yellow")
                    
                    live.update(response_panel)
        
        if response_panel: self.console.print(response_panel)            
        #segments = self.console.render(response_panel)
        #self.console._record_buffer.extend(segments)
        return ChatMessage(role="assistant", content=full_response, usage=usage)

    def _parse_response(self, response):
        message = response.choices[0].message
        reason = getattr(message, "reasoning_content", None)
        return ChatMessage(
            role=message.role,
            content=message.content,
            reason=reason,
            usage=self._parse_usage(response.usage)
        )

    def get_completion(self, messages):
        if not self._client:
            self._client = self._get_client()
        kws = {'stream_options': {'include_usage': True}} if self._stream and not self._base_url else {}
        try:
            response = self._client.chat.completions.create(
                model = self._model,
                messages = messages,
                stream=self._stream,
                max_tokens = self.max_tokens,
                **kws
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

    def usable(self):
        return super().usable() and self._base_url
    
    def _parse_usage(self, response):
        ret = {'input_tokens': response['prompt_eval_count'], 'output_tokens': response['eval_count']}
        ret['total_tokens'] = ret['input_tokens'] + ret['output_tokens']
        return ret

    def _parse_stream_response(self, response):
        full_response = ""
        response_panel = None
        title = f"{self.name} {T('llm_response')}"
        with Live(auto_refresh=True, vertical_overflow='visible', transient=True, refresh_per_second=self.RPS) as live:
            status = self.console.status(f"[dim white]{self.name} {T('thinking')}...", spinner='runner')
            response_panel = Panel(status, title=title, border_style="blue")
            live.update(response_panel)
            
            for chunk in response:
                msg = chunk.json()
                if msg['done']:
                    usage = self._parse_usage(chunk.usage)
                    break

                if 'message' in msg and 'content' in msg['message'] and msg['message']['content']:
                    content = msg['message']['content']
                    full_response += content
                    
                    try:
                        md = Markdown(full_response)
                        response_panel = Panel(md, title=title, border_style="green")
                    except Exception:
                        text = Text(full_response)
                        response_panel = Panel(text, title=title, border_style="yellow")
                    
                    live.update(response_panel)
        
        if response_panel: self.console.print(response_panel)
        #segments = self.console.render(response_panel)
        #self.console._record_buffer.extend(segments)
        return ChatMessage(role="assistant", content=full_response, usage=usage)

    def _parse_response(self, response):
        response = response.json()
        msg = response["message"]
        return ChatMessage(role=msg['role'], content=msg['content'], usage=self._parse_usage(response))
    
    def get_completion(self, messages):
        try:
            response = self._session.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": self._stream,
                    "options": {"num_predict": self.max_tokens}
                },
                timeout=self._timeout
            )
            response.raise_for_status()
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T('call_failed')}: [yellow]{str(e)}")
            response = None
        return response

# https://docs.anthropic.com/en/api/messages
class ClaudeClient(BaseClient):
    MODEL = "claude-3-7-sonnet-20250219"
    
    def __init__(self, config):
        super().__init__(config)
        self._system_prompt = None

    def _get_client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout)
    
    def usable(self):
        return super().usable() and self._api_key
    
    def _parse_usage(self, response):
        usage = response.usage
        ret = {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens}
        ret['total_tokens'] = ret['input_tokens'] + ret['output_tokens']
        return ret

    def _parse_stream_response(self, response):
        usage = Counter()    
        full_response = ""
        response_panel = None
        title = f"{self.name} {T('llm_response')}"
        with Live(auto_refresh=True, vertical_overflow='visible', transient=True, refresh_per_second=self.RPS) as live:
            status = self.console.status(f"[dim white]{self.name} {T('thinking')}...", spinner='runner')
            response_panel = Panel(status, title=title, border_style="blue")
            live.update(response_panel)
            
            for event in response:
                if hasattr(event, 'delta') and hasattr(event.delta, 'text') and event.delta.text:
                    content = event.delta.text
                    full_response += content
                    
                    try:
                        md = Markdown(full_response)
                        response_panel = Panel(md, title=title, border_style="green")
                    except Exception:
                        text = Text(full_response)
                        response_panel = Panel(text, title=title, border_style="yellow")
                    live.update(response_panel)
                elif hasattr(event, 'message') and hasattr(event.message, 'usage') and event.message.usage:
                    usage['input_tokens'] += getattr(event.message.usage, 'input_tokens', 0)
                    usage['output_tokens'] += getattr(event.message.usage, 'output_tokens', 0)
                elif hasattr(event, 'usage') and event.usage:
                    usage['input_tokens'] += getattr(event.usage, 'input_tokens', 0)
                    usage['output_tokens'] += getattr(event.usage, 'output_tokens', 0)

        usage['total_tokens'] = usage['input_tokens'] + usage['output_tokens']
        if response_panel: self.console.print(response_panel)      
        #segments = self.console.render(response_panel)
        #self.console._record_buffer.extend(segments)
        return ChatMessage(role="assistant", content=full_response, usage=usage)

    def _parse_response(self, response):
        content = response.content[0].text
        role = response.role
        return ChatMessage(role=role, content=content, usage=self._parse_usage(response))
    
    def add_system_prompt(self, history, system_prompt):
        self._system_prompt = system_prompt

    def get_completion(self, messages):
        if not self._client:
            self._client = self._get_client()
        try:
            message = self._client.messages.create(
                model = self._model,
                messages = messages,
                stream=self._stream,
                system=self._system_prompt,
                max_tokens = self.max_tokens
            )
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T('call_failed')}: [yellow]{str(e)}")
            message = None
        return message

class GeminiClient(OpenAIClient): 
    BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/'
    MODEL = 'gemini-2.5-pro-exp-03-25'

class DeepSeekClient(OpenAIClient): 
    BASE_URL = 'https://api.deepseek.com'
    MODEL = 'deepseek-chat'

class GrokClient(OpenAIClient): 
    BASE_URL = 'https://api.x.ai/v1/'
    MODEL = 'grok-3-mini'

class TrustClient(OpenAIClient): 
    BASE_URL = 'https://api.trustoken.ai/v1'
    MODEL = 'auto'

class AzureOpenAIClient(OpenAIClient): 
    MODEL = 'gpt-4o'

    def __init__(self, config):
        super().__init__(config)
        self._end_point = config.get('endpoint')

    def usable(self):
        return super().usable() and self._end_point
    
    def _get_client(self):
        from openai import AzureOpenAI
        return AzureOpenAI(azure_endpoint=self._end_point, api_key=self._api_key, api_version="2024-02-01")
            
class LLM(object):
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
    MAX_TOKENS = 4096

    def __init__(self, settings, console,system_prompt=None):
        self.llms = {}
        self.console = console
        self.default = None
        self._last = None
        self.history = ChatHistory()
        self.max_tokens = settings.get('max_tokens', self.MAX_TOKENS)
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
                names['error'].add(name)
                continue
            
            names['enabled'].add(name)
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
        if llm and llm.usable():
            self.current = llm
            return True
        return False
    
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
            self.console.print(f"[red]LLM: {name} {T('not usable')}")
            return None
        
        self._last = llm
        return llm(self.history, instruction, system_prompt=system_prompt)
        