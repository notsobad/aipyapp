import asyncio
import contextlib
import os
import sys
import time
from datetime import timedelta
from typing import Dict, Optional, Tuple

from loguru import logger
from mcp.client.session_group import (
    ClientSessionGroup,
    SseServerParameters,
    StreamableHttpParameters,
)
from mcp.client.stdio import StdioServerParameters
from mcp.shared.exceptions import McpError

class LazyMCPClient:
    """
    惰性MCP会话管理器：
    - 仅在调用某个server的工具时才连接该server
    - 可配置空闲TTL，超时自动断开
    - 支持“serverKey:toolName”命名以避免全量扫描
    """

    def __init__(self, mcp_servers: dict, idle_ttl_seconds: int = 300, suppress_output: bool = True):
        self._servers: dict = mcp_servers or {}
        self._idle_ttl = idle_ttl_seconds
        self._suppress_output = suppress_output

        self._group: Optional[ClientSessionGroup] = None
        self._connected: Dict[str, object] = {}          # serverKey -> mcp.ClientSession
        self._last_used_ts: Dict[str, float] = {}        # serverKey -> last used unix ts
        self._connecting_locks: Dict[str, asyncio.Lock] = {}

        # 用于在聚合时将工具名命名为 "serverKey:toolName"
        self._current_prefix: Optional[str] = None

    # ---------- 工具方法 ----------
    def _now(self) -> float:
        return time.time()

    def _qualified(self, server_key: str, tool_name: str) -> str:
        return f"{server_key}:{tool_name}"

    @contextlib.contextmanager
    def _suppress_stdout_stderr(self):
        if not self._suppress_output:
            yield
            return
        orig_out, orig_err = sys.stdout, sys.stderr
        try:
            with open(os.devnull, "w") as devnull:
                sys.stdout = devnull
                sys.stderr = devnull
                yield
        finally:
            sys.stdout, sys.stderr = orig_out, orig_err

    def _run_async(self, coro):
        with self._suppress_stdout_stderr():
            try:
                return asyncio.run(coro)
            except Exception as e:
                logger.error(f"Async run error: {e}")
                return None

    def _create_server_parameters(self, cfg: dict):
        if "url" in cfg:
            transport_type = cfg.get("transport", {}).get("type")
            if transport_type == "streamable_http":
                return StreamableHttpParameters(
                    url=cfg["url"],
                    headers=cfg.get("headers"),
                    timeout=timedelta(seconds=cfg.get("timeout", 30)),
                    sse_read_timeout=timedelta(seconds=cfg.get("sse_read_timeout", 300)),
                    terminate_on_close=cfg.get("terminate_on_close", True),
                )
            # 默认 SSE
            return SseServerParameters(
                url=cfg["url"],
                headers=cfg.get("headers"),
                timeout=cfg.get("timeout", 5),
                sse_read_timeout=cfg.get("sse_read_timeout", 300),
            )
        # STDIO
        return StdioServerParameters(
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            env=cfg.get("env"),
        )

    async def _ensure_group(self):
        if self._group is None:
            # 将工具名聚合为 "serverKey:toolName"
            def name_hook(name: str, server_info) -> str:
                prefix = self._current_prefix or server_info.name
                return f"{prefix}:{name}"

            self._group = ClientSessionGroup(component_name_hook=name_hook)
            await self._group.__aenter__()

    async def _connect_if_needed(self, server_key: str):
        if server_key in self._connected:
            return

        if server_key not in self._servers:
            raise KeyError(f"Unknown server '{server_key}'")

        await self._ensure_group()

        # 并发首连保护
        lock = self._connecting_locks.setdefault(server_key, asyncio.Lock())
        async with lock:
            if server_key in self._connected:
                return

            params = self._create_server_parameters(self._servers[server_key])
            self._current_prefix = server_key
            try:
                session = await self._group.connect_to_server(params)
                self._connected[server_key] = session
                self._last_used_ts[server_key] = self._now()
                logger.debug(f"Connected to server '{server_key}'")
            finally:
                self._current_prefix = None

    async def _disconnect(self, server_key: str):
        if self._group is None:
            return
        session = self._connected.pop(server_key, None)
        self._last_used_ts.pop(server_key, None)
        if session:
            try:
                await self._group.disconnect_from_server(session)
            except Exception as e:
                logger.warning(f"Disconnect '{server_key}' failed: {e}")

    async def _reap_idle(self):
        if not self._connected:
            return
        now = self._now()
        for server_key in list(self._connected.keys()):
            if now - self._last_used_ts.get(server_key, 0) > self._idle_ttl:
                await self._disconnect(server_key)

    def _parse_server_and_tool(self, tool_name: str) -> Tuple[Optional[str], str]:
        if ":" in tool_name:
            sk, tn = tool_name.split(":", 1)
            return sk.strip(), tn.strip()
        return None, tool_name

    # ---------- 对外同步API ----------
    def list_tools(self, discover_all: bool = False) -> list:
        """
        返回当前已连接服务器的工具列表；若 discover_all=True，会按需连接所有服务器以枚举工具。
        为避免常驻，可保持默认 False。
        """
        return self._run_async(self._list_tools_async(discover_all)) or []

    async def _list_tools_async(self, discover_all: bool) -> list:
        await self._ensure_group()
        await self._reap_idle()

        if discover_all:
            # 按需逐个连接（可能较慢，但只在需要时发生）
            for server_key in self._servers.keys():
                if server_key not in self._connected:
                    try:
                        await self._connect_if_needed(server_key)
                    except Exception as e:
                        logger.warning(f"Connect '{server_key}' failed during discovery: {e}")

        tools = []
        for name, tool in (self._group.tools if self._group else {}).items():
            tools.append({
                "name": name,  # 已是 "serverKey:toolName"
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            })
        return tools

    def call_tool(self, tool_name: str, arguments: dict):
        """
        支持两种调用：
        - "serverKey:toolName"：仅连接该server，最省资源（推荐）
        - "toolName"：将按需尝试连接各server，直到发现该工具（可能连接多个server）
        """
        return self._run_async(self._call_tool_async(tool_name, arguments))

    async def _call_tool_async(self, tool_name: str, arguments: dict):
        await self._ensure_group()
        await self._reap_idle()

        server_key, bare_tool = self._parse_server_and_tool(tool_name)

        async def try_call_on(server_key: str, bare_tool: str):
            await self._connect_if_needed(server_key)
            self._last_used_ts[server_key] = self._now()
            qualified = self._qualified(server_key, bare_tool)
            if qualified not in self._group.tools:
                # 工具不存在
                return None, {"error": f"Tool '{qualified}' not found"}
            try:
                res = await self._group.call_tool(qualified, arguments)
                return res, None
            except Exception as e:
                return None, e

        # 已指定 serverKey，最省资源
        if server_key:
            res, err = await try_call_on(server_key, bare_tool)
            # 出错时（崩溃/断线等）尝试一次重连重试
            if err:
                await self._disconnect(server_key)
                try:
                    res2, err2 = await try_call_on(server_key, bare_tool)
                    if err2:
                        raise err2
                    return res2.model_dump()
                except Exception as e:
                    logger.exception(f"Call failed after reconnect on '{server_key}': {e}")
                    return {"error": str(e), "tool_name": tool_name, "arguments": arguments}
            return res.model_dump() if res else {"error": "Unknown error"}

        # 未指定 serverKey：按需连接搜索
        for sk in self._servers.keys():
            try:
                res, err = await try_call_on(sk, bare_tool)
                if err is None and res is not None:
                    return res.model_dump()
                # 不存在该工具则换下一个server；若为传输异常则断开以免占用
                if isinstance(err, (McpError, OSError, ConnectionError)):
                    await self._disconnect(sk)
            except Exception as e:
                await self._disconnect(sk)
                logger.debug(f"Skip server '{sk}' due to error: {e}")

        return {"error": f"Tool '{bare_tool}' not found on any server", "tool_name": tool_name, "arguments": arguments}