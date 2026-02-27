import json
import time
import queue
import threading
import socket
from typing import Any, Dict
from loguru import logger

try:
    import websocket
except ImportError:
    # logger has not fully configured yet at module level sometimes
    print("websocket-client not installed. Please run 'uv add websocket-client'")
    websocket = None

print("DEBUG: p_websocket module loaded") # Force print to stdout

from aipyapp import TaskPlugin

class WebSocketManager:
    """Global WebSocket Manager Singleton"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger = logger.bind(src='ws_manager')
        self.ws = None
        self.running = False
        self.thread = None
        self.msg_queue = queue.Queue()
        self.url = None
        self.client_id = None
        self._initialized = True
        self.connect_retry_conf = {'max_retries': 5, 'delay': 2}

    def configure(self, url: str, client_id: str):
        if not url:
            return
        
        # Ensure URL format is correct
        final_url = url
        if '?' in url:
            final_url = f"{url}&id={client_id}"
        else:
            final_url = f"{url}?id={client_id}"
            
        if self.url == final_url and self.running:
            return

        self.url = final_url
        self.client_id = client_id
        self.logger.info(f"WebSocket configured: {self.url}")

    def start(self):
        if self.running or not self.url or not websocket:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()
        
        # Start message sender thread
        self.sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.sender_thread.start()

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
            
    def send(self, message: Any):
        if not self.running:
            return
        
        if not isinstance(message, str):
            try:
                message = json.dumps(message, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"Failed to serialize message: {e}")
                return
                
        self.msg_queue.put(message)

    def _send_loop(self):
        while self.running:
            try:
                message = self.msg_queue.get(timeout=1)
                if self.ws and self.ws.sock and self.ws.sock.connected:
                    try:
                        self.ws.send(message)
                        self.logger.debug(f"Sent: {message[:50]}...")
                    except Exception as e:
                        self.logger.error(f"Failed to send message: {e}")
                        # Put back to queue or discard? For now, discard to avoid loop
                else:
                    # Connection lost, wait a bit
                    time.sleep(1)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in send loop: {e}")

    def _on_message(self, ws, message):
        self.logger.info(f"Received: {message}")
        try:
            # Try to parse as JSON
            data = json.loads(message)
            self._handle_json_message(data)
        except json.JSONDecodeError:
            self._handle_text_message(message)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _handle_json_message(self, data: Dict):
        # Handle standard response format
        if "errCode" in data:
            if data["errCode"] != 0:
                self.logger.warning(f"Server error: {data.get('errMsg')}")
            return

        # Handle other JSON messages (potential commands from server)
        self.logger.info(f"Processing JSON command: {data}")
        # Here we could implement logic to control the agent if needed
        # For now, just logging

    def _handle_text_message(self, message: str):
        self.logger.info(f"Processing text message: {message}")

    def _on_error(self, ws, error):
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
             raise error
        self.logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")

    def _on_open(self, ws):
        self.logger.info("WebSocket connected")

    def _run_forever(self):
        while self.running:
            try:
                self.logger.info(f"Connecting to {self.url}...")
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.run_forever(ping_interval=60, ping_timeout=10)
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
            
            if self.running:
                self.logger.info("Reconnecting in 5 seconds...")
                time.sleep(5)


class WebSocketPlugin(TaskPlugin):
    """
    WebSocket Plugin for AIPy
    
    Configuration example in role.toml:
    [plugins.websocket]
    enabled = true
    config = { url = "ws://localhost:8080/ws", client_id = "aipy-client1" }
    """
    name = "websocket"
    version = "1.0.0"
    description = "WebSocket client plugin for event reporting and remote control"
    
    def init(self):
        if not websocket:
            self.logger.warning("WebSocket plugin disabled: websocket-client not installed")
            return

        url = self.config.get('url', 'ws://localhost:8080/ws')
        client_id = self.config.get('client_id', f'aipy-{int(time.time())}')
        
        self.manager = WebSocketManager()
        self.manager.configure(url, client_id)
        self.manager.start()
        
        self.logger.info("WebSocket plugin initialized")

    # --- Event Handlers ---

    def on_task_started(self, event):
        """Task started event"""
        self.logger.info(f"WebSocket Plugin: on_task_started triggered")
        self.manager.send("开始任务")
        
        task_id = event.task_id
        instruction = event.instruction
        msg = {
            "type": "event",
            "event": "task_started",
            "task_id": task_id,
            "instruction": str(instruction)
        }
        self.manager.send(json.dumps(msg, ensure_ascii=False))

    def on_exec_started(self, event):
        self.logger.info("WebSocket Plugin: on_exec_started triggered")
        self.manager.send("执行代码")

    def on_step_started(self, event):
        msg = {
            "type": "event",
            "event": "step_started",
            "step": event.step,
            "instruction": str(event.instruction)
        }
        self.manager.send(json.dumps(msg, ensure_ascii=False))

    def on_step_completed(self, event):
        """Step completed event"""
        response = event.response
        summary = event.summary
        
        # 尝试提取文本内容
        text_content = ""
        if response and hasattr(response, 'message') and response.message:
            text_content = getattr(response.message, 'content', '')
        elif response:
            text_content = str(response)

        # Send step_completed event with full content and summary
        msg = {
            "type": "event",
            "event": "step_completed",
            "content": text_content,
            "summary": summary
        }
        self.manager.send(json.dumps(msg, ensure_ascii=False))
        
        # Also send raw text content for simple clients
        if text_content:
             self.manager.send(text_content)

    def on_stream(self, event):
        """Streaming content event"""
        # User requested to disable streaming and send full text only
        pass

    def on_runtime_message(self, event):
        """Runtime message event"""
        self.manager.send(event.message)

    def on_exec_completed(self, event):
        """Code execution completed"""
        block = event.block
        result = event.result
        
        msg = {
            "type": "event",
            "event": "exec_completed",
            "block_name": getattr(block, 'name', 'unknown') if block else 'unknown',
            "success": getattr(result, 'success', False) if result else False
        }
        self.manager.send(json.dumps(msg, ensure_ascii=False))

    def on_task_completed(self, event):
        """Task completed event"""
        self.logger.info("WebSocket Plugin: on_task_completed triggered")
        self.manager.send("任务完成")

        task_id = event.task_id
        msg = {
            "type": "event",
            "event": "task_completed",
            "task_id": task_id
        }
        self.manager.send(json.dumps(msg, ensure_ascii=False))

    def on_exception(self, event):
        """Exception event"""
        msg = str(event.msg)
        self.manager.send({
            "type": "event",
            "event": "error",
            "message": msg
        })
