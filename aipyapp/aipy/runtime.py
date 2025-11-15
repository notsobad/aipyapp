#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import pickle
from typing import Union, Any, Dict
from functools import wraps
import inspect

from term_image.image import from_file, from_url

from .functions import FunctionManager
from .. import T, TaskPlugin
from ..exec import PythonRuntime
from .blocks import CodeBlock

def restore_output(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

        try:
            return func(self, *args, **kwargs)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
    return wrapper

class CliPythonRuntime(PythonRuntime):
    def __init__(self, task):
        super().__init__(envs=task.role.envs, session=task.session)
        self.task = task
        self.gui = task.gui
        self.display = task.display
        self._auto_install = task.settings.get('auto_install')
        self._auto_getenv = task.settings.get('auto_getenv')
        self.function_manager = FunctionManager()

    def register_plugin(self, plugin: TaskPlugin):
        self.function_manager.register_functions(plugin.get_functions())

    def save_shared_data(self, filename: str, data: Any) -> str:
        """
        Save data to the shared directory for parent-subtask communication

        Args:
            filename: Name of the file (e.g., "data.json", "config.pkl")
            data: Data to save (will be automatically serialized)

        Returns:
            str: Absolute path to the saved file

        Notes:
            - JSON files (.json): Use JSON serialization
            - Pickle files (.pkl, .pickle): Use pickle serialization
            - Text files (.txt): Save as plain text (str required)
            - Other extensions: Use pickle by default

        Examples:
            >>> path = utils.save_shared_data("config.json", {"api_key": "xxx"})
            >>> path = utils.save_shared_data("model.pkl", trained_model)
            >>> path = utils.save_shared_data("report.txt", "Analysis complete")
        """
        shared_dir = self.task.shared_dir
        shared_dir.mkdir(exist_ok=True)

        filepath = shared_dir / filename
        ext = filepath.suffix.lower()

        if ext == ".json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif ext == ".txt":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(data))
        else:  # .pkl, .pickle, or default to pickle
            with open(filepath, "wb") as f:
                pickle.dump(data, f)

        self.log.info(f"Saved shared data to: {filepath}")
        return str(filepath.absolute())

    def load_shared_data(self, filename: str) -> Any:
        """
        Load data from the shared directory

        Args:
            filename: Name of the file to load

        Returns:
            Any: Deserialized data

        Raises:
            FileNotFoundError: If the file is not found

        Notes:
            - Automatically detects format based on file extension

        Examples:
            >>> config = utils.load_shared_data("config.json")
            >>> model = utils.load_shared_data("model.pkl")
            >>> result = utils.load_shared_data("result.json")
        """
        filepath = self.task.shared_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(
                f"Shared file '{filename}' not found in {self.task.shared_dir}"
            )

        ext = filepath.suffix.lower()

        if ext == ".json":
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif ext == ".txt":
            with open(filepath, "r", encoding="utf-8") as f:
                data = f.read()
        else:  # .pkl, .pickle, or default to pickle
            with open(filepath, "rb") as f:
                data = pickle.load(f)

        self.log.info(f"Loaded shared data from: {filepath}")
        return data

    @restore_output
    def install_packages(self, *packages: str) -> bool:
        """
        Install third-party packages

        Args:
            packages: The names of the packages to install

        Returns:
            bool: True if the packages are installed successfully, False otherwise

        Examples:
            >>> utils.install_packages('requests', 'openai')
            True
            >>> utils.install_packages('requests', 'openai')
            False
        """
        message = f"LLM {T('Request to install third-party packages')}: {packages}"
        self.task.emit('runtime_message', message=message, status='warning')
        
        if self.display:
            prompt = f"{T('If you agree, please enter')} 'y'> "
            ok = self.display.confirm(prompt, auto=self._auto_install)
        else:
            ok = True
            
        if ok:
            ret = self.ensure_packages(*packages)
            result_message = T("Package installation completed") if ret else T("Package installation failed")
            self.task.emit('runtime_message', message=result_message, status='success' if ret else 'error')
            return ret
        return False
    
    @restore_output
    def get_env(self, name: str, default: str = None, *, desc: str = None) -> Union[str, None]:
        message = f"LLM {T('Request to obtain environment variable {}, purpose', name)}: {desc}"
        self.task.emit('runtime_message', message=message)
        
        try:
            value = self.envs[name][0]
            success_message = f"{T('Environment variable {} exists, returned for code use', name)}"
            self.task.emit('runtime_message', message=success_message)
        except KeyError:
            if self._auto_getenv:
                auto_message = T('Auto confirm')
                self.task.emit('runtime_message', message=auto_message)
                value = None
            elif self.display:
                prompt = f"{T('Environment variable {} not found, please enter', name)}: "
                value = self.display.input(prompt)
                value = value.strip()
            else:
                value = None
            if value:
                self.set_env(name, value, desc)
        return value or default
    
    @restore_output
    def show_image(self, path: str = None, url: str = None) -> None:
        """
        Display an image

        Args:
            path: The path of the image
            url: The URL of the image
        """
        self.task.emit('show_image', path=path, url=url)
        if not self.gui:
            image = from_file(path) if path else from_url(url)
            image.draw()

    @restore_output
    def input(self, prompt: str) -> str:
        self.task.emit('runtime_input', prompt=prompt)
        if self.display:
            return self.display.input(prompt)
        return None
    
    def get_block_by_name(self, block_name: str) -> Union[CodeBlock, None]:
        """
        Get a code block by name

        Args:
            block_name: The name of the code block

        Returns:
            CodeBlock: The code block objector None if not found
        """
        return self.task.blocks.get_block_by_name(block_name)
    
    def call_function(self, name: str, **kwargs) -> Any:
        """
        Call a registered function

        Args:
            name: The name of the function to call
            **kwargs: The keyword arguments to pass to the function

        Returns:
            Any: The result of the function call or raise an exception

        Examples:
            >>> utils.call_function('get_env', name='PATH')
            '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
            >>> utils.call_function('get_env', name='PATH')
            None
        """
        self.task.emit('function_call_started', funcname=name, kwargs=kwargs)
        try:
            result = self.function_manager.call(name, **kwargs)
            self.task.emit('function_call_completed', funcname=name, kwargs=kwargs, result=result, success=True)
            return result
        except Exception as e:
            self.task.emit('function_call_completed', funcname=name, kwargs=kwargs, result=None, success=False, error=str(e), exception=e)
            raise
    
    def should_stop(self) -> bool:
        """
        检查用户是否请求停止当前代码块执行

        Returns:
            bool: 如果用户请求停止，返回 True；否则返回 False

        用法示例：
            while True:
                if utils.should_stop():
                    print("执行被用户中止")
                    break
                do_something()
        """
        if hasattr(self.task, 'is_stopped') and callable(self.task.is_stopped):
            return self.task.is_stopped()
        if hasattr(self.task, 'stop_event'):
            return self.task.stop_event.is_set()
        return False

    def set_operation(self, operation_name: str, total_items: int = None) -> None:
        """
        标记开始一个长时间操作（知道总数）

        Args:
            operation_name: 操作的名称（如 "数据处理", "模型训练"）
            total_items: 总项数（可选）

        用法示例：
            utils.set_operation("数据处理", total_items=1000)
        """
        self.current_operation = {
            'name': operation_name,
            'total_items': total_items,
            'current_items': 0,
        }
        self.task.emit('operation_started',
                       operation_name=operation_name,
                       total=total_items)

    def update_operation(self, current: int = None, message: str = "") -> None:
        """
        更新操作进度

        Args:
            current: 当前完成的项数（0-total_items）
            message: 额外的进度信息

        用法示例：
            for i in range(1000):
                if utils.should_stop():
                    break
                process_item(i)
                utils.update_operation(i+1, f"处理中... {i+1}/1000")
        """
        if not hasattr(self, 'current_operation'):
            return

        if current is not None:
            self.current_operation['current_items'] = current

        total = self.current_operation.get('total_items')
        percent = None
        if total and current:
            percent = int((current / total) * 100)

        self.task.emit('operation_progress',
                       current=current,
                       total=total,
                       percent=percent,
                       message=message)

    def finish_operation(self, success: bool = True, message: str = "") -> None:
        """
        标记操作完成

        Args:
            success: 操作是否成功完成
            message: 完成信息

        用法示例：
            utils.finish_operation(success=True, message="数据处理完成，共处理 1000 条记录")
        """
        self.task.emit('operation_finished',
                       success=success,
                       message=message)
        if hasattr(self, 'current_operation'):
            delattr(self, 'current_operation')

    def report_progress(self, progress: int, message: str = "") -> None:
        """
        报告操作进度（不知道总数）

        Args:
            progress: 进度值（通常 0-100 表示百分比，也可自定义）
            message: 进度描述信息

        用法示例：
            for i in range(100):
                utils.report_progress(i+1, f"完成 {i+1}%")
        """
        self.task.emit('progress_report',
                       progress=progress,
                       message=message)

    def get_builtin_functions(self) -> Dict[str, Dict[str, str]]:
        """
        根据函数签名和docstring，生成函数调用提示
        """
        functions = {}

        # 内置运行时函数
        builtin_names = ['set_state', 'get_block_state', 'set_persistent_state', 'get_persistent_state', 'install_packages', 'get_env', 'show_image', 'get_block_by_name', 'call_function', 'save_shared_data', 'load_shared_data', 'should_stop', 'set_operation', 'update_operation', 'finish_operation', 'report_progress']
        for name in builtin_names:
            func_obj = getattr(self, name)
            docstring = func_obj.__doc__
            signature = inspect.signature(func_obj)
            functions[name] = {
                'docstring': docstring,
                'signature': signature,
            }
        return functions
    
    def get_plugin_functions(self):
        return self.function_manager.get_functions()
        