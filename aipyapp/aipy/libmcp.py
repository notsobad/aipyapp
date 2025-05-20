import io
import os
import sys
import re
import json
import asyncio
import contextlib
import tempfile

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
        """上下文管理器：临时重定向 stdout 和 stderr 到 /dev/null 或临时文件"""
        if not self.suppress_output:
            yield  # 如果不需要抑制输出，直接返回
            return

        # 保存原始的 stdout 和 stderr
        #original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            # 在 Unix 系统上重定向到 /dev/null
            if os.name == 'posix':
                # 目前windows下会报错，其他系统暂未发现问题，这里就不处理
                yield
                #with open(os.devnull, 'w') as devnull:
                #    #sys.stdout = devnull
                #    sys.stderr = devnull
                #    yield
            # 在 Windows 或其他系统上使用临时文件
            else:
                with tempfile.TemporaryFile('w+') as stderr_file:
                    #sys.stdout = stdout_file
                    sys.stderr = stderr_file
                    yield
        finally:
            # 恢复原始的 stdout 和 stderr
            #sys.stdout = original_stdout
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
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    server_tools = await session.list_tools()
                    tools = server_tools.model_dump().get("tools", [])
                    return tools
        except Exception as e:
            logger.exception(f"Failed to list tools: {e}")
            return []

    async def _call_tool(self, tool_name, arguments):
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return result.model_dump()
        except Exception as e:
            logger.exception(f"Failed to call tool {tool_name}: {e}")
            raise

class MCPToolManager:
    def __init__(self, config_path):
        self.config_reader = MCPConfigReader(config_path)
        self.mcp_servers = self.config_reader.get_mcp_servers()
        self._tools_cache = {}  # 缓存已获取的工具列表
        self._inited = False

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
