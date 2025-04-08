import sys
import re
from dynaconf import Dynaconf
from .i18n import T

def is_valid_openai_api_key(api_key):
    """
    校验是否为有效的 OpenAI API Key 格式。
    OpenAI API Key 格式通常以 "sk-" 开头，后面是 48 个字母或数字，总长度为 51
    :param api_key: 待校验的 API Key 字符串
    :return: 如果格式有效返回 True，否则返回 False
    """
    pattern = r"^sk-[A-Za-z0-9]{48}$"
    return bool(re.match(pattern, api_key))


class ConfigManager:
    def __init__(self, default_config="default.toml", user_config="aipython.toml"):
        self.default_config = default_config
        self.user_config = user_config
        self.config = self._load_config()

    def _load_config(self):
        try:
            config = Dynaconf(
                settings_files=[self.default_config, self.user_config],
                envvar_prefix="AIPY", merge_enabled=True
            )
        except Exception as e:
            print(T('error_loading_config').format(e))
            config = None
        return config

    def get_config(self):
        return self.config

    def check_config(self):
        if not self.config:
            print(T('config_file_error'))
            return

        self.check_llm()

    def check_llm(self):
        if not self.config:
            print(T('config_not_loaded'))
            return

        llm = self.config.get("llm")
        if not llm:
            print(T('llm_config_not_found'))

        llms = {}
        for name, config in self.config.get('llm', {}).items():
            if config.get("enable", True):
                llms[name] = config

        if not llms:
            self._init_llm()

    def _init_llm(self):
        print(T('trustoken_register_instruction').format(self.user_config))

        while True:
            user_token = input(T('prompt_token_input')).strip()
            if user_token.lower() == "exit":
                print(T('exit_token_prompt'))
                sys.exit(0)
            if not user_token:
                print(T('no_token_detected'))
                continue
            if not is_valid_openai_api_key(user_token):
                print(T('invalid_token'))
                continue

            self.save_trustoken(user_token)

            self.config = self._load_config()
            break

    def save_trustoken(self, token):
        config_file = self.user_config
        try:
            with open(config_file, "a") as f:
                f.write("\n[llm.trustoken]\n")
                f.write(f'api_key = "{token}"\n')
                f.write('base_url = "https://api.trustoken.ai/v1"\n')
                f.write('model = "deepseek/deepseek-chat-v3-0324"\n')
                f.write("default = true\n")
            print(T('token_saved').format(config_file))
        except Exception as e:
            print(T('token_save_error').format(e))
