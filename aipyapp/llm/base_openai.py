import openai
from collections import Counter

from .base import BaseClient
from .display import LiveManager
from .session import ChatMessage
from .. import T

# https://platform.openai.com/docs/api-reference/chat/create
# https://api-docs.deepseek.com/api/create-chat-completion
class OpenAIBaseClient(BaseClient):
    def usable(self):
        return super().usable() and self._api_key
    
    def _get_client(self):
        return openai.Client(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)
    
    def _parse_usage(self, usage):
        usage = Counter({'total_tokens': usage.total_tokens,
                'input_tokens': usage.prompt_tokens,
                'output_tokens': usage.completion_tokens})
        return usage
    
    def _parse_stream_response(self, response):
        usage = Counter()
        with LiveManager(self.console, self.name) as lm:
            for chunk in response:
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    usage = self._parse_usage(chunk.usage)

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    lm.process_chunk(content)

                if self.is_stopped():
                    self.log.info('Stopping stream')
                    break
        response_panel = lm.response_panel
        full_response = lm.full_response
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
        try:
            response = self._client.chat.completions.create(
                model = self._model,
                messages = messages,
                stream=self._stream,
                max_tokens = self.max_tokens,
                **self._params
            )
        except Exception as e:
            self.console.print(f"❌ [bold red]{self.name} API {T("Call failed")}: [yellow]{str(e)}")
            self.log.exception('Error calling OpenAI API')
            response = None
        return response
