#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import Counter
from dataclasses import dataclass, field

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

class Session:
    def __init__(self, manager):
        self.manager = manager
        self.history = ChatHistory()

    def use(self, llm):
        pass
    def chat(self, prompt, system_prompt=None, llm=None):
        return self.manager(self.history.get_messages(), prompt)
