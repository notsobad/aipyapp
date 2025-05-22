# MCP 使用说明

MCP (Model Context Protocol) 是一组工具协议，允许 AI 模型与外部工具交互。在 aipyapp 中，您可以配置和使用多种 MCP 工具来增强 AI 助手的能力。本文档将指导您完成 MCP 的配置和使用。

## 1. MCP 环境安装

### 基础环境要求

- Node.js 环境 (用于大部分 MCP 工具)

### 安装特定 MCP 工具

根据您使用的工具类型，可能需要安装额外的依赖：

1. **基于 Node.js 的工具**：

   ```bash
   # 文件系统工具
   npm install -g @modelcontextprotocol/server-filesystem
   
   # Everything 搜索工具
   npm install -g @modelcontextprotocol/server-everything
   
   # Playwright 工具
   npm install -g @playwright/mcp
   ```

2. **基于 Python 的工具**：
   
   您可以创建自己的 Python MCP 工具，或安装第三方工具：
   
   ```bash
   # 示例：安装天气 MCP 工具
   pip install mcp-weather-tools
   ```

## 2. MCP 配置文件

aipyapp 使用 JSON 格式的配置文件来管理 MCP 工具。默认配置文件位置为应用程序配置目录下的 `mcp.json`。

**注意：目前暂时仅支持stdio方式调用的MCP服务**

### 配置文件格式

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/path/to/directory1",
        "/path/to/directory2"
      ]
    },
    "everything": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-everything"
      ]
    },
    "weather": {
      "command": "/path/to/python",
      "args": [
        "/path/to/weather.py"
      ]
    },
    "disabled_server": {
      "command": "some-tool",
      "args": [],
      "disabled": true
    }
  }
}
```

### 配置文件位置

配置文件位置默认为应用程序配置目录下的 `mcp.json`。您可以通过以下方式查找和创建配置：

- aipy的命令行界面中查看配置目录：`/info`
- 手动创建配置：在应用程序配置目录创建 `mcp.json` 文件

## 3. 配置 MCP 服务器

### 服务器配置字段

每个 MCP 服务器配置可以包含以下字段：

- `command`：(必填) 执行命令，可以是可执行文件路径或命令名称
- `args`：(可选) 命令行参数数组
- `env`：(可选) 环境变量对象
- `disabled`：(可选) 设置为 `true` 时禁用该服务器
- `enabled`：(可选) 设置为 `false` 时禁用该服务器

### 常见工具配置示例

1. **文件系统工具**：

```json
"filesystem": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-filesystem",
    "/home/user/documents",
    "/home/user/projects"
  ]
}
```

2. **Everything 搜索工具**：

```json
"everything": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-everything"
  ]
}
```

3. **自定义 Python 工具**：

```json
"custom_tool": {
  "command": "/path/to/venv/bin/python",
  "args": [
    "/path/to/your_script.py"
  ],
  "env": {
    "API_KEY": "your-api-key",
    "DEBUG": "true"
  }
}
```

## 4. 启用和禁用 MCP 服务器

您可以通过以下两种方式启用或禁用 MCP 服务器：

### 方法一：使用 `disabled` 属性

添加 `"disabled": true` 字段来禁用一个服务器：

```json
"server_name": {
  "command": "...",
  "args": [...],
  "disabled": true  // 禁用该服务器
}
```

### 方法二：使用 `enabled` 属性

添加 `"enabled": false` 字段来禁用一个服务器：

```json
"server_name": {
  "command": "...",
  "args": [...],
  "enabled": false  // 禁用该服务器
}
```

## 5. 缓存机制

为提高性能，aipyapp 会将 MCP 工具列表缓存到文件中，避免每次启动都重新加载所有工具。缓存文件位于与 `mcp.json` 同一目录下，名称为 `mcp_tools_cache.json`。

缓存在以下情况会被自动更新：
- `mcp.json` 文件被修改
- 缓存文件不存在或无效
- 缓存时间超过 48 小时

如果您添加或修改了工具但缓存未更新，可以删除 `mcp_tools_cache.json` 文件，aipyapp 将在下次启动时重新加载所有工具。

## 6. 使用 MCP 工具

在 aipyapp 中，AI 助手会自动识别可能需要使用工具的请求，并调用合适的工具。您只需要向 AI 提出问题，例如：

```
搜索我的文档里含有"人工智能"的文件
```

如果需要了解所有可用的工具，可以在 aipyapp 中查看：

```
请列出所有可用的工具及其用途
```

## 7. 常见问题排查

1. **工具未显示**：检查 `mcp.json` 配置，确保 `command` 路径正确
2. **工具调用失败**：检查工具依赖是否已安装，命令是否可执行
3. **权限问题**：确保命令有足够的权限执行
4. **性能问题**：如果工具加载缓慢，请检查缓存文件是否正确

如果仍然有问题，可以删除缓存文件 `mcp_tools_cache.json` 并重启 aipyapp。

