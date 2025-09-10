#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import List, TYPE_CHECKING, Any
import time
from collections import Counter

from loguru import logger
from pydantic import BaseModel, Field

from ..llm import ErrorMessage, UserMessage
from .chat import ChatMessage
from .response import Response
from .toolcalls import ToolCallResult
from .prompts import Prompts
from .events import BaseEvent
from .types import DataMixin

if TYPE_CHECKING:
    from .task import Task

class Round(BaseModel):
    request: ChatMessage = Field(default_factory=ChatMessage)
    response: Response = Field(default_factory=Response)
    toolcall_results: List[ToolCallResult] | None = None

    def should_continue(self) -> bool:
        return self.response.should_continue()
    
    def get_reply_msg(self, prompts: Prompts) -> UserMessage:
        if self.response.errors:
            prompt = prompts.get_parse_error_prompt(self.response.errors)
        elif self.toolcall_results:
            prompt = prompts.get_toolcall_results_prompt(self.toolcall_results)
        else:
            raise ValueError('Should not be here')
        return UserMessage(content=prompt)
    
class StepData(BaseModel):
    instruction: str
    title: str | None = None
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    rounds: List[Round] = Field(default_factory=list)
    events: List[BaseEvent.get_subclasses_union()] = Field(default_factory=list)
    
    @property
    def result(self):
        if not self.rounds:
            return None
        return self.rounds[-1].response
    
    def add_round(self, round: Round):
        self.rounds.append(round)

class Step:
    def __init__(self, task: Task, data: StepData):
        self.task = task
        self.log = logger.bind(src='Step')
        self._data = data
        self._summary = Counter()
    
    @property
    def data(self):
        return self._data
    
    def __getitem__(self, name: str):
        return getattr(self._data, name)
    
    def __setitem__(self, name: str, value: Any):
        setattr(self._data, name, value)
    
    def get(self, name: str, default: Any = None):
        return getattr(self._data, name, default)
    
    def request(self, user_message: ChatMessage) -> Response:
        client = self.task.client
        self.task.emit('request_started', llm=client.name)
        msg = client(user_message)
        self.task.emit('response_completed', llm=client.name, msg=msg)
        if isinstance(msg.message, ErrorMessage):
            response = Response(message=msg)
            self.log.error('LLM request error', error=msg.content)
        else:
            self._summary.update(msg.usage)
            response = Response.from_message(msg, parse_mcp=self.task.mcp)
        return response

    def process(self, response: Response) -> list[ToolCallResult] | None:
        if isinstance(response.message.message, ErrorMessage):
            return None
        
        if response.task_status:
            self.task.emit('task_status', status=response.task_status)

        if response.code_blocks:
            self.task.blocks.add_blocks(response.code_blocks)
        
        if response.tool_calls:
            toolcall_results = self.task.tool_call_processor.process(self.task, response.tool_calls)
        else:
            toolcall_results = None
        return toolcall_results
    
    def run(self, user_message: UserMessage) -> Response:
        max_rounds = self.task.max_rounds
        message_storage = self.task.message_storage
        while len(self['rounds']) < max_rounds:
            user_message = message_storage.store(user_message)
            response = self.request(user_message)

            self.task.emit('parse_reply_completed', response=response)
            round = Round(request=user_message, response=response)
            self._data.add_round(round)
            
            round.toolcall_results = self.process(response)
            
            if not round.should_continue():
                break

            user_message = round.get_reply_msg(self.task.prompts)

        self['end_time'] = time.time()
        return response

    def get_summary(self):
        summary = dict(self._summary)
        summary['elapsed_time'] = int(time.time() - self['start_time'])
        summary['rounds'] = len(self['rounds'])
        summarys = "{rounds} | {time}s/{elapsed_time}s | Tokens: {input_tokens}/{output_tokens}/{total_tokens}".format(**summary)
        return {'summary': summarys}
    