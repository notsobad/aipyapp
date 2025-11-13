import asyncio
import contextlib
import sys
import time
import threading
from datetime import timedelta
from typing import Dict, Optional, Tuple, Any
import types as pytypes

from loguru import logger
from mcp.client.session_group import (
    ClientSessionGroup,
    SseServerParameters,
    StreamableHttpParameters,
)
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.shared.exceptions import McpError


class LazyMCPClient:
    """
    惰性MCP会话管理器：
    - 仅在调用某个server的工具时才连接该server
    - 可配置空闲TTL，超时自动断开
    - 支持"serverKey:toolName"命名以避免全量扫描
    """

    def __init__(
        self,
        mcp_servers: dict,
        idle_ttl_seconds: int = 300,
        suppress_output: bool = True,
    ):
        self._servers: dict = mcp_servers or {}
        self._idle_ttl = idle_ttl_seconds
        self._suppress_output = suppress_output

        self._group: Optional[ClientSessionGroup] = None
        self._connected: Dict[str, ClientSession] = {}
        self._last_used_ts: Dict[str, float] = {}  # serverKey -> last used ts
        self._connecting_locks: Dict[str, asyncio.Lock] = {}

        # 用于在聚合时将工具名命名为 "serverKey:toolName"
        self._current_prefix: Optional[str] = None

        # 在后台线程维护持久事件循环，避免每次调用后关闭导致子进程退出
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop_runner, name="LazyMCPClientLoop", daemon=True
        )
        self._loop_thread.start()

    def _loop_runner(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            logger.debug("Event loop stopped")

    def _now(self) -> float:
        return time.time()

    def _qualified(self, server_key: str, tool_name: str) -> str:
        return f"{server_key}:{tool_name}"

    def _build_progress_callback(self, qualified: str):
        """Create an async progress callback for a specific qualified tool name."""
        async def _cb(
            progress: float,
            total: float | None,
            message: str | None,
        ) -> None:
            if total and total > 0:
                pct = f"{(progress / total) * 100:.1f}%"
                detail = f"{progress}/{total}"
            else:
                pct = f"{progress * 100:.1f}%"
                detail = f"{progress:.3f}" if progress <= 1 else f"step={progress}"
            msg_part = f" - {message}" if message else ""
            line = f"[MCP Progress] {qualified}: {pct} ({detail}){msg_part}"
            logger.info(line)
            try:
                # 同步打印到终端（stdout），便于实时观察
                print(line, flush=True)
            except Exception:
                # 打印失败不影响主流程
                pass
        return _cb

    @contextlib.contextmanager
    def _suppress_stdout_stderr(self):
        if not self._suppress_output:
            yield
            return
        orig_out, orig_err = sys.stdout, sys.stderr
        try:
            # 使用 StringIO 而不是 devnull，避免文件关闭问题
            import io

            #dummy_out = io.StringIO()
            dummy_err = io.StringIO()
            #sys.stdout = dummy_out
            sys.stderr = dummy_err
            yield
        except Exception as e:
            # 如果重定向失败，直接使用原始流
            sys.stdout, sys.stderr = orig_out, orig_err
            logger.debug(f"Output suppression failed: {e}")
            yield
        finally:
            sys.stdout, sys.stderr = orig_out, orig_err

    def _run_async(self, coro):
        with self._suppress_stdout_stderr():
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
                return fut.result(timeout=60)  # 添加超时限制
            except asyncio.TimeoutError as e:
                logger.error(f"Async operation timeout (60s): {e}")
                return {"error": "Operation timeout", "details": str(e)}
            except Exception as e:
                logger.error(f"Async run error: {e}")
                return {"error": "Async execution failed", "details": e}

    def _create_server_parameters(self, cfg: dict):
        if "url" in cfg:
            transport_type = cfg.get("transport", {}).get("type")
            if transport_type == "streamable_http":
                return StreamableHttpParameters(
                    url=cfg["url"],
                    headers=cfg.get("headers"),
                    timeout=timedelta(seconds=cfg.get("timeout", 30)),
                    sse_read_timeout=timedelta(
                        seconds=cfg.get("sse_read_timeout", 120)  # 减少超时时间
                    ),
                    terminate_on_close=cfg.get("terminate_on_close", True),
                )
            return SseServerParameters(
                url=cfg["url"],
                headers=cfg.get("headers"),
                timeout=cfg.get("timeout", 10),  # 减少超时时间
                sse_read_timeout=cfg.get("sse_read_timeout", 120),  # 减少超时时间
            )
        return StdioServerParameters(
            command=cfg.get("command", ""), args=cfg.get("args", []), env=cfg.get("env")
        )

    async def _ensure_group(self):
        if self._group is None:

            def name_hook(name: str, server_info) -> str:
                prefix = self._current_prefix or server_info.name
                return f"{prefix}:{name}"

            self._group = ClientSessionGroup(component_name_hook=name_hook)
            await self._group.__aenter__()
            # Patch group.call_tool to support progress_callback
            self._patch_group_for_progress()

    def _patch_group_for_progress(self) -> None:
        """Monkey patch ClientSessionGroup.call_tool to accept progress_callback.

        If a progress_callback is provided, this wrapper will locate the
        underlying session and call session.call_tool with the callback.
        Otherwise, it falls back to the original implementation.
        """
        group = self._group
        if group is None:
            return
        if getattr(group, "_aipy_progress_patched", False):
            return

        orig_call_tool = group.call_tool

        async def call_tool_patched(self_group, name: str, args: dict,
                                    progress_callback=None,
                                    read_timeout_seconds: timedelta | None = None):
            if progress_callback is None and read_timeout_seconds is None:
                return await orig_call_tool(name, args)
            # Find session and delegate with progress
            tool_to_session = getattr(self_group, "_tool_to_session", {})
            tools = getattr(self_group, "tools", {})
            session = tool_to_session.get(name)
            if session is None:
                # Fallback to original behavior
                return await orig_call_tool(name, args)
            session_tool_name = tools[name].name if name in tools else name
            return await session.call_tool(
                session_tool_name,
                args,
                read_timeout_seconds=read_timeout_seconds,
                progress_callback=progress_callback,
            )

        group._orig_call_tool = orig_call_tool  # type: ignore[attr-defined]
        group.call_tool = pytypes.MethodType(call_tool_patched, group)  # type: ignore[assignment]
        group._aipy_progress_patched = True  # type: ignore[attr-defined]

    async def _connect_if_needed(self, server_key: str):
        if server_key in self._connected:
            return
        if server_key not in self._servers:
            raise KeyError(f"Unknown server '{server_key}'")

        await self._ensure_group()
        assert self._group is not None

        lock = self._connecting_locks.setdefault(server_key, asyncio.Lock())
        async with lock:
            if server_key in self._connected:
                return

            params = self._create_server_parameters(self._servers[server_key])
            self._current_prefix = server_key
            try:
                logger.info(f"Connecting to server '{server_key}'...")
                session = await asyncio.wait_for(
                    self._group.connect_to_server(params),
                    timeout=30.0,  # 30秒连接超时
                )
                self._connected[server_key] = session
                self._last_used_ts[server_key] = self._now()
                logger.info(f"Successfully connected to server '{server_key}'")
            except asyncio.TimeoutError:
                logger.error(f"Connection timeout for server '{server_key}' (30s)")
                raise ConnectionError(f"Connection timeout for server '{server_key}'")
            except (OSError, ConnectionError) as e:
                # 网络相关错误
                logger.error(f"Network error connecting to server '{server_key}': {e}")
                raise ConnectionError(f"Network error for server '{server_key}': {e}")
            except Exception as e:
                logger.error(
                    f"Unexpected error connecting to server '{server_key}': {e}"
                )
                raise
            finally:
                self._current_prefix = None

    async def _disconnect(self, server_key: str):
        if self._group is None:
            return
        session = self._connected.pop(server_key, None)
        self._last_used_ts.pop(server_key, None)
        if session:
            try:
                logger.debug(f"Disconnecting from server '{server_key}'...")
                await asyncio.wait_for(
                    self._group.disconnect_from_server(session),
                    timeout=10.0,  # 10秒断开超时
                )
                logger.debug(f"Successfully disconnected from server '{server_key}'")
            except asyncio.TimeoutError:
                logger.warning(f"Disconnect timeout for server '{server_key}' (10s)")
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

    def list_tools(self, discover_all: bool = False) -> list:
        """
        返回当前已连接服务器的工具列表；
        若 discover_all=True，会按需连接所有服务器以枚举工具。
        为避免常驻，可保持默认 False。
        """
        result = self._run_async(self._list_tools_async(discover_all))
        if isinstance(result, dict) and "error" in result:
            logger.error(f"List tools failed: {result}")
            return []
        if isinstance(result, list):
            return result
        return []

    async def _list_tools_async(self, discover_all: bool) -> list:
        await self._ensure_group()
        await self._reap_idle()

        if discover_all:
            for server_key in self._servers.keys():
                if server_key not in self._connected:
                    try:
                        await self._connect_if_needed(server_key)
                    except (ConnectionError, asyncio.TimeoutError) as e:
                        logger.warning(
                            f"Connect '{server_key}' failed during discovery: {e}"
                        )
                    except Exception as e:
                        logger.error(f"Unexpected error connecting '{server_key}': {e}")
                        print("Connect error, skipping server:", server_key)

        tools = []
        if self._group is not None:
            for name, tool in self._group.tools.items():
                tools.append(
                    {
                        "name": name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                )
        return tools

    def _to_obj(self, res: Any):
        if res is None:
            return None
        try:
            return res.model_dump()
        except Exception:
            try:
                return res.dict()
            except Exception:
                return res

    def call_tool(
        self, tool_name: str, arguments: dict, server_name: Optional[str] = None
    ):
        """
        支持三种调用方式：
        1. call_tool("search_web", {}, "Search")  # 推荐：明确指定服务器
        2. call_tool("Search:search_web", {})     # 兼容：使用 serverKey:toolName 格式
        """
        return self._run_async(self._call_tool_async(tool_name, arguments, server_name))

    async def _call_tool_async(
        self, tool_name: str, arguments: dict, server_name: Optional[str] = None
    ):
        await self._ensure_group()
        await self._reap_idle()
        group = self._group
        assert group is not None

        # 优先使用 server_name 参数，其次解析 tool_name 中的服务器名
        if server_name:
            server_key = server_name
            bare_tool = tool_name
        else:
            server_key, bare_tool = self._parse_server_and_tool(tool_name)

        async def try_call_on(server_key: str, bare_tool: str):
            try:
                await self._connect_if_needed(server_key)
                self._last_used_ts[server_key] = self._now()
                qualified = self._qualified(server_key, bare_tool)
                if qualified not in group.tools:
                    return None, {"error": f"Tool '{qualified}' not found"}

                logger.debug(f"Calling tool '{qualified}' with args: {arguments}")
                progress_cb = self._build_progress_callback(qualified)

                # 通过已 patch 的 group.call_tool 注入 progress
                # （使用 getattr 避免签名检查）
                patched_call = getattr(group, "call_tool")
                res = await asyncio.wait_for(
                    patched_call(
                        qualified,
                        arguments,
                        progress_cb,
                    ),
                    timeout=120.0,
                )
                logger.debug(f"Tool '{qualified}' completed successfully")
                return res, None
            except asyncio.TimeoutError as e:
                logger.error(f"Tool call timeout for '{server_key}:{bare_tool}' (120s)")
                return None, {"error": "Tool call timeout", "details": str(e)}
            except ConnectionError as e:
                logger.error(f"Connection error for '{server_key}': {e}")
                return None, {"error": "Connection error", "details": str(e)}
            except (OSError, IOError) as e:
                # 网络I/O错误
                logger.error(f"I/O error for '{server_key}:{bare_tool}': {e}")
                return None, {"error": "I/O error", "details": str(e)}
            except McpError as e:
                logger.error(f"MCP error for '{server_key}:{bare_tool}': {e}")
                return None, {"error": "MCP protocol error", "details": str(e)}
            except Exception as e:
                logger.error(
                    f"Unexpected error calling '{server_key}:{bare_tool}': {e}"
                )
                return None, {"error": "Unexpected error", "details": str(e)}

        if server_key:
            res, err = await try_call_on(server_key, bare_tool)
            if err:
                logger.warning(
                    f"First attempt failed, reconnecting to '{server_key}'..."
                )
                await self._disconnect(server_key)
                try:
                    res2, err2 = await try_call_on(server_key, bare_tool)
                    if err2:
                        logger.error(f"Retry failed for '{server_key}': {err2}")
                        return err2
                    return self._to_obj(res2)
                except Exception as e:
                    logger.exception(
                        f"Call failed after reconnect on '{server_key}': {e}"
                    )
                    return {
                        "error": "Failed after reconnect",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "details": str(e),
                    }
            return self._to_obj(res) if res else {"error": "Unknown error"}

        return {
            "error": f"Tool '{bare_tool}' not found on any server",
            "tool_name": tool_name,
            "arguments": arguments,
        }

    def close(self):
        async def _shutdown():
            logger.info("Shutting down MCP client...")
            for sk in list(self._connected.keys()):
                with contextlib.suppress(Exception):
                    await self._disconnect(sk)
            if self._group is not None:
                with contextlib.suppress(Exception):
                    await self._group.__aexit__(None, None, None)
                self._group = None
            logger.info("MCP client shutdown complete")

        with self._suppress_stdout_stderr():
            try:
                fut = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
                fut.result(timeout=10)  # 增加超时时间到10秒
            except asyncio.TimeoutError:
                logger.error("Shutdown timeout (10s)")
            except Exception as e:
                logger.debug(f"Shutdown error: {e}")
            finally:
                if self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
                if self._loop_thread and self._loop_thread.is_alive():
                    self._loop_thread.join(timeout=5)  # 增加超时时间

    def __del__(self):
        with contextlib.suppress(Exception):
            self.close()
