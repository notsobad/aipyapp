# 角色系统

用于定义 LLM 的角色以及提供供 LLM 使用的知识点。

配置文件位于 `~/.aipyapp/tips/` 目录下，格式和文件扩展名为 `.toml`，每个文件可以定义一个角色。

# 配置文件
配置文件为 `TOML` 格式，每个文件为一个 `tips` 字典。每个字典定义一个知识点，字典 key 为知识点名称，值为支持下述字段的字典：
- `short`: 单行的简短描述，精确描述该知识点的功能。
- `detail`: 多行详细描述

其中，名称为 `role` 的知识点用于角色定义，额外支持 `name` 属性，表示该角色的名称。

示例：`https://github.com/knownsec/aipyapp/blob/main/aipyapp/res/tips/aipy.toml`

# 角色使用
目前只支持命令行加载角色：`/use @role.aipy` 其中 `aipy` 为前述配置文件里 `role` 里面的 `name` 属性。


