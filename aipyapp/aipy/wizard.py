from collections import OrderedDict

import questionary

providers = OrderedDict({
    "OpenAI": {"type": "openai", "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "o4-mini", "o3", "o3-mini"]},
    "Anthropic": {"type": "claude", "models": ["claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]},
    "DeepSeek": {"type": "deepseek", "models": ["deepseek-chat", "deepseek-reasoner"]},
    "xAI": {"type": "grok", "models": ["grok-3-mini", "grok-3", "grok-3-fast", "grok-3-mini-fast"]},
})

def config_llm(providers, default=None):
    name = questionary.select("请选择 API 提供商：", choices=list(providers.keys()), default=default).ask()
    provider = providers[name]
    config = {"type": provider["type"]}

    api_key = questionary.text(f"请输入 {provider} 的 API Key：", validate=lambda x: len(x)>8).ask()
    config['api_key'] = api_key

    name = questionary.select("请选择模型：", choices=provider['models']).ask()
    config['model'] = name

    return {"name": config}

if __name__ == '__main__':
    config = config_llm(providers, default='DeepSeek')
    print(config)
