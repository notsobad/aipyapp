from collections import OrderedDict
import questionary
import requests
from loguru import logger
from ..config.llm import LLMConfig, PROVIDERS
from .trustoken import TrustToken

providers = OrderedDict(PROVIDERS)

def get_models(provider: str, api_key: str) -> list:
    """获取可用的模型列表"""
    provider_info = providers[provider]
    headers = {
        "Content-Type": "application/json"
    }
    
    if provider == "Claude":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(
            f"{provider_info['api_base']}{provider_info['models_endpoint']}",
            headers=headers
        )
        logger.info(f"获取模型列表: {response.text}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"获取模型列表成功: {data}")
            if provider in ["OpenAI", "DeepSeek", "xAI", "Claude"]:
                return [model["id"] for model in data["data"]]
            elif provider == "Gemini":
                return [model["name"] for model in data["models"]]
            return []
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        return []  # 如果API调用失败，返回空列表

def select_provider(llm_config, default='Trustoken'):
    """选择提供商"""
    while True:
        name = questionary.select(
            "请选择 API 提供商：",
            choices=[
                questionary.Choice(title='Trustoken (小白模式，推荐)', value='Trustoken', description='Trustoken配置简单、已融合多模型'),
                questionary.Choice(title='其它提供商（专家模式）', value='other')
            ],
            default=default
        ).unsafe_ask()
        if name == default:
            return default

        names = [name for name in providers.keys() if name != default]
        names.append('<--')
        name = questionary.select(
            "请选择其它提供商：",
            choices=names
        ).unsafe_ask()
        if name != '<--':
            return name


def config_llm(llm_config):
    """配置 LLM 提供商"""
    # 第一步：选择提供商
    name = select_provider(llm_config)
    if not name:
        return None
    provider = llm_config.providers[name]
    config = {"type": provider["type"]}

    if name == 'Trustoken':
        def save_token(token):
            config['api_key'] = token

        tt = TrustToken()
        if tt.fetch_token(save_token):
            config['model'] = 'auto'
            llm_config.config[name] = config
            llm_config.save_config(llm_config.config)
            return llm_config.config
        else:
            return None
        
    # 第二步：输入 API Key
    api_key = questionary.text(
            f"请输入 {name} 的 API Key：",
            validate=lambda x: len(x) > 8
    ).unsafe_ask()
    config['api_key'] = api_key

    # 获取可用模型列表
    available_models = get_models(name, api_key)
    if not available_models:
        logger.warning(f"无法获取 {name} 的模型列表，请检查 API Key 是否正确")
        return None

    # 第三步：选择模型
    model = questionary.select(
        "请选择模型：",
        choices=available_models
    ).unsafe_ask()
    config['model'] = model

    # 第四步：配置参数
    max_tokens = questionary.text(
        "请输入最大 Token 数（默认：8192）：",
        default="8192",
        validate=lambda x: x.isdigit() and int(x) > 0
    ).unsafe_ask()
    config['max_tokens'] = int(max_tokens)

    temperature = questionary.text(
        "请输入 Temperature（0-1，默认：0.5）：",
        default="0.7",
        validate=lambda x: 0 <= float(x) <= 1
    ).unsafe_ask()
    config['temperature'] = float(temperature)

    # 保存配置
    current_config = llm_config.config
    current_config[name] = config
    llm_config.save_config(current_config)
    return current_config
    