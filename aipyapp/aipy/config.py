import sys
import os
import re
import io
import datetime
import webbrowser
import json
import base64
import socket
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dynaconf import Dynaconf
from rich import print
import tomli_w


from .i18n import T
from .. import __PACKAGE_NAME__

OLD_SETTINGS_FILES = [
    Path.home() / '.aipy.toml',
    Path('aipython.toml').resolve(),
    Path('.aipy.toml').resolve(),
    Path('aipy.toml').resolve()
]

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

CONFIG_FILE_NAME = f"{__PACKAGE_NAME__}.toml"
USER_CONFIG_FILE_NAME = "user_config.toml"
CONFIG_DIR = init_config_dir()

def get_config_file_path(file_name=CONFIG_FILE_NAME):
    """
    获取配置文件的完整路径
    :return: 配置文件的完整路径
    """
    config_dir = init_config_dir()
    config_file_path = config_dir / file_name

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

def start_local_server(save_func):
    """web服务器用于接收 Trustoken 的登录凭证
    """
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Parse 'credential' from query parameters
            query = urlparse(self.path).query
            params = parse_qs(query)
            credential_b64 = params.get("credential", [None])[0]
            if credential_b64:
                try:
                    credential_json = base64.b64decode(credential_b64).decode("utf-8")
                    credential = json.loads(credential_json)
                    token = credential.get("token")
                    if token:
                        save_func(token)
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(T('token_received').encode('utf-8'))
                        print("Token received and saved")
                        return
                except Exception as e:
                    print("Error decoding credential:", e)
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid credential.")

    server = None
    port = 0
    while server is None:
        port = random.randint(1024, 65535)
        try:
            server = HTTPServer(('localhost', port), RequestHandler)
            print(T('server_started').format(port))
        except socket.error as e:
            if e.errno == socket.errno.EADDRINUSE:
                print(f"Port {port} is already in use, trying another one...")
            else:
                print(f"Error starting server: {e}")
                raise # Reraise other socket errors

    print(T('open_browser'))
    webbrowser.open(f"https://api-test.trustoken.ai/token/grant?redirect=http://127.0.0.1:{port}")

    #print("Waiting for credential...")
    server.handle_request()


class ConfigManager:
    def __init__(self, default_config="default.toml",  config_file=None):
        self.config_file = get_config_file_path()
        self.user_config_file = get_config_file_path(USER_CONFIG_FILE_NAME)
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
            settings_files=[self.default_config, self.config_file],
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
            start_local_server(self.save_tt_config)
        
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
                api_key = section_data.get('api_key', '')
                if api_key:
                    tt_keys.append(api_key)
                # 从原配置中删除
                llm.pop(section_name)

        #print("keys found:", tt_keys)

        if tt_keys:
            # 保存第一个找到的API key
            self.save_tt_config(tt_keys[0])

        #print(old_config.to_dict())
        # 将 old_config 转换为 dict
        config_dict = old_config.to_dict()
        try:
            with open(self.user_config_file, "wb") as f:
                tomli_w.dump(config_dict, f)
                print(T('migrate_config').format(self.user_config_file))
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

        # 条件2: base_url包含目标域名
        if isinstance(config, dict) and 'base_url' in config:
            base_url = config['base_url'].lower()
            if 'trustoken.ai' in base_url:
                return True

        # 条件3: 其他特定标记
        # type == trust, 且没有base_url.
        if isinstance(config, dict) and config.get('type') == 'trust' and not config.get('base_url'):
            return True
        
        return False