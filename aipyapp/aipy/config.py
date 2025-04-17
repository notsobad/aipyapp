import sys
import os
import re
from pathlib import Path

from dynaconf import Dynaconf
from rich import print


from .i18n import T
from .. import __PACKAGE_NAME__

SETTINGS_FILES = [Path.home() / '.aipy.toml', Path('aipython.toml').resolve(), Path('.aipy.toml').resolve(), Path('aipy.toml').resolve()]


CONFIG_FILE_NAME = "config.toml"

def init_config_dir():
    """
    获取平台相关的配置目录，并确保目录存在
    """
    if sys.platform == "win32":
        # Windows 路径
        app_data = os.environ.get("APPDATA")
        if app_data:
            config_dir = Path(app_data) / __PACKAGE_NAME__
        else:
            config_dir = Path.home() / "AppData" / "Roaming" / __PACKAGE_NAME__
    else:
        # Linux/macOS 路径
        config_dir = Path.home() / ".config" / __PACKAGE_NAME__
    
    # 确保目录存在
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(T('permission_denied_error').format(config_dir))
        raise
    except Exception as e:
        print(T('error_creating_config_dir').format(config_dir, str(e)))
        raise
    
    return config_dir

def get_config_file_path():
    """
    获取配置文件的完整路径
    :return: 配置文件的完整路径
    """
    config_dir = init_config_dir()
    config_file_path = config_dir / CONFIG_FILE_NAME

    # 如果配置文件不存在，则创建一个空文件
    if not config_file_path.exists():
        try:
            config_file_path.touch()
        except Exception as e:
            print(T('error_creating_config_dir').format(config_file_path, str(e)))
            raise

    return config_file_path


def is_valid_api_key(api_key):
    """
    校验是否为有效的 API Key 格式。
    API Key 格式为字母、数字、减号、下划线的组合，长度在 8 到 128 之间
    :param api_key: 待校验的 API Key 字符串
    :return: 如果格式有效返回 True，否则返回 False
    """
    pattern = r"^[A-Za-z0-9_-]{8,128}$"
    return bool(re.match(pattern, api_key))


class Config:
    def __init__(self, default_config="default.toml",  config_file=None):
        self.config_file = config_file or get_config_file_path()
        self.config = Dynaconf(
            settings_files=[default_config, self.config_file],
            envvar_prefix="AIPY",
            merge_enabled=True
        )

        # old user config, without default config.
        self._old_user_config = Dynaconf(
            settings_files=SETTINGS_FILES[:-1] + [Path('aipython.toml').resolve()],
            envvar_prefix="AIPY", merge_enabled=True
        )

    def get_config(self):
        return self.config

    def check_config(self):

        if not self.config:
            print(T('config_not_loaded'))
            return

        tt = self.config.get("trustoken")
        if tt and tt['api_key']:
            # valid tt config
            pass
        else:
            # no tt config, need to init.
            llm = self.config.get("trustoken")

            pass

    def _migrate_old_config(self, old_config):
        """从旧的配置文件迁移 LLM 配置到新的配置文件
        1. llm中有名为trustoken的配置，则将其迁移到新的配置文件中
        2. 如果llm的base_url中包含trustoken，则将其迁移到新的配置文件中
        """
        
        if not old_config:
            print("no old config found")
            return
        #config_dict = old_config.get('config').to_dict()


        llm = old_config.get('llm', {})
        trustoken_cfg = None
        # 1. 如果llm中有名为trustoken的配置，则迁移
        if "trustoken" in llm:
            trustoken_cfg = llm["trustoken"]
            llm.pop("trustoken")
            #self.config.set("llm.trustoken", trustoken_cfg)
            #self.config.save()
            #print(T('trustoken_migrated'))

        # 2. 如果llm的base_url中包含trustoken，则迁移
        else:
            for name, cfg in llm.items():
                base_url = cfg.get("base_url", "")
                if "trustoken.ai" in base_url:
                    #self.config.set(f"llm.{name}", cfg)
                    #print(T('trustoken_migrated'))
                    trustoken_cfg = cfg
                    llm.pop(name)
                    break
        

class ConfigManager:
    def __init__(self, default_config="default.toml", user_config="aipy.toml"):
        self.default_config = default_config
        self.user_config = user_config
        self.config = self._load_config()

    def _load_config(self):
        try:
            settings_files = [self.default_config] + SETTINGS_FILES[:-1] + [Path(self.user_config).resolve()]

            config = Dynaconf(
                settings_files=settings_files,
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
            if not is_valid_api_key(user_token):
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
                f.write('model = "auto"\n')
                f.write("default = true\n")
                f.write("enable = true\n")
            print(T('token_saved').format(config_file))
        except Exception as e:
            print(T('token_save_error').format(e))
