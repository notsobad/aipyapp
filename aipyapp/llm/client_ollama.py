#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

from .base import BaseClient
from .display import LiveManager
from .session import ChatMessage
from .. import T

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
        with LiveManager(self.console, self.name) as lm:
            for chunk in response.iter_lines():
                chunk = chunk.decode(encoding='utf-8')
                msg = json.loads(chunk)
                if msg['done']:
                    usage = self._parse_usage(msg)
                    break

                if 'message' in msg and 'content' in msg['message'] and msg['message']['content']:
                    content = msg['message']['content']
                    lm.process_chunk(content)

                if self.is_stopped():
                    self.log.info('Stopping stream')
                    break
        response_panel = lm.response_panel
        full_response = lm.full_response        
        if response_panel: self.console.print(response_panel)
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
                timeout=self._timeout,
                **self._params
            )
            response.raise_for_status()
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T("Call failed")}: [yellow]{str(e)}")
            self.log.exception('Error calling Ollama API')
            response = None
        return response
