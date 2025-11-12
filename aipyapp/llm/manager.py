from collections import defaultdict, namedtuple

from loguru import logger

from .. import T, __respath__
from .base_openai import OpenAIBaseClient
from .client_claude import ClaudeClient
from .client_ollama import OllamaClient
from .client_oauth2 import OAuth2Client
from .models import ModelRegistry

class OpenAIClient(OpenAIBaseClient): 
    MODEL = 'gpt-4o'

class GeminiClient(OpenAIBaseClient): 
    BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/'
    MODEL = 'gemini-2.5-flash'

class DeepSeekClient(OpenAIBaseClient): 
    BASE_URL = 'https://api.deepseek.com'
    MODEL = 'deepseek-chat'

class GrokClient(OpenAIBaseClient): 
    BASE_URL = 'https://api.x.ai/v1/'
    MODEL = 'grok-3-mini'

class TrustClient(OpenAIBaseClient): 
    MODEL = 'auto'

    def get_base_url(self):
        return self.config.get("base_url") or T("https://sapi.trustoken.ai/v1")
    
class AzureOpenAIClient(OpenAIBaseClient): 
    MODEL = 'gpt-4o'

    def __init__(self, config):
        super().__init__(config)
        self._end_point = config.get('endpoint')

    def usable(self):
        return super().usable() and self._end_point
    
    def _get_client(self):
        from openai import AzureOpenAI
        return AzureOpenAI(azure_endpoint=self._end_point, api_key=self._api_key, api_version="2024-02-01")

class DoubaoClient(OpenAIBaseClient): 
    BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
    MODEL = 'doubao-seed-1-6-251015'

class MoonShotClient(OpenAIBaseClient): 
    BASE_URL = T('https://api.moonshot.ai/v1')
    MODEL = 'kimi-latest'

class BigModelClient(OpenAIBaseClient): 
    BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
    MODEL = 'glm-4.5-air'

class ZClient(OpenAIBaseClient):
    BASE_URL = 'https://api.z.ai/api/paas/v4'
    MODEL = 'glm-4.5-flash'

CLIENTS = {
    "openai": OpenAIClient,
    "ollama": OllamaClient,
    "claude": ClaudeClient,
    "gemini": GeminiClient,
    "deepseek": DeepSeekClient,
    'grok': GrokClient,
    'trust': TrustClient,
    'azure': AzureOpenAIClient,
    'oauth2': OAuth2Client,
    'doubao': DoubaoClient,
    'kimi': MoonShotClient,
    'bigmodel': BigModelClient,
    'z': ZClient
}

class ClientManager(object):
    MAX_TOKENS = 8192

    def __init__(self, settings: dict, max_tokens: int | None = None):
        self.clients = {}
        self.default = None
        self.current = None
        self.max_tokens = max_tokens or self.MAX_TOKENS
        self.log = logger.bind(src='client_manager')
        self.names = self._init_clients(settings)
        self.model_registry = ModelRegistry(__respath__ / "models.yaml")
        
    def _create_client(self, config):
        kind = config.get("type", "openai")
        client_class = CLIENTS.get(kind.lower())
        if not client_class:
            self.log.error('Unsupported LLM provider', kind=kind)
            return None
        return client_class(config)
    
    def _init_clients(self, settings):
        names = defaultdict(set)
        for name, config in settings.items():
            if not config.get('enable', True):
                names['disabled'].add(name)
                continue
            
            config['name'] = name
            try:
                client = self._create_client(config)
            except Exception as e:
                self.log.exception('Error creating LLM client', config=config)
                names['error'].add(name)
                continue

            if not client or not client.usable():
                names['disabled'].add(name)
                self.log.error('LLM client not usable', name=name, config=config)
                continue

            names['enabled'].add(name)
            if not client.max_tokens:
                client.max_tokens = self.max_tokens
            self.clients[name] = client

            if config.get('default', False) and not self.default:
                self.default = client
                names['default'] = name

        if not self.default:
            name = list(self.clients.keys())[0]
            self.default = self.clients[name]
            names['default'] = name

        self.current = self.default
        return names

    def __len__(self):
        return len(self.clients)
    
    def __repr__(self):
        return f"Current: {'default' if self.current == self.default else self.current}, Default: {self.default}"
    
    def __contains__(self, name):
        return name in self.clients
    
    def use(self, name):
        client = self.clients.get(name)
        if client and client.usable():
            self.current = client
            return True
        return False

    def get_client(self, name):
        return self.clients.get(name)
    
    def to_records(self):
        LLMRecord = namedtuple('LLMRecord', ['Name', 'Model', 'Max_Tokens', 'Base_URL'])
        rows = []
        for name, client in self.clients.items():
            rows.append(LLMRecord(name, client.model, client.max_tokens, client.base_url))
        return rows
    
    def get_model_info(self, model: str):
        return self.model_registry.get_model_info(model)
    