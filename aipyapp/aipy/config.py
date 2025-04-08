import sys
import re
from dynaconf import Dynaconf

def is_valid_openai_api_key(api_key):
    """
    校验是否为有效的 OpenAI API Key 格式。

    :param api_key: 待校验的 API Key 字符串
    :return: 如果格式有效返回 True，否则返回 False
    """
    # OpenAI API Key 格式通常以 "sk-" 开头，后面是 48 个字母或数字，总长度为 51
    pattern = r"^sk-[A-Za-z0-9]{48}$"
    return bool(re.match(pattern, api_key))

class ConfigManager:
    def __init__(self, default_config="default.toml", user_config="aipython.toml"):
        self.default_config = default_config
        self.user_config = user_config
        self.config = self._load_config()

    def _load_config(self):
        # 使用 Dynaconf 合并 default 和用户指定的配置文件
        try:
            config = Dynaconf(
                settings_files=[self.default_config, self.user_config],
                envvar_prefix="AIPY", merge_enabled=True
            )
        except Exception as e:
            print(f"加载配置时出错: {e}")
        return config

    def get_config(self):
        return self.config

    def check_config(self):
        if not self.config:
            ret = "请检查配置文件路径和格式。"
            print(ret)
            return

        self.check_llm()

    def check_llm(self):
        if not self.config:
            print("配置尚未加载。")

        # 检查是否存在 'llm' 节
        llm = self.config.get("llm")
        if not llm:
            print("缺少 'llm' 配置。")

        llms = {}
        for name, config in self.config['llm'].items():
            # 检查每个 LLM 的配置
            if config.get("enable", True):
                llms[name] = config
        
        if not llms:
            self._init_llm()
        

    def _init_llm(self):
        print(
            """当前环境缺少配置文件，请注册一个trustoken账号，可以使用免费赠送的API账号。
浏览器打开 https://api.trustoken.ai/register ， 进行账号注册。
注册后进行登录，访问页面顶部的“令牌”页面，或者点击这个地址：https://api.trustoken.ai/token 
点击“复制”按钮，复制令牌到剪贴板。
在此执行粘贴。"""
        )

        while True:
            user_token = input("请粘贴令牌并按 Enter 键 (输入 'exit' 退出): ").strip()
            if user_token.lower() == "exit":
                print("退出令牌输入流程。")
                break
            if not user_token:
                print("未检测到令牌输入。")
                continue
            # 这里假设合法令牌的条件为长度不小于10字符，可根据需要调整验证逻辑

            if not is_valid_openai_api_key(user_token): 
                print("输入的令牌不合法，请确保令牌正确，格式为‘sk-xxxxxx……’，或输入 'exit' 退出。")
                continue

            self.save_trustoken(user_token)

            # reload config
            self.config = self._load_config()
            break

    def save_trustoken(self, token):
        # 根据文件所在目录定位配置文件
        config_file = self.user_config
        try:
            with open(config_file, "a") as f:
                # 在配置文件末尾追加新的llm信任令牌配置，采用指定的格式
                f.write("\n[llm.trustoken]\n")
                f.write(f'api_key = "{token}"\n')
                f.write('base_url = "https://api.trustoken.ai/v1"\n')
                f.write('model = "deepseek/deepseek-chat-v3-0324"\n')
                f.write("default = true\n")
            print(f"令牌已保存到 {config_file}")
        except Exception as e:
            print(f"保存令牌时出错: {e}")

