import sys
import time
import requests # Import requests library
import os
import re
import io
import datetime
import webbrowser
from pathlib import Path

from dynaconf import Dynaconf
from rich import print
import tomli_w
import qrcode


from .i18n import T

__PACKAGE_NAME__ = "aipyapp"

OLD_SETTINGS_FILES = [
    Path.home() / '.aipy.toml',
    Path('aipython.toml').resolve(),
    Path('.aipy.toml').resolve(),
    Path('aipy.toml').resolve()
]

# Coordinator 服务器地址
COORDINATOR_URL = os.getenv('COORDINATOR_URL', 'https://api.trustoken.ai/api')
POLL_INTERVAL = 5 # 轮询间隔（秒）
CONFIG_FILE_NAME = f"{__PACKAGE_NAME__}.toml"
USER_CONFIG_FILE_NAME = "user_config.toml"

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

CONFIG_DIR = init_config_dir()

def get_config_file_path(config_dir=None, file_name=CONFIG_FILE_NAME):
    """
    获取配置文件的完整路径
    :return: 配置文件的完整路径
    """
    if config_dir:
        config_dir = Path(config_dir)
    else:
        config_dir = CONFIG_DIR

    config_file_path = config_dir / file_name

    # 如果配置文件不存在，则创建一个空文件
    if not config_file_path.exists():
        try:
            config_file_path.touch()
        except Exception as e:
            print(T('error_creating_config_dir').format(config_file_path, str(e)))
            raise

    return config_file_path

def lowercase_keys(d):
    """递归地将字典中的所有键转换为小写"""
    if not isinstance(d, dict):
        return d
    return {k.lower(): lowercase_keys(v) for k, v in d.items()}

def is_valid_api_key(api_key):
    """
    校验是否为有效的 API Key 格式。
    API Key 格式为字母、数字、减号、下划线的组合，长度在 8 到 128 之间
    :param api_key: 待校验的 API Key 字符串
    :return: 如果格式有效返回 True，否则返回 False
    """
    pattern = r"^[A-Za-z0-9_-]{8,128}$"
    return bool(re.match(pattern, api_key))

def request_binding():
    """向 Coordinator 请求绑定"""
    url = f"{COORDINATOR_URL}/request_bind"
    try:
        response = requests.post(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        approval_url = data['approval_url']
        request_id = data['request_id']
        expires_in = data['expires_in']

        print(T('binding_request_sent').format(request_id, approval_url, expires_in))
        print(T('scan_qr_code'))

        try:
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                border=1
            )
            qr.add_data(approval_url)
            qr.make(fit=True)
            qr.print_ascii(tty=True)
            print("\n")
        except Exception as e:
            print(T('qr_code_display_failed').format(e))

        return data['request_id']

    except requests.exceptions.RequestException as e:
        print(T('coordinator_request_error').format(e))
        return None
    except Exception as e:
        print(T('unexpected_request_error').format(e))
        return None

def poll_status(request_id, save_func=None):
    """轮询绑定状态"""
    url = f"{COORDINATOR_URL}/check_status"
    params = {'request_id': request_id}
    start_time = time.time()
    polling_timeout = 310

    print(T('waiting_for_approval'))
    try:
        while time.time() - start_time < polling_timeout:
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                status = data.get('status')
                print(T('current_status').format(status))

                if status == 'approved':
                    if save_func:
                        save_func(data['secret_token'])
                    return True
                elif status == 'expired':
                    print(T('binding_expired'))
                    return False
                elif status == 'pending':
                    pass
                else:
                    print(T('unknown_status').format(status))
                    return False

            except requests.exceptions.RequestException as e:
                print(T('coordinator_polling_error').format(e))
                time.sleep(POLL_INTERVAL)
            except Exception as e:
                print(T('unexpected_polling_error').format(e))
                return False

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print(T('polling_cancelled'))
        return False

    print(T('polling_timeout'))
    return False

def fetch_token(save_func):
    """从 Coordinator 获取 Token 并保存"""
    print(T('start_binding_process'))
    req_id = request_binding()
    if req_id:
        if poll_status(req_id, save_func):
            print(T('binding_success'))
        else:
            print(T('binding_failed'))
            sys.exit(1)
    else:
        print(T('binding_request_failed'))
        sys.exit(1)

