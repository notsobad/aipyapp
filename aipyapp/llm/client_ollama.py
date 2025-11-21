#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
from collections import Counter

from .base import BaseClient, AIMessage

# https://github.com/ollama/ollama/blob/main/docs/api.md
class OllamaClient(BaseClient):
    def __init__(self, config):
        super().__init__(config)
        self._session = requests.Session()

    def usable(self):
        return super().usable() and self.base_url
    
    def _parse_usage(self, response):
        ret = Counter({
            'input_tokens': response['prompt_eval_count'],
            'output_tokens': response['eval_count'],
            'total_tokens': response['prompt_eval_count'] + response['eval_count']
        })
        return ret

    def _parse_stream_response(self, response, stream_processor):
        with stream_processor as lm:
            for chunk in response.iter_lines():
                chunk = chunk.decode(encoding='utf-8')
                msg = json.loads(chunk)
                if msg['done']:
                    usage = self._parse_usage(msg)
                    break

                if 'message' in msg and 'content' in msg['message'] and msg['message']['content']:
                    content = msg['message']['content']
                    lm.process_chunk(content)

        return AIMessage(content=lm.content, usage=usage)

    def _parse_response(self, response):
        response = response.json()
        msg = response["message"]
        return AIMessage(role=msg['role'], content=msg['content'], usage=self._parse_usage(response))

    def get_api_params(self, **kwargs):
        # Ollama 使用特定的参数结构
        params = {
            "model": self.model,
            "messages": [],  # messages 将在 get_completion 中设置
            "stream": self.config.stream,
            "options": {}
        }

        # 设置 options
        if self.config.max_tokens:
            params["options"]["num_predict"] = self.config.max_tokens
        if self.config.temperature is not None:
            params["options"]["temperature"] = self.config.temperature

        # 合并自定义参数到 options
        for key, value in self.config.extra_fields.items():
            if key.startswith('options.'):
                option_key = key[8:]  # 移除 'options.' 前缀
                params["options"][option_key] = value
            else:
                params[key] = value

        return params

    def get_completion(self, messages, **kwargs):
        # 获取 API 参数
        api_params = self.get_api_params(**kwargs)

        # 设置 messages
        api_params["messages"] = messages

        # 处理 extra_headers
        extra_headers = kwargs.pop('extra_headers', None)

        response = self._session.post(
            f"{self.base_url}/api/chat",
            json=api_params,
            timeout=self.config.timeout,
            headers=extra_headers,
        )
        response.raise_for_status()
        return response
