import io
import os
import sys
import re
import json
import asyncio
import contextlib
import tempfile
import time

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 预编译正则表达式
CODE_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
JSON_PATTERN = re.compile(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})')

def extract_call_tool(text) -> str:
    """
    Extract MCP call_tool JSON from text.

    Args:
        text (str): The input text that may contain MCP call_tool JSON.

    Returns:
        str: The JSON str if found and valid, otherwise empty str.
    """

    # 使用预编译的正则模式
    code_blocks = CODE_BLOCK_PATTERN.findall(text)

    # Potential JSON candidates to check
    candidates = code_blocks.copy()

    # 使用预编译的正则模式
    standalone_jsons = JSON_PATTERN.findall(text)
    candidates.extend(standalone_jsons)

    # Try to parse each candidate
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            data = json.loads(candidate)
            # Validate that it's a call_tool action
            if not isinstance(data, dict):
                continue
            if 'action' not in data or 'name' not in data:
                continue
            if 'arguments' in data and not isinstance(data['arguments'], dict):
                continue

            # return json string. not dict
            return json.dumps(data, ensure_ascii=False)
        except json.JSONDecodeError:
            continue

    return ''


class MCPConfigReader:
    def __init__(self, config_path):
        self.config_path = config_path

    def get_mcp_servers(self):
        """读取 mcp.json 文件并返回 MCP 服务器清单"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return {}

class MCPClientSync:
    def __init__(self, server_params, suppress_output=True):
        self.server_params = server_params
        self.suppress_output = suppress_output

    @contextlib.contextmanager
    def _suppress_stdout_stderr(self):
        """上下文管理器：临时重定向 stdout 和 stderr 到空设备"""
        if not self.suppress_output:
            yield  # 如果不需要抑制输出，直接返回
            return

        # 保存原始的 stdout 和 stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            # 使用 os.devnull - 跨平台解决方案
            with open(os.devnull, 'w') as devnull:
                sys.stdout = devnull
                sys.stderr = devnull
                yield
        finally:
            # 恢复原始的 stdout 和 stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    def _run_async(self, coro):
        with self._suppress_stdout_stderr():
            try:
                return asyncio.run(coro)
            except Exception as e:
                print(f"Error running async function: {e}")
                raise

    def list_tools(self):
        return self._run_async(self._list_tools())

    def call_tool(self, tool_name, arguments):
        return self._run_async(self._call_tool(tool_name, arguments))

    async def _list_tools(self):
        try:
            tools = []
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    server_tools = await session.list_tools()
                    tools = server_tools.model_dump().get("tools", [])
            if sys.platform == "win32":
                # FIX windows下抛异常的问题
                await asyncio.sleep(3)
            return tools
        except Exception as e:
            logger.exception(f"Failed to list tools: {e}")
            return []

    async def _call_tool(self, tool_name, arguments):
        try:
            ret = {}
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    ret = result.model_dump()
            if sys.platform == "win32":
                # FIX windows下抛异常的问题
                await asyncio.sleep(3)
            return ret
        except Exception as e:
            logger.exception(f"Failed to call tool {tool_name}: {e}")
            raise

class MCPToolManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config_reader = MCPConfigReader(config_path)
        self.mcp_servers = self.config_reader.get_mcp_servers()
        self._tools_cache = {}  # 缓存已获取的工具列表
        self._inited = False
        # 设置缓存文件路径，与配置文件同目录
        self._cache_file = os.path.join(os.path.dirname(config_path), "mcp_tools_cache.json")
        self._config_mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

    def _is_cache_valid(self):
        """检查缓存文件是否有效"""
        # 如果缓存文件不存在，缓存无效
        if not os.path.exists(self._cache_file):
            return False

        # 如果配置文件修改时间晚于缓存创建时间，缓存无效
        if os.path.exists(self.config_path):
            config_mtime = os.path.getmtime(self.config_path)
            cache_mtime = os.path.getmtime(self._cache_file)
            if config_mtime > cache_mtime:
                return False

        return True

    def _save_cache(self):
        """保存工具列表到缓存文件"""
        try:
            cache_data = {
                "config_mtime": self._config_mtime,
                "tools_cache": self._tools_cache
            }
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"工具列表缓存已保存到 {self._cache_file}")
            return True
        except Exception as e:
            logger.exception(f"保存工具列表缓存失败: {e}")
            return False

    def _load_cache(self):
        """从缓存文件加载工具列表"""
        if not self._is_cache_valid():
            return False

        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            config_mtime = cache_data.get("config_mtime", 0)

            # 检查配置文件修改时间是否与缓存中的一致, mcp.json可能从别的地方复制过来，修改时间异常
            if self._config_mtime != config_mtime:
                logger.debug("配置文件已被修改，需要重新获取工具列表")
                return False

            # 检查缓存时间是否超过48小时
            current_time = time.time()
            if current_time - config_mtime > 172800:  # 48小时 = 48 * 60 * 60 = 172800秒
                logger.debug("缓存已超过48小时，需要重新获取工具列表")
                return False

            self._tools_cache = cache_data.get("tools_cache", {})
            self._config_mtime = config_mtime
            self._inited = True
            logger.debug(f"已从缓存加载工具列表: {self._cache_file}")
            return True
        except Exception as e:
            logger.exception(f"加载工具列表缓存失败: {e}")
            return False

    def list_tools(self):
        """返回所有MCP服务器的工具列表
        [{'description': 'Get weather alerts for a US state.\n'
                           '\n'
                           '    Args:\n'
                           '        state: Two-letter US state code (e.g. CA, '
                           'NY)\n'
                           '    ',
            'inputSchema': {'properties': {'state': {'title': 'State',
                                                     'type': 'string'}},
                            'required': ['state'],
                            'title': 'get_alertsArguments',
                            'type': 'object'},
            'name': 'get_alerts',
            'server': 'server1'
            },
        ]
        """
        # 尝试从缓存加载
        if self._load_cache():
            # 如果成功加载缓存，直接返回结果
            all_tools = []
            for server_name, tools in self._tools_cache.items():
                all_tools.extend(tools)
            return all_tools

        # 缓存无效或加载失败，重新获取工具列表
        all_tools = []
        for server_name, server_config in self.mcp_servers.items():
            # 去掉禁用的server，即 disabled: true or enabled: false
            if server_config.get("disabled", False) or server_config.get("enabled", True) is False:
                continue
            # 如果缓存中没有该服务器的工具，则获取
            if server_name not in self._tools_cache:
                try:
                    # 创建服务器参数
                    if "url" in server_config:
                        # HTTP/SSE 类型的服务器，暂不支持
                        #print(f"Skipping HTTP/SSE server {server_name}: {server_config['url']}")
                        continue
                    
                    server_params = StdioServerParameters(
                        command=server_config.get("command"),
                        args=server_config.get("args", []),
                        env=server_config.get("env")
                    )
                    
                    # 获取工具列表
                    client = MCPClientSync(server_params)
                    tools = client.list_tools()
                    #print(tools)
                    # 为每个工具添加服务器标识
                    for tool in tools:
                        tool["server"] = server_name
                    
                    self._tools_cache[server_name] = tools
                except Exception as e:
                    print(f"Error listing tools for server {server_name}: {e}")
                    self._tools_cache[server_name] = []
            
            # 添加到总工具列表
            all_tools.extend(self._tools_cache[server_name])
            self._inited = True

        # 保存到缓存
        self._save_cache()

        return all_tools

    def get_all_tools(self):
        """返回所有工具的列表"""

        if self._inited:
            all_tools = []
            for server_name, tools in self._tools_cache.items():
                for tool in tools:
                    tool["server"] = server_name
                    all_tools.append(tool)
        else:
            all_tools = self.list_tools()
        return all_tools

    def get_all_servers(self) -> dict:
        """返回所有服务器的列表"""
        if not self._inited:
            self.list_tools()
        return self._tools_cache

    def call_tool(self, tool_name, arguments):
        """调用指定名称的工具，自动选择最匹配的服务器"""
        # 获取所有工具
        all_tools = self.get_all_tools()
        if not all_tools:
            raise ValueError("No tools available to call.")
        
        # 查找匹配的工具
        matching_tools = [t for t in all_tools if t["name"] == tool_name]
        if not matching_tools:
            raise ValueError(f"No tool found with name: {tool_name}")
        
        # 选择参数匹配度最高的工具
        best_match = None
        best_score = -1
        
        for tool in matching_tools:
            score = 0
            required_params = []
            
            # 检查工具的输入模式
            if "inputSchema" in tool and "properties" in tool["inputSchema"]:
                properties = tool["inputSchema"]["properties"]
                required_params = tool["inputSchema"].get("required", [])
                
                # 检查所有必需参数是否提供
                required_provided = all(param in arguments for param in required_params)
                if not required_provided:
                    continue
                
                # 计算匹配的参数数量
                matching_params = sum(1 for param in arguments if param in properties)
                extra_params = len(arguments) - matching_params
                
                # 评分：匹配参数越多越好，额外参数越少越好
                score = matching_params - 0.1 * extra_params
            
            if score > best_score:
                best_score = score
                best_match = tool
        
        if not best_match:
            raise ValueError(f"No suitable tool found for {tool_name} with given arguments")
        
        # 获取服务器配置
        server_name = best_match["server"]
        server_config = self.mcp_servers[server_name]
        
        # 创建服务器参数
        server_params = StdioServerParameters(
            command=server_config.get("command"),
            args=server_config.get("args", []),
            env=server_config.get("env")
        )
        
        # 调用工具
        client = MCPClientSync(server_params)
        return client.call_tool(tool_name, arguments)
