#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import Counter

import httpx
import openai
from loguru import logger

from .. import T
from . import BaseClient, ChatMessage

# https://platform.openai.com/docs/api-reference/chat/create
# https://api-docs.deepseek.com/api/create-chat-completion
class OpenAIBaseClient(BaseClient):
    def usable(self):
        return super().usable() and self._api_key
    
    def _get_client(self):
        return openai.Client(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            http_client=httpx.Client(
                verify=self._tls_verify
            )
        )
    
    def add_system_prompt(self, history, system_prompt):
        history.add("system", system_prompt)

    def _parse_usage(self, usage):
        try:
            reasoning_tokens = int(usage.completion_tokens_details.reasoning_tokens)
        except Exception:
            reasoning_tokens = 0

        usage = Counter({'total_tokens': usage.total_tokens,
                'input_tokens': usage.prompt_tokens,
                'output_tokens': usage.completion_tokens + reasoning_tokens})
        return usage
    
    def _parse_stream_response(self, response, stream_processor):
        usage = Counter()
        tool_calls = []
        with stream_processor as lm:
            for chunk in response:
                #print(chunk)
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    usage = self._parse_usage(chunk.usage)

                if chunk.choices:
                    content = None
                    delta = chunk.choices[0].delta

                    # 处理普通内容和推理内容
                    if delta.content:
                        reason = False
                        content = delta.content
                    elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reason = True
                        content = delta.reasoning_content

                    # 处理 tool_calls
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            # 确保 tool_calls 列表足够长
                            while len(tool_calls) <= tool_call.index:
                                tool_calls.append({
                                    'id': None,
                                    'type': None,
                                    'function': {'name': None, 'arguments': ''}
                                })

                            # 更新对应索引的 tool_call
                            if tool_call.id:
                                tool_calls[tool_call.index]['id'] = tool_call.id
                            if tool_call.type:
                                tool_calls[tool_call.index]['type'] = tool_call.type
                            if tool_call.function:
                                if tool_call.function.name:
                                    tool_calls[tool_call.index]['function']['name'] = tool_call.function.name
                                if tool_call.function.arguments:
                                    tool_calls[tool_call.index]['function']['arguments'] += tool_call.function.arguments
                    
                    if content:
                        lm.process_chunk(content, reason=reason)

        return ChatMessage(
            role="assistant",
            content=lm.content,
            reason=lm.reason,
            tool_calls=tool_calls,
            usage=usage
        )

    def _parse_response(self, response):
        message = response.choices[0].message
        reason = getattr(message, "reasoning_content", None)
        # 解析 tool_calls
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls = []
            for tool_call in message.tool_calls:
                tool_calls.append({
                    'id': tool_call.id,
                    'type': tool_call.type,
                    'function': {
                        'name': tool_call.function.name,
                        'arguments': tool_call.function.arguments
                    }
                })
        return ChatMessage(
            role=message.role,
            content=message.content,
            reason=reason,
            tool_calls=tool_calls,
            usage=self._parse_usage(response.usage)
        )

    def get_completion(self, messages, tools=None):
        if not self._client:
            self._client = self._get_client()

        # 构建请求参数
        params = {
            "model": self._model,
            "messages": messages,
            "stream": self._stream,
            "max_tokens": self.max_tokens,
            **self._params
        }
        
        # 添加tools参数
        if tools:
            params["tools"] = tools
            # 如果有tools，可以设置tool_choice参数
            if "tool_choice" not in self._params:
                params["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**params)
        return response
    