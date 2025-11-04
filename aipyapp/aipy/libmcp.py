import json
import re

from loguru import logger
from .. import T

# 预编译正则表达式
CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")

def _find_top_level_json_objects(text: str) -> list[str]:
    """Extract top-level JSON object substrings by scanning braces while
    being aware of string literals and escape characters.

    This avoids matching braces that appear inside quoted strings, which
    commonly happens when JSON contains code (e.g., JavaScript) as strings.

    Args:
        text: Input text possibly containing JSON objects.

    Returns:
        A list of substrings, each corresponding to a top-level JSON object.
    """
    results: list[str] = []
    n = len(text)
    i = 0
    in_str = False
    esc = False
    brace_depth = 0
    start = -1

    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                if brace_depth == 0:
                    start = i
                brace_depth += 1
            elif ch == '}':
                if brace_depth > 0:
                    brace_depth -= 1
                    if brace_depth == 0 and start != -1:
                        results.append(text[start:i + 1])
                        start = -1
        i += 1

    return results


def extra_call_tool_blocks(blocks) -> list[dict]:
    """
    从代码块列表中提取 MCP call_tool JSON。

    Args:
        blocks (list): CodeBlock 对象列表

    Returns:
        str: 找到的 JSON 字符串，如果没找到则返回空字符串
    """
    if not blocks:
        return []

    tools = []
    for block in blocks:
        # 检查代码块是否是 JSON 格式
        if hasattr(block, 'lang') and block.lang and block.lang.lower() in ['json', '']:
            # 尝试解析代码块内容
            content = (
                getattr(block, 'code', '')
                if hasattr(block, 'code')
                else str(block)
            )
            if content:
                content = content.strip()
                try:
                    data = json.loads(content)
                    # 验证是否是 call_tool 动作
                    if not isinstance(data, dict):
                        continue
                    if "action" not in data or "name" not in data:
                        continue
                    if "arguments" in data and not isinstance(data["arguments"], dict):
                        continue

                    # 返回 JSON 字符串
                    tools.append(data)
                except json.JSONDecodeError:
                    continue

    return tools


def extract_call_tool_str(text) -> list[dict]:
    """
    Extract MCP call_tool JSON from text.

    Args:
        text (str): The input text that may contain MCP call_tool JSON.

    Returns:
        list[dict]: List of parsed JSON dicts if found and valid, otherwise empty list.
    """

    # 使用预编译的正则模式
    code_blocks = CODE_BLOCK_PATTERN.findall(text)

    # Potential JSON candidates to check
    candidates = code_blocks.copy()

    # 使用引号感知的扫描器提取顶层 JSON 对象，避免匹配字符串中的大括号
    standalone_jsons = _find_top_level_json_objects(text)
    candidates.extend(standalone_jsons)

    tools = []
    seen_jsons = set()  # 用于去重

    # Try to parse each candidate
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            data = json.loads(candidate)
            # Validate that it's a call_tool action
            if not isinstance(data, dict):
                continue
            if "action" not in data or "name" not in data:
                continue
            if "arguments" in data and not isinstance(data["arguments"], dict):
                continue

            # 使用标准化的JSON字符串进行去重
            json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
            if json_str in seen_jsons:
                continue

            seen_jsons.add(json_str)
            tools.append(data)
        except json.JSONDecodeError:
            continue

    return tools


class MCPConfigReader:
    def __init__(self, config_path, tt_api_key):
        self.config_path = config_path
        self.tt_api_key = tt_api_key

    def _rewrite_config(self, servers):
        """rewrite MCP server config"""
        if not self.tt_api_key:
            return servers

        for _, server_config in servers.items():
            # 检查是否是trustoken的URL且transport类型为streamable_http
            url = server_config.get("url", "")
            transport = server_config.get("transport", {})

            if (
                url.startswith(T("https://sapi.trustoken.ai"))
                and transport.get("type") == "streamable_http"
            ):
                if "headers" not in server_config:
                    server_config["headers"] = {}

                server_config["headers"].update({
                    "Authorization": f"Bearer {self.tt_api_key}"
                })

        return servers

    def get_user_mcp(self) -> dict:
        """读取 mcp.json 文件并返回 MCP 服务器清单，包括禁用的服务器"""
        if not self.config_path:
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                servers = config.get("mcpServers", {})
                return self._rewrite_config(servers)
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(
                T("Error decoding MCP config file {}: {}").format(
                    self.config_path, e
                )
            )
            return {}


    def get_sys_mcp(self) -> dict:
        """
        获取内部 MCP 服务器配置。

        Returns:
            dict: 内部 MCP 服务器配置字典。
        """
        if not self.tt_api_key:
            logger.warning(
                "No Trustoken API key provided, sys_mcp will not be available."
            )
            return {}

        return {
            "Trustoken-map": {
                "url": f"{T('https://sapi.trustoken.ai')}/aio-api/mcp/amap/",
                "transport": {
                    "type": "streamable_http"
                },
                "headers": {
                    "Authorization": f"Bearer {self.tt_api_key}"
                }
            },
            "Trustoken-search": {
                "url": f"{T('https://sapi.trustoken.ai')}/mcp/",
                "transport": {
                    "type": "streamable_http"
                },
                "headers": {
                    "Authorization": f"Bearer {self.tt_api_key}"
                }
            }
        }
