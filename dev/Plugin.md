# 插件位置

- 配置文件里 plugin_dir 指定的目录
- 或，当前目录下的 `plugins` 目录

每个插件为一个 Python 文件，文件名必须以 `.py` 结尾，且不以 `_` 开头。

**注意**: 后续版本，`plugins` 目录将会固定为 `~/.aipy/plugins`

# 插件接口

插件必须实现 `Plugin` 类，接口定义如下：  

```python
class Plugin:
    def on_task_start(self, prompt):
        pass

    def on_exec(self, blocks):
        pass

    def on_result(self, result):
        pass

    def on_response_complete(self, response):
        pass
```