class ConfigManager:
    def __init__(self, default_config="default.toml",  config_dir=None):
        self.config_file = get_config_file_path(config_dir)
        self.user_config_file = get_config_file_path(config_dir, USER_CONFIG_FILE_NAME)
        self.default_config = default_config
        self.config = self._load_config()

        # old user config, without default config.
        self._old_user_config = Dynaconf(
            settings_files=OLD_SETTINGS_FILES,
            envvar_prefix="AIPY", merge_enabled=True
        )
        #print(self.config.to_dict())
        #print(self._old_user_config.to_dict())

    def _load_config(self):
        config = Dynaconf(
            settings_files=[self.default_config, self.config_file, self.user_config_file],
            envvar_prefix="AIPY",
        )
        #print(config.to_dict())
        return config

    def get_config(self):
        return self.config

    def save_tt_config(self, api_key):
        config = {
            'llm': {
                'trustoken': {
                    'api_key': api_key,
                    'type': 'trust',
                    'base_url': 'https://api.trustoken.ai/v1',
                    'model': 'auto',
                    'default': True,
                    'enable': True
                }
            }
        }
        header_comments = [
            f"# Configuration file for {__PACKAGE_NAME__}",
            "# Auto-generated on " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"# 请勿直接修改此文件，除非您了解具体配置格式，如果自定义配置，请放到{self.user_config_file}",
            f"# Please do not edit this file directly unless you understand the format. If you want to customize the configuration, please edit {self.user_config_file}",
            ""
        ]
        footer_comments = [
            "",
            "# End of configuration file"
        ]

        with open(self.config_file, "w", encoding="utf-8") as f:
            # 1. 写入头部注释
            f.write("\n".join(header_comments) + "\n")

            # 2. 写入 TOML 内容到临时内存文件

            temp_buffer = io.BytesIO()
            tomli_w.dump(config, temp_buffer)
            toml_content = temp_buffer.getvalue().decode('utf-8')

            # 3. 写入 TOML 内容
            f.write(toml_content)

            # 4. 写入尾部注释
            f.write("\n".join(footer_comments))

        return config

    def check_config(self):

        if not self.config:
            print(T('config_not_loaded'))
            return
        tt = self.config.get('llm', {}).get('trustoken', {})
        if tt and tt.get('api_key') and tt.get('type') == 'trust':
            # valid tt config
            #print("trustoken config found")
            return
        elif self._old_user_config.to_dict():
            # no tt config, try to migrate from old config
            # remove this later.
            self._migrate_old_config(self._old_user_config)
        else:
            # try to fetch config from web.
            fetch_token(self.save_tt_config)
        
        # reload config
        self.config = self._load_config()

    def _migrate_old_config(self, old_config):
        """
        从old_config中提取符合特定条件的API keys，并从原始配置中删除
        
        返回: 提取的API keys字典，格式为 {配置名称: API key}
        """
        if not old_config:
            return {}

        tt_keys = []

        # 处理顶级配置
        llm = old_config.get('llm', {})
        for section_name, section_data in list(llm.items()):
            # 跳过非字典类型的配置
            if not isinstance(section_data, dict):
                continue
            # 检查顶级配置
            if self._is_tt_config(section_name, section_data):
                api_key = section_data.get('api_key', section_data.get('api-key'))
                if api_key:
                    tt_keys.append(api_key)
                # 从原配置中删除
                llm.pop(section_name)


        print("keys found:", tt_keys)

        if tt_keys:
            # 保存第一个找到的API key
            self.save_tt_config(tt_keys[0])
            print(T('migrate_config').format(self.config_file))

        # 将 old_config 转换为 dict
        config_dict = lowercase_keys(old_config.to_dict())
        #print(config_dict)
        if not config_dict.get('llm'):
            config_dict.pop('llm', None)
        if not config_dict:
            return {}
        try:
            with open(self.user_config_file, "wb") as f:
                tomli_w.dump(config_dict, f)
                print(T('migrate_user_config').format(self.user_config_file))
        except Exception as e:
            print(T('error_saving_config').format(self.user_config_file, str(e)))
        return

    def _is_tt_config(self, name, config):
        """
        判断配置是否符合特定条件
        
        参数:
            name: 配置名称
            config: 配置内容字典
        
        返回: 如果符合条件返回True
        """
        # 条件1: 配置名称包含目标关键字
        if any(keyword in name.lower() for keyword in ['trustoken', 'trust']):
            return True

        base_url = config.get('base_url', config.get('base-url', '')).lower()
        # 条件2: base_url包含目标域名
        if isinstance(config, dict) and base_url:
            if 'trustoken.ai' in base_url:
                return True

        # 条件3: 其他特定标记
        # type == trust, 且没有base_url.
        if isinstance(config, dict) and config.get('type') == 'trust' and not base_url:
            return True
        
        return False